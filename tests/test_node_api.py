"""
Testes para node/api.py

Cobre todos os 14 endpoints Flask via test_client.
Usa unittest.mock.patch para threads de propagacao (previne HTTP real).
"""

from unittest.mock import patch, MagicMock

from core.transacao import Transacao
from core.bloco import Bloco
from core.cripto import gerar_par_chaves, assinar
from core.mineracao import minerar_bloco
from core.cadeia import criar_bloco_genesis

DIFICULDADE_TESTE = 1


# ==================== Chain endpoints ====================

def test_get_chain(app_client):
    client, estado = app_client
    resp = client.get("/chain")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "comprimento" in data
    assert "blocos" in data
    assert data["comprimento"] == 1


def test_get_chain_comprimento(app_client):
    client, estado = app_client
    resp = client.get("/chain/comprimento")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["comprimento"] == 1


def test_get_chain_integridade_valida(app_client):
    client, estado = app_client
    resp = client.get("/chain/integridade")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["valida"] is True


def test_get_chain_integridade_chain_corrompida(app_client, transacao_assinada):
    client, estado = app_client
    genesis = estado.blocos[0]
    bloco = minerar_bloco(genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    estado.adicionar_bloco(bloco)
    estado.blocos[1].hash_atual = "f" * 64  # corromper
    resp = client.get("/chain/integridade")
    data = resp.get_json()
    assert data["valida"] is False


# ==================== Transaction endpoints ====================

def test_post_transacao_valida(app_client, transacao_assinada):
    client, estado = app_client
    with patch("node.api.threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        resp = client.post("/transacao", json=transacao_assinada.to_dict())
    assert resp.status_code == 201
    data = resp.get_json()
    assert "tx_hash" in data


def test_post_transacao_invalida_sem_assinatura(app_client, transacao_sem_assinatura):
    client, estado = app_client
    resp = client.post("/transacao", json=transacao_sem_assinatura.to_dict())
    assert resp.status_code == 400


def test_post_transacao_duplicada(app_client, transacao_assinada):
    client, estado = app_client
    # Adicionar a tx diretamente na mempool para simular duplicata
    estado.mempool.adicionar(transacao_assinada)
    with patch("node.api.threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        resp = client.post("/transacao", json=transacao_assinada.to_dict())
    # validar_transacao vai detectar voto pendente na mempool
    # ou mempool.adicionar retorna False
    assert resp.status_code in (200, 400)


def test_post_transacao_assinatura_invalida(app_client, par_chaves):
    client, estado = app_client
    sk, pk = par_chaves
    tx = Transacao(id_votacao="v1", chave_publica=pk, escolha="A", timestamp=1.0)
    tx.assinatura = "ff" * 32
    resp = client.post("/transacao", json=tx.to_dict())
    assert resp.status_code == 400
    assert "assinatura" in resp.get_json()["erro"].lower()


def test_post_transacao_json_ausente(app_client):
    client, estado = app_client
    resp = client.post("/transacao", data="nao e json", content_type="text/plain")
    assert resp.status_code in (400, 415)  # Flask pode retornar 415 Unsupported Media Type


def test_post_transacao_propaga_para_peers(app_client, transacao_assinada):
    client, estado = app_client
    estado.peers.adicionar("localhost:5001")
    with patch("node.api.threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        resp = client.post("/transacao", json=transacao_assinada.to_dict())
    assert resp.status_code == 201
    mock_thread.assert_called_once()
    mock_thread.return_value.start.assert_called_once()


def test_get_mempool(app_client, transacao_assinada):
    client, estado = app_client
    estado.mempool.adicionar(transacao_assinada)
    resp = client.get("/mempool")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] == 1
    assert len(data["pendentes"]) == 1


# ==================== Block endpoints ====================

def test_post_bloco_valido(app_client, transacao_assinada):
    client, estado = app_client
    genesis = estado.blocos[0]
    bloco = minerar_bloco(genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    resp = client.post("/bloco", json=bloco.to_dict())
    assert resp.status_code == 201


def test_post_bloco_invalido(app_client):
    client, estado = app_client
    bloco_falso = {
        "indice": 1, "timestamp": 1.0, "transacoes": [],
        "hash_anterior": "wrong", "nonce": 0, "dificuldade": 1,
        "hash_atual": "a" * 64
    }
    resp = client.post("/bloco", json=bloco_falso)
    assert resp.status_code == 400


def test_post_bloco_gap_dispara_sincronizacao(app_client, transacao_assinada):
    client, estado = app_client
    genesis = estado.blocos[0]
    # Criar bloco com indice 5 (gap grande)
    bloco = minerar_bloco(genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    bloco.indice = 5
    bloco.hash_atual = bloco.gerar_hash()
    with patch("node.api.threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        resp = client.post("/bloco", json=bloco.to_dict())
    assert resp.status_code == 202
    assert "sincronizando" in resp.get_json()["mensagem"].lower()


def test_post_bloco_json_ausente(app_client):
    client, estado = app_client
    resp = client.post("/bloco", data="nao json", content_type="text/plain")
    assert resp.status_code in (400, 415)  # Flask pode retornar 415 Unsupported Media Type


def test_post_bloco_chain_cresce(app_client, transacao_assinada):
    client, estado = app_client
    genesis = estado.blocos[0]
    bloco = minerar_bloco(genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    client.post("/bloco", json=bloco.to_dict())
    resp = client.get("/chain/comprimento")
    assert resp.get_json()["comprimento"] == 2


# ==================== Mining endpoint ====================

def test_post_minerar_com_transacoes(app_client, transacao_assinada):
    client, estado = app_client
    estado.mempool.adicionar(transacao_assinada)
    with patch("node.api.threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        with patch("node.api.minerar_bloco") as mock_minerar:
            genesis = estado.blocos[0]
            bloco_fake = minerar_bloco(genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
            mock_minerar.return_value = bloco_fake
            resp = client.post("/minerar")
    assert resp.status_code == 201
    assert "bloco" in resp.get_json()


def test_post_minerar_sem_transacoes(app_client):
    client, estado = app_client
    resp = client.post("/minerar")
    assert resp.status_code == 400
    assert "pendente" in resp.get_json()["erro"].lower()


def test_post_minerar_remove_txs_da_mempool(app_client, transacao_assinada):
    client, estado = app_client
    estado.mempool.adicionar(transacao_assinada)
    with patch("node.api.threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        with patch("node.api.minerar_bloco") as mock_minerar:
            genesis = estado.blocos[0]
            bloco = minerar_bloco(genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
            mock_minerar.return_value = bloco
            client.post("/minerar")
    assert estado.mempool.tamanho() == 0


# ==================== Peer endpoints ====================

def test_get_peers_vazio(app_client):
    client, estado = app_client
    resp = client.get("/peers")
    assert resp.status_code == 200
    assert resp.get_json()["peers"] == []


def test_post_registrar_peer(app_client):
    client, estado = app_client
    resp = client.post("/peers/registrar", json={"endereco": "peer1:5000"})
    assert resp.status_code == 200
    assert "peer1:5000" in resp.get_json()["peers"]


def test_post_registrar_peer_sem_endereco(app_client):
    client, estado = app_client
    resp = client.post("/peers/registrar", json={"endereco": ""})
    assert resp.status_code == 400


# ==================== Voting endpoints ====================

def test_get_votacoes_vazio(app_client):
    client, estado = app_client
    resp = client.get("/votacoes")
    assert resp.status_code == 200
    assert resp.get_json()["votacoes"] == []


def test_post_votacao_merge(app_client):
    client, estado = app_client
    dados = {
        "id_votacao": "vot1",
        "nome": "Eleicao Teste",
        "opcoes": ["Alice", "Bob"],
        "ativa": True
    }
    resp = client.post("/votacao", json=dados)
    assert resp.status_code == 201


def test_post_votacao_duplicada(app_client):
    client, estado = app_client
    dados = {
        "id_votacao": "vot1",
        "nome": "Eleicao Teste",
        "opcoes": ["Alice", "Bob"],
        "ativa": True
    }
    client.post("/votacao", json=dados)
    resp = client.post("/votacao", json=dados)
    assert resp.status_code == 200
    assert "conhecida" in resp.get_json()["mensagem"].lower()


def test_post_votacao_propagar(app_client):
    client, estado = app_client
    dados = {
        "id_votacao": "vot1",
        "nome": "Eleicao Teste",
        "opcoes": ["Alice", "Bob"],
        "ativa": True
    }
    with patch("node.api.threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        resp = client.post("/votacao/propagar", json=dados)
    assert resp.status_code == 200
    assert "propagacao" in resp.get_json()["mensagem"].lower()


# ==================== Report and info endpoints ====================

def test_get_relatorio_sem_votos(app_client):
    client, estado = app_client
    resp = client.get("/votacao/relatorio/vot1")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["vencedor"] is None
    assert data["total"] == 0


def test_get_no_info(app_client):
    client, estado = app_client
    resp = client.get("/no/info")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "id_no" in data
    assert "porta" in data
    assert "comprimento_chain" in data
    assert "transacoes_pendentes" in data
    assert "peers" in data
    assert data["porta"] == 5000
