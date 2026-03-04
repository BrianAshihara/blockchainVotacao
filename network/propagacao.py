import logging
import time
from datetime import datetime, timezone
from typing import List

import requests

from core.transacao import Transacao
from core.bloco import Bloco

logger = logging.getLogger(__name__)
TIMEOUT_REQUISICAO = 5


def _url_peer(peer: str, caminho: str, usar_tls: bool = False) -> str:
    """Constroi URL com protocolo correto (http ou https)."""
    protocolo = "https" if usar_tls else "http"
    return f"{protocolo}://{peer}{caminho}"


def _enviar_com_retry(url: str, json_data: dict, tentativas: int = 3) -> bool:
    """
    Envia POST com retry e backoff exponencial.
    Delays: 1s, 2s, 4s entre tentativas.
    """
    for i in range(tentativas):
        try:
            resp = requests.post(url, json=json_data, timeout=TIMEOUT_REQUISICAO)
            return resp.status_code in (200, 201, 202)
        except requests.exceptions.RequestException as e:
            if i < tentativas - 1:
                time.sleep(2 ** i)
            else:
                logger.warning(f"Falha apos {tentativas} tentativas para {url}: {e}")
    return False


def propagar_transacao(tx: Transacao, peers: List[str], porta_local: int,
                       usar_tls: bool = False):
    """
    Envia transacao para todos os peers conhecidos.
    Chamada em background thread. Retry com backoff em caso de falha.
    """
    for peer in peers:
        url = _url_peer(peer, "/transacao", usar_tls)
        _enviar_com_retry(url, tx.to_dict())


def propagar_bloco(bloco: Bloco, peers: List[str], porta_local: int,
                   usar_tls: bool = False):
    """
    Envia bloco minerado para todos os peers.
    """
    for peer in peers:
        url = _url_peer(peer, "/bloco", usar_tls)
        _enviar_com_retry(url, bloco.to_dict())


def propagar_votacao(dados_votacao: dict, peers: List[str], porta_local: int,
                     usar_tls: bool = False):
    """
    Envia sessao de votacao para todos os peers.
    """
    for peer in peers:
        url = _url_peer(peer, "/votacao", usar_tls)
        _enviar_com_retry(url, dados_votacao)


def registrar_em_peer(endereco_peer: str, endereco_local: str,
                      identidade=None, usar_tls: bool = False) -> bool:
    """
    Registra este no em um peer remoto (handshake bidirecional).
    Se identidade for fornecida, envia payload assinado para autenticacao.
    """
    payload = {"endereco": endereco_local}

    if identidade is not None:
        from core.cripto import assinar
        timestamp = datetime.now(timezone.utc).isoformat()
        dados_para_assinar = f"{endereco_local}:{timestamp}"
        assinatura = assinar(identidade.chave_privada, dados_para_assinar)
        payload.update({
            "id_no": identidade.id_no,
            "chave_publica": identidade.chave_publica,
            "timestamp": timestamp,
            "assinatura": assinatura
        })

    url = _url_peer(endereco_peer, "/peers/registrar", usar_tls)
    return _enviar_com_retry(url, payload)
