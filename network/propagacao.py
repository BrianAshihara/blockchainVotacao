import logging
from typing import List

import requests

from core.transacao import Transacao
from core.bloco import Bloco

logger = logging.getLogger(__name__)
TIMEOUT_REQUISICAO = 5


def propagar_transacao(tx: Transacao, peers: List[str], porta_local: int):
    """
    Envia transacao para todos os peers conhecidos.
    Chamada em background thread. Ignora falhas silenciosamente.
    """
    for peer in peers:
        try:
            url = f"http://{peer}/transacao"
            requests.post(url, json=tx.to_dict(), timeout=TIMEOUT_REQUISICAO)
        except requests.exceptions.RequestException as e:
            logger.warning(f"Falha ao propagar transacao para {peer}: {e}")


def propagar_bloco(bloco: Bloco, peers: List[str], porta_local: int):
    """
    Envia bloco minerado para todos os peers.
    """
    for peer in peers:
        try:
            url = f"http://{peer}/bloco"
            requests.post(url, json=bloco.to_dict(), timeout=TIMEOUT_REQUISICAO)
        except requests.exceptions.RequestException as e:
            logger.warning(f"Falha ao propagar bloco para {peer}: {e}")


def propagar_votacao(dados_votacao: dict, peers: List[str], porta_local: int):
    """
    Envia sessao de votacao para todos os peers.
    """
    for peer in peers:
        try:
            url = f"http://{peer}/votacao"
            requests.post(url, json=dados_votacao, timeout=TIMEOUT_REQUISICAO)
        except requests.exceptions.RequestException as e:
            logger.warning(f"Falha ao propagar votacao para {peer}: {e}")


def registrar_em_peer(endereco_peer: str, endereco_local: str) -> bool:
    """
    Registra este no em um peer remoto (handshake bidirecional).
    """
    try:
        url = f"http://{endereco_peer}/peers/registrar"
        resp = requests.post(url, json={"endereco": endereco_local}, timeout=TIMEOUT_REQUISICAO)
        return resp.status_code == 200
    except requests.exceptions.RequestException:
        return False
