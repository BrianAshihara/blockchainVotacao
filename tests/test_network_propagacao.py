"""
Testes para network/propagacao.py

Cobre propagacao HTTP de transacoes, blocos e votacoes para peers,
e handshake de registro. Todas as chamadas HTTP sao mockadas.
"""

from unittest.mock import patch, call, MagicMock
import requests

from network.propagacao import (
    propagar_transacao, propagar_bloco, propagar_votacao, registrar_em_peer
)


# ==================== propagar_transacao ====================

def test_propagar_transacao_chama_todos_peers(transacao_assinada):
    peers = ["peer1:5000", "peer2:5001"]
    with patch("network.propagacao.requests.post") as mock_post:
        propagar_transacao(transacao_assinada, peers, 5000)
    assert mock_post.call_count == 2


def test_propagar_transacao_url_correta(transacao_assinada):
    with patch("network.propagacao.requests.post") as mock_post:
        propagar_transacao(transacao_assinada, ["peer1:5000"], 5000)
    mock_post.assert_called_once()
    url_chamada = mock_post.call_args[0][0]
    assert url_chamada == "http://peer1:5000/transacao"


def test_propagar_transacao_payload_correto(transacao_assinada):
    with patch("network.propagacao.requests.post") as mock_post:
        propagar_transacao(transacao_assinada, ["peer1:5000"], 5000)
    kwargs = mock_post.call_args[1]
    assert kwargs["json"] == transacao_assinada.to_dict()


def test_propagar_transacao_peer_falha_nao_interrompe(transacao_assinada):
    with patch("network.propagacao.requests.post") as mock_post:
        mock_post.side_effect = [
            requests.exceptions.ConnectionError("falha"),
            MagicMock()
        ]
        propagar_transacao(transacao_assinada, ["peer1:5000", "peer2:5001"], 5000)
    assert mock_post.call_count == 2


def test_propagar_transacao_sem_peers(transacao_assinada):
    with patch("network.propagacao.requests.post") as mock_post:
        propagar_transacao(transacao_assinada, [], 5000)
    mock_post.assert_not_called()


# ==================== propagar_bloco ====================

def test_propagar_bloco_chama_todos_peers(bloco_genesis):
    peers = ["peer1:5000", "peer2:5001"]
    with patch("network.propagacao.requests.post") as mock_post:
        propagar_bloco(bloco_genesis, peers, 5000)
    assert mock_post.call_count == 2


def test_propagar_bloco_payload_correto(bloco_genesis):
    with patch("network.propagacao.requests.post") as mock_post:
        propagar_bloco(bloco_genesis, ["peer1:5000"], 5000)
    kwargs = mock_post.call_args[1]
    assert kwargs["json"] == bloco_genesis.to_dict()


def test_propagar_bloco_peer_falha_nao_interrompe(bloco_genesis):
    with patch("network.propagacao.requests.post") as mock_post:
        mock_post.side_effect = [
            requests.exceptions.ConnectionError("falha"),
            MagicMock()
        ]
        propagar_bloco(bloco_genesis, ["peer1:5000", "peer2:5001"], 5000)
    assert mock_post.call_count == 2


# ==================== propagar_votacao ====================

def test_propagar_votacao_chama_todos_peers():
    dados = {"id_votacao": "v1", "nome": "Teste", "opcoes": ["A", "B"], "ativa": True}
    with patch("network.propagacao.requests.post") as mock_post:
        propagar_votacao(dados, ["peer1:5000", "peer2:5001"], 5000)
    assert mock_post.call_count == 2


def test_propagar_votacao_payload_correto():
    dados = {"id_votacao": "v1", "nome": "Teste", "opcoes": ["A", "B"], "ativa": True}
    with patch("network.propagacao.requests.post") as mock_post:
        propagar_votacao(dados, ["peer1:5000"], 5000)
    kwargs = mock_post.call_args[1]
    assert kwargs["json"] == dados


# ==================== registrar_em_peer ====================

def test_registrar_em_peer_sucesso():
    with patch("network.propagacao.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        resultado = registrar_em_peer("peer1:5000", "localhost:5001")
    assert resultado is True


def test_registrar_em_peer_falha_conexao():
    with patch("network.propagacao.requests.post") as mock_post:
        mock_post.side_effect = requests.exceptions.ConnectionError("falha")
        resultado = registrar_em_peer("peer1:5000", "localhost:5001")
    assert resultado is False


def test_registrar_em_peer_url_correta():
    with patch("network.propagacao.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        registrar_em_peer("peer1:5000", "localhost:5001")
    url_chamada = mock_post.call_args[0][0]
    assert url_chamada == "http://peer1:5000/peers/registrar"


def test_registrar_em_peer_payload_correto():
    with patch("network.propagacao.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        registrar_em_peer("peer1:5000", "localhost:5001")
    kwargs = mock_post.call_args[1]
    assert kwargs["json"] == {"endereco": "localhost:5001"}
