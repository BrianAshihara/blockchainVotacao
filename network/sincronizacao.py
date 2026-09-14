import logging
import time

import requests

from core.cadeia import eleitor_ja_votou
from network.consenso import resolver_conflitos
from network.propagacao import registrar_em_peer

logger = logging.getLogger(__name__)
TIMEOUT_REQUISICAO = 10


def sincronizar_chain(estado) -> bool:
    """
    Sincroniza a chain local com a rede.
    Chamado no startup, quando um gap de blocos e detectado e quando chega um
    bloco valido de outro ramo (bifurcacao).

    Tambem recupera transacoes orfas: se a chain local e substituida,
    transacoes que estavam em blocos locais mas NAO estao na nova chain
    sao re-adicionadas a mempool.

    Returns True se a chain foi substituida.
    """
    # varios blocos fora de ordem podem pedir sincronizacao juntos; basta uma por vez
    if not estado._sync_lock.acquire(blocking=False):
        logger.info("Sincronizacao ja em andamento.")
        return False

    try:
        peers = estado.peers.listar()
        if not peers:
            logger.info("Nenhum peer conhecido. Nada para sincronizar.")
            return False

        nova_chain = resolver_conflitos(estado.blocos, peers, usar_tls=estado.usar_tls,
                                        caminho_votacoes=estado.caminho_votacoes)

        if nova_chain is not None:
            # Coleta hashes das txs na nova chain
            tx_hashes_nova = set()
            for bloco in nova_chain:
                for tx in bloco.transacoes:
                    tx_hashes_nova.add(tx.calcular_hash())

            # Recupera txs orfas (estavam na chain local mas nao na nova)
            for bloco in estado.blocos[1:]:  # skip genesis
                for tx in bloco.transacoes:
                    if tx.calcular_hash() in tx_hashes_nova:
                        continue
                    # eleitor que ja tem voto no ramo vencedor nao recupera o orfao (seria voto duplo)
                    if eleitor_ja_votou(nova_chain, tx.chave_publica, tx.id_votacao):
                        continue
                    estado.mempool.adicionar(tx)

            estado.substituir_chain(nova_chain)

            # Remove da mempool txs que ja estao na nova chain
            estado.mempool.remover_varias(list(tx_hashes_nova))

            logger.info(f"Chain substituida. Novo comprimento: {len(nova_chain)}")
            return True

        logger.info("Chain local ja e a mais longa.")
        return False
    finally:
        estado._sync_lock.release()


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
    from node.identidade import verificar_mensagem
    from sistema.votacao import merge_votacao, votacao_recebida_valida

    peers = estado.peers.listar()
    if not peers:
        return

    protocolo = "https" if estado.usar_tls else "http"

    for peer in peers:
        try:
            url = f"{protocolo}://{peer}/votacoes"
            resp = requests.get(url, timeout=TIMEOUT_REQUISICAO)
            if resp.status_code != 200:
                continue
            dados = resp.json()
            votacoes = dados.get("votacoes")
            # qualquer um pode se registrar como peer, entao so vale resposta assinada por no confiavel
            autenticada, motivo = verificar_mensagem(votacoes, dados, estado.nos_confiaveis.listar())
            if not autenticada or not isinstance(votacoes, list):
                logger.warning(f"Votacoes de {peer} ignoradas: {motivo or 'resposta invalida'}")
                continue
            for votacao in votacoes:
                if not votacao_recebida_valida(votacao):
                    logger.warning(f"Votacao com dados invalidos ignorada (peer {peer})")
                    continue
                merge_votacao(votacao, caminho=estado.caminho_votacoes)
            logger.info(f"Votacoes sincronizadas com {peer}")
        except (requests.exceptions.RequestException, ValueError, AttributeError) as e:
            logger.warning(f"Falha ao sincronizar votacoes com {peer}: {e}")


def sincronizar_votacoes_e_chain(estado) -> bool:
    # Atualiza as sessoes e depois a cadeia
    sincronizar_votacoes(estado)
    return sincronizar_chain(estado)


def iniciar_sincronizacao(estado, endereco_local: str):
    """
    Procedimento completo de startup sync.
    1. Registrar nos peers
    2. Sincronizar votacoes (antes da chain: os votos sao validados contra as sessoes)
    3. Sincronizar chain
    """
    registrar_nos_peers(estado, endereco_local)
    sincronizar_votacoes(estado)
    sincronizar_chain(estado)


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
