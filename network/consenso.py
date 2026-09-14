import logging
from typing import List, Optional

import requests

from core.bloco import Bloco
from core.cadeia import verificar_integridade
from core.validacao import validar_votos_da_cadeia

logger = logging.getLogger(__name__)
TIMEOUT_REQUISICAO = 10


def resolver_conflitos(blocos_locais: List[Bloco], peers: List[str],
                       usar_tls: bool = False, caminho_votacoes: str = None) -> Optional[List[Bloco]]:
    """
    Implementa consenso por cadeia mais longa (Nakamoto consensus).

    1. Consulta comprimento de cada peer
    2. Para peers com chain mais longa, baixa a chain completa
    3. Valida integridade da chain recebida (hashes, PoW, dificuldade minima)
    4. Com caminho_votacoes, valida tambem os votos (sessao, opcao, chave autorizada, voto duplo)
    5. Se valida e mais longa, retorna como substituta

    Returns:
        Nova chain se encontrou uma mais longa e valida, None caso contrario.
    """
    comprimento_local = len(blocos_locais)
    melhor_chain: Optional[List[Bloco]] = None
    maior_comprimento = comprimento_local

    protocolo = "https" if usar_tls else "http"

    for peer in peers:
        try:
            resp_comp = requests.get(
                f"{protocolo}://{peer}/chain/comprimento",
                timeout=TIMEOUT_REQUISICAO
            )
            comp_remoto = resp_comp.json()["comprimento"]

            if comp_remoto <= maior_comprimento:
                continue

            resp_chain = requests.get(
                f"{protocolo}://{peer}/chain",
                timeout=TIMEOUT_REQUISICAO
            )
            dados = resp_chain.json()
            chain_remota = [Bloco.from_dict(b) for b in dados["blocos"]]

            if not verificar_integridade(chain_remota):
                logger.warning(f"Chain invalida recebida de {peer}")
                continue

            if caminho_votacoes is not None:
                votos_validos, motivo = validar_votos_da_cadeia(chain_remota, caminho_votacoes)
                if not votos_validos:
                    logger.warning(f"Chain de {peer} com voto invalido: {motivo}")
                    continue

            maior_comprimento = len(chain_remota)
            melhor_chain = chain_remota
            logger.info(f"Chain mais longa encontrada em {peer}: {maior_comprimento} blocos")

        except requests.exceptions.RequestException as e:
            logger.warning(f"Falha ao consultar peer {peer}: {e}")
        except (KeyError, ValueError) as e:
            logger.warning(f"Resposta invalida de {peer}: {e}")

    return melhor_chain
