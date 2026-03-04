import logging
import time

import requests

from network.consenso import resolver_conflitos
from network.propagacao import registrar_em_peer

logger = logging.getLogger(__name__)
TIMEOUT_REQUISICAO = 10


def sincronizar_chain(estado) -> bool:
    """
    Sincroniza a chain local com a rede.
    Chamado no startup e quando um gap de blocos e detectado.

    Tambem recupera transacoes orfas: se a chain local e substituida,
    transacoes que estavam em blocos locais mas NAO estao na nova chain
    sao re-adicionadas a mempool.

    Returns True se a chain foi substituida.
    """
    peers = estado.peers.listar()
    if not peers:
        logger.info("Nenhum peer conhecido. Nada para sincronizar.")
        return False

    nova_chain = resolver_conflitos(estado.blocos, peers, usar_tls=estado.usar_tls)

    if nova_chain is not None:
        # Coleta hashes das txs na nova chain
        tx_hashes_nova = set()
        for bloco in nova_chain:
            for tx in bloco.transacoes:
                tx_hashes_nova.add(tx.calcular_hash())

        # Recupera txs orfas (estavam na chain local mas nao na nova)
        for bloco in estado.blocos[1:]:  # skip genesis
            for tx in bloco.transacoes:
                if tx.calcular_hash() not in tx_hashes_nova:
                    estado.mempool.adicionar(tx)

        estado.substituir_chain(nova_chain)

        # Remove da mempool txs que ja estao na nova chain
        estado.mempool.remover_varias(list(tx_hashes_nova))

        logger.info(f"Chain substituida. Novo comprimento: {len(nova_chain)}")
        return True

    logger.info("Chain local ja e a mais longa.")
    return False


def registrar_nos_peers(estado, endereco_local: str):
    """Registra este no em todos os peers conhecidos (handshake)."""
    for peer in estado.peers.listar():
        sucesso = registrar_em_peer(
            peer, endereco_local,
            identidade=estado.identidade,
            usar_tls=estado.usar_tls
        )
        if sucesso:
            logger.info(f"Registrado em peer {peer}")
        else:
            logger.warning(f"Falha ao registrar em peer {peer}")


def sincronizar_votacoes(estado):
    """
    Sincroniza sessoes de votacao com os peers.
    GET /votacoes de cada peer, merge local.
    """
    from sistema.votacao import merge_votacao

    peers = estado.peers.listar()
    if not peers:
        return

    protocolo = "https" if estado.usar_tls else "http"

    for peer in peers:
        try:
            url = f"{protocolo}://{peer}/votacoes"
            resp = requests.get(url, timeout=TIMEOUT_REQUISICAO)
            if resp.status_code == 200:
                dados = resp.json()
                for votacao in dados.get("votacoes", []):
                    merge_votacao(votacao, caminho=estado.caminho_votacoes)
                logger.info(f"Votacoes sincronizadas com {peer}")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Falha ao sincronizar votacoes com {peer}: {e}")


def iniciar_sincronizacao(estado, endereco_local: str):
    """
    Procedimento completo de startup sync.
    1. Registrar nos peers
    2. Sincronizar chain
    3. Sincronizar votacoes
    """
    registrar_nos_peers(estado, endereco_local)
    sincronizar_chain(estado)
    sincronizar_votacoes(estado)


def loop_verificacao_peers(estado, endereco_local: str, intervalo: int = 60):
    """
    Loop periodico que verifica saude dos peers.
    - Pinga cada peer com GET /no/info (2s timeout)
    - Se um peer falha 3 vezes consecutivas, loga aviso
    - Se um peer que estava fora volta, re-registra automaticamente
    """
    falhas_consecutivas: dict[str, int] = {}
    protocolo = "https" if estado.usar_tls else "http"

    while True:
        time.sleep(intervalo)

        for peer in estado.peers.listar():
            try:
                resp = requests.get(
                    f"{protocolo}://{peer}/no/info",
                    timeout=2
                )
                if resp.status_code == 200:
                    falhas_anteriores = falhas_consecutivas.get(peer, 0)
                    falhas_consecutivas[peer] = 0

                    if falhas_anteriores >= 1:
                        logger.info(f"Peer {peer} voltou a responder. Re-registrando...")
                        registrar_em_peer(
                            peer, endereco_local,
                            identidade=estado.identidade,
                            usar_tls=estado.usar_tls
                        )
                    continue
            except requests.exceptions.RequestException:
                pass

            falhas_consecutivas[peer] = falhas_consecutivas.get(peer, 0) + 1
            contagem = falhas_consecutivas[peer]

            if contagem == 3:
                logger.warning(f"Peer {peer} inalcancavel (3 falhas consecutivas)")
            elif contagem > 3 and contagem % 10 == 0:
                logger.warning(f"Peer {peer} inalcancavel ({contagem} falhas consecutivas)")
