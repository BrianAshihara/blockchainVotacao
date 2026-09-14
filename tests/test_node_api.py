"""
Testes para node/api.py

Cobre todos os endpoints Flask via test_client.
Usa unittest.mock.patch para threads de propagacao (previne HTTP real).
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

from node.identidade import IdentidadeNo, verificar_mensagem
from core.transacao import Transacao
from core.bloco import Bloco
from core.cripto import gerar_par_chaves, assinar
from core.mineracao import minerar_bloco
from core.cadeia import criar_bloco_genesis
from sistema.votacao import autorizar_eleitor, criar_votacao, encerrar_votacao

DIFICULDADE_TESTE = 1


def _criar_votacao_ativa(estado, chave_publica=None, id_votacao="vot1", nome="Eleicao Teste"):
    """Helper: cria sessao ativa (e autoriza a chave) para validar_transacao aceitar o voto."""
    criar_votacao(id_votacao, nome, ["Alice", "Bob"], caminho=estado.caminho_votacoes)
    if chave_publica:
        autorizar_eleitor(id_votacao, "eleitor_teste", chave_publica=chave_publica,
                          caminho=estado.caminho_votacoes)


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
    _criar_votacao_ativa(estado, transacao_assinada.chave_publica)
    with patch("node.api.threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        resp = client.post("/transacao", json=transacao_assinada.to_dict())
    assert resp.status_code == 201
    data = resp.get_json()
    assert "tx_hash" in data


def test_post_transacao_rejeita_sessao_inexistente(app_client, transacao_assinada):
    """Check #5: votacao deve estar ativa. Sem sessao em votacoes.json, rejeita."""
    client, estado = app_client
    resp = client.post("/transacao", json=transacao_assinada.to_dict())
    assert resp.status_code == 400
    assert "ativa" in resp.get_json()["erro"].lower() or "periodo" in resp.get_json()["erro"].lower()


def test_post_transacao_rejeita_sessao_encerrada(app_client, transacao_assinada):
    """Voto em sessao encerrada deve ser rejeitado pela validacao temporal."""
    client, estado = app_client
    _criar_votacao_ativa(estado)
    encerrar_votacao("vot1", caminho=estado.caminho_votacoes)
    resp = client.post("/transacao", json=transacao_assinada.to_dict())
    assert resp.status_code == 400


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
    _criar_votacao_ativa(estado, transacao_assinada.chave_publica)
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


# Block endpoints

def test_post_bloco_valido(app_client, transacao_assinada):
    client, estado = app_client
    _criar_votacao_ativa(estado, transacao_assinada.chave_publica)
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
    # bloco valido de uma cadeia 5 blocos a frente; o conteudo precisa ser valido
    # (hash e PoW), senao o no nao aceita ressincronizar por causa dele
    anterior = Bloco(indice=4, timestamp=1.0, transacoes=[], hash_anterior="f" * 64, dificuldade=DIFICULDADE_TESTE)
    bloco = minerar_bloco(anterior, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    with patch("node.api.threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        resp = client.post("/bloco", json=bloco.to_dict())
    assert resp.status_code == 202
    assert "sincronizando" in resp.get_json()["mensagem"].lower()


def test_post_bloco_de_outro_ramo_dispara_sincronizacao(app_client, transacao_assinada, fazer_transacao_assinada):
    # Bifurcacao: o peer esta num ramo mais longo; o no ressincroniza em vez de so recusar.
    client, estado = app_client
    genesis = estado.blocos[0]
    sk, pk = gerar_par_chaves()
    estado.adicionar_bloco(minerar_bloco(genesis, [fazer_transacao_assinada(sk, pk)], dificuldade=DIFICULDADE_TESTE))

    ramo_peer_1 = minerar_bloco(genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    ramo_peer_2 = minerar_bloco(ramo_peer_1, [], dificuldade=DIFICULDADE_TESTE)
    with patch("node.api.threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        resp = client.post("/bloco", json=ramo_peer_2.to_dict())
    assert resp.status_code == 202
    mock_thread.assert_called_once()


def test_post_bloco_concorrente_na_mesma_altura_mantem_o_primeiro(
    app_client, transacao_assinada, fazer_transacao_assinada
):
    client, estado = app_client
    genesis = estado.blocos[0]
    sk, pk = gerar_par_chaves()
    local = minerar_bloco(genesis, [fazer_transacao_assinada(sk, pk)], dificuldade=DIFICULDADE_TESTE)
    estado.adicionar_bloco(local)

    concorrente = minerar_bloco(genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    with patch("node.api.threading.Thread") as mock_thread:
        resp = client.post("/bloco", json=concorrente.to_dict())
    assert resp.status_code == 400
    mock_thread.assert_not_called()
    assert estado.ultimo_bloco().hash_atual == local.hash_atual


def test_post_bloco_invalido_nao_dispara_sincronizacao(app_client, transacao_assinada):
    # Um peer nao pode forcar o download da cadeia mandando bloco com hash falso.
    client, estado = app_client
    anterior = Bloco(indice=4, timestamp=1.0, transacoes=[], hash_anterior="f" * 64, dificuldade=DIFICULDADE_TESTE)
    bloco = minerar_bloco(anterior, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    bloco.hash_atual = "0" * 64
    with patch("node.api.threading.Thread") as mock_thread:
        resp = client.post("/bloco", json=bloco.to_dict())
    assert resp.status_code == 400
    mock_thread.assert_not_called()


def test_post_bloco_json_ausente(app_client):
    client, estado = app_client
    resp = client.post("/bloco", data="nao json", content_type="text/plain")
    assert resp.status_code in (400, 415)  # Flask pode retornar 415 Unsupported Media Type


def test_post_bloco_chain_cresce(app_client, transacao_assinada):
    client, estado = app_client
    _criar_votacao_ativa(estado, transacao_assinada.chave_publica)
    genesis = estado.blocos[0]
    bloco = minerar_bloco(genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    client.post("/bloco", json=bloco.to_dict())
    resp = client.get("/chain/comprimento")
    assert resp.get_json()["comprimento"] == 2


def test_post_bloco_com_voto_nao_autorizado_recusado_e_ressincroniza(app_client, transacao_assinada):
    # Recusa o bloco e atualiza as sessoes, caso a autorizacao ainda nao tenha chegado neste no.
    client, estado = app_client
    _criar_votacao_ativa(estado)  # sessao existe, mas a chave nao foi autorizada
    bloco = minerar_bloco(estado.blocos[0], [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    with patch("node.api.threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        resp = client.post("/bloco", json=bloco.to_dict())
    assert resp.status_code == 400
    assert "autorizado" in resp.get_json()["erro"].lower()
    mock_thread.assert_called_once()
    assert estado.comprimento_chain() == 1


def test_post_bloco_com_opcao_inexistente_recusado(app_client, par_chaves, fazer_transacao_assinada):
    client, estado = app_client
    sk, pk = par_chaves
    _criar_votacao_ativa(estado, pk)
    voto = fazer_transacao_assinada(sk, pk, escolha="Carlos")
    bloco = minerar_bloco(estado.blocos[0], [voto], dificuldade=DIFICULDADE_TESTE)
    with patch("node.api.threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        resp = client.post("/bloco", json=bloco.to_dict())
    assert resp.status_code == 400
    assert "opcao" in resp.get_json()["erro"].lower()
    assert estado.comprimento_chain() == 1


def test_post_transacao_opcao_inexistente(app_client, par_chaves, fazer_transacao_assinada):
    client, estado = app_client
    sk, pk = par_chaves
    _criar_votacao_ativa(estado, pk)
    voto = fazer_transacao_assinada(sk, pk, escolha="Carlos")
    resp = client.post("/transacao", json=voto.to_dict())
    assert resp.status_code == 400
    assert "opcao" in resp.get_json()["erro"].lower()


# Mining endpoint

def test_post_minerar_com_transacoes(app_client, transacao_assinada):
    client, estado = app_client
    estado.mempool.adicionar(transacao_assinada)
    # /minerar usa estado.minerar_pendentes() que importa core.mineracao.minerar_bloco
    # internamente. Mockamos esse import para retornar um bloco com dificuldade=1.
    genesis = estado.blocos[0]
    bloco_fake = minerar_bloco(genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    with patch("node.api.threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        with patch("core.mineracao.minerar_bloco", return_value=bloco_fake):
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
    genesis = estado.blocos[0]
    bloco = minerar_bloco(genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    with patch("node.api.threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        with patch("core.mineracao.minerar_bloco", return_value=bloco):
            client.post("/minerar")
    assert estado.mempool.tamanho() == 0


def test_post_minerar_concorrente_retorna_409(app_client, transacao_assinada):
    """Quando _mining_lock ja esta segurado, /minerar retorna 409."""
    client, estado = app_client
    estado.mempool.adicionar(transacao_assinada)
    # Segurar o lock para simular mineracao em andamento
    assert estado._mining_lock.acquire(blocking=False) is True
    try:
        resp = client.post("/minerar")
        assert resp.status_code == 409
        assert "andamento" in resp.get_json()["erro"].lower()
    finally:
        estado._mining_lock.release()


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


VOTACAO_PEER = {
    "id_votacao": "vot1",
    "nome": "Eleicao Teste",
    "opcoes": ["Alice", "Bob"],
    "ativa": True
}


def _no_confiavel(estado, tmp_path, nome="peer.json"):
    identidade = IdentidadeNo(caminho_arquivo=str(tmp_path / nome))
    estado.nos_confiaveis.adicionar(identidade.chave_publica)
    return identidade


def _mensagem_votacao(identidade, votacao):
    return {"votacao": votacao, **identidade.assinar_mensagem(votacao)}


def test_post_votacao_merge(app_client, tmp_path):
    client, estado = app_client
    peer = _no_confiavel(estado, tmp_path)
    resp = client.post("/votacao", json=_mensagem_votacao(peer, VOTACAO_PEER))
    assert resp.status_code == 201


def test_post_votacao_duplicada(app_client, tmp_path):
    client, estado = app_client
    peer = _no_confiavel(estado, tmp_path)
    client.post("/votacao", json=_mensagem_votacao(peer, VOTACAO_PEER))
    resp = client.post("/votacao", json=_mensagem_votacao(peer, VOTACAO_PEER))
    assert resp.status_code == 200
    assert "conhecida" in resp.get_json()["mensagem"].lower()


def test_post_votacao_sem_assinatura_recusada(app_client):
    # o ataque antigo: qualquer um encerrava a votacao mandando ativa=false
    client, estado = app_client
    criar_votacao("vot1", "Eleicao Teste", ["Alice", "Bob"], caminho=estado.caminho_votacoes)
    resp = client.post("/votacao", json=dict(VOTACAO_PEER, ativa=False))
    assert resp.status_code == 401
    assert client.get("/votacoes").get_json()["votacoes"][0]["ativa"] is True


def test_post_votacao_de_no_fora_da_lista_recusada(app_client, tmp_path):
    client, estado = app_client
    intruso = IdentidadeNo(caminho_arquivo=str(tmp_path / "intruso.json"))
    resp = client.post("/votacao", json=_mensagem_votacao(intruso, VOTACAO_PEER))
    assert resp.status_code == 401
    assert "confiaveis" in resp.get_json()["erro"]
    assert client.get("/votacoes").get_json()["votacoes"] == []


def test_post_votacao_alterada_depois_de_assinada(app_client, tmp_path):
    client, estado = app_client
    peer = _no_confiavel(estado, tmp_path)
    mensagem = _mensagem_votacao(peer, VOTACAO_PEER)
    mensagem["votacao"] = dict(VOTACAO_PEER, chaves_autorizadas=[gerar_par_chaves()[1]])
    resp = client.post("/votacao", json=mensagem)
    assert resp.status_code == 401
    assert "Assinatura" in resp.get_json()["erro"]


def test_post_votacao_mensagem_antiga_recusada(app_client, tmp_path):
    client, estado = app_client
    peer = _no_confiavel(estado, tmp_path)
    antes = datetime.now(timezone.utc) - timedelta(minutes=10)
    with patch("node.identidade.datetime") as mock_datetime:
        mock_datetime.now.return_value = antes
        mensagem = _mensagem_votacao(peer, VOTACAO_PEER)
    resp = client.post("/votacao", json=mensagem)
    assert resp.status_code == 401
    assert "expirado" in resp.get_json()["erro"].lower()


def test_post_votacao_assinatura_malformada(app_client, tmp_path):
    client, estado = app_client
    peer = _no_confiavel(estado, tmp_path)
    mensagem = _mensagem_votacao(peer, VOTACAO_PEER)
    mensagem["assinatura"] = "nao-e-hex"
    assert client.post("/votacao", json=mensagem).status_code == 401


def test_post_votacao_dados_invalidos_de_no_confiavel(app_client, tmp_path):
    client, estado = app_client
    peer = _no_confiavel(estado, tmp_path)
    invalida = dict(VOTACAO_PEER, opcoes=["Alice"])
    resp = client.post("/votacao", json=_mensagem_votacao(peer, invalida))
    assert resp.status_code == 400
    assert client.get("/votacoes").get_json()["votacoes"] == []


def test_get_votacoes_assinado_pelo_no(app_client):
    client, estado = app_client
    criar_votacao("vot1", "Eleicao Teste", ["Alice", "Bob"], caminho=estado.caminho_votacoes)
    dados = client.get("/votacoes").get_json()
    assert dados["chave_publica"] == estado.identidade.chave_publica
    assert verificar_mensagem(dados["votacoes"], dados, [estado.identidade.chave_publica]) == (True, "")


def test_post_votacao_propagar_rele_sessao_do_disco(app_client):
    client, estado = app_client
    criar_votacao("vot1", "Eleicao Teste", ["Alice", "Bob"], caminho=estado.caminho_votacoes)
    with patch("node.api.threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        # campos extras no corpo sao ignorados: vale o que esta gravado no no
        resp = client.post("/votacao/propagar", json={"id_votacao": "vot1", "ativa": False})
    assert resp.status_code == 200
    assert "propagacao" in resp.get_json()["mensagem"].lower()
    votacao_enviada, _, _, identidade, _ = mock_thread.call_args.kwargs["args"]
    assert votacao_enviada["ativa"] is True
    assert identidade is estado.identidade


def test_post_votacao_propagar_inexistente(app_client):
    client, estado = app_client
    with patch("node.api.threading.Thread") as mock_thread:
        resp = client.post("/votacao/propagar", json={"id_votacao": "nao_existe"})
    assert resp.status_code == 404
    mock_thread.assert_not_called()


def test_post_votacao_propagar_de_outra_maquina_recusado(app_client):
    client, estado = app_client
    criar_votacao("vot1", "Eleicao Teste", ["Alice", "Bob"], caminho=estado.caminho_votacoes)
    with patch("node.api.threading.Thread") as mock_thread:
        resp = client.post("/votacao/propagar", json={"id_votacao": "vot1"},
                           environ_base={"REMOTE_ADDR": "192.168.1.50"})
    assert resp.status_code == 403
    mock_thread.assert_not_called()


# ==================== Report and info endpoints ====================

def test_get_relatorio_sessao_inexistente(app_client):
    """Sessao nao existe localmente: votacao_ativa() retorna False, vai para o relatorio completo (vazio)."""
    client, estado = app_client
    resp = client.get("/votacao/relatorio/vot1")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["vencedor"] is None
    assert data["total"] == 0


def test_get_relatorio_sessao_ativa_retorna_slim(app_client, transacao_assinada):
    """Sessao ativa: relatorio retorna payload slim (sem breakdown)."""
    client, estado = app_client
    _criar_votacao_ativa(estado)
    # Adicionar tx confirmada na chain
    genesis = estado.blocos[0]
    bloco = minerar_bloco(genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    estado.adicionar_bloco(bloco)

    resp = client.get("/votacao/relatorio/vot1")
    assert resp.status_code == 200
    data = resp.get_json()
    # Campos slim
    assert data["ativa"] is True
    assert data["total_votos_confirmados"] == 1
    assert data["nome"] == "Eleicao Teste"
    # Campos do relatorio completo NAO devem estar presentes
    assert "detalhes" not in data
    assert "vencedor" not in data
    assert "blocos_com_votos" not in data


def test_get_relatorio_sessao_encerrada_retorna_completo(app_client, transacao_assinada):
    """Sessao encerrada: relatorio retorna payload completo com breakdown."""
    client, estado = app_client
    _criar_votacao_ativa(estado)
    genesis = estado.blocos[0]
    bloco = minerar_bloco(genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    estado.adicionar_bloco(bloco)
    encerrar_votacao("vot1", caminho=estado.caminho_votacoes)

    resp = client.get("/votacao/relatorio/vot1")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total_votos_confirmados"] == 1
    assert data["vencedor"] == "Alice"
    assert "detalhes" in data
    assert data["detalhes"]["Alice"]["votos"] == 1
    assert data["detalhes"]["Alice"]["percentual"] == 100.0
    assert data["blocos_com_votos"] == 1


def test_get_votacao_contagem_zero(app_client):
    client, estado = app_client
    resp = client.get("/votacao/contagem/vot1")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id_votacao"] == "vot1"
    assert data["total_votos_confirmados"] == 0


def test_get_votacao_contagem_com_votos(app_client, transacao_assinada):
    client, estado = app_client
    genesis = estado.blocos[0]
    bloco = minerar_bloco(genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    estado.adicionar_bloco(bloco)
    resp = client.get("/votacao/contagem/vot1")
    assert resp.status_code == 200
    assert resp.get_json()["total_votos_confirmados"] == 1


def test_get_votacao_contagem_apenas_chain_nao_mempool(app_client, transacao_assinada):
    """Votos na mempool nao devem ser contados — apenas on-chain."""
    client, estado = app_client
    estado.mempool.adicionar(transacao_assinada)
    resp = client.get("/votacao/contagem/vot1")
    assert resp.get_json()["total_votos_confirmados"] == 0


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
