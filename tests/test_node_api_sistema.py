# Testes dos endpoints usados pelo frontend 

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

from core.cripto import gerar_par_chaves
from sistema.autenticacao import cadastrar_usuario, hash_senha
from sistema.votacao import autorizar_eleitor

CHAVE_CIFRADA = '{"versao": 1, "cifra": "abc"}'


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _login(client, login, senha):
    resp = client.post("/usuario/login", json={"login": login, "senha": senha})
    return resp.get_json()["token"]


def _token_master(client):
    return _login(client, "admin", "admin")


def _registrar_eleitor(client, login="eleitor1", senha="senha123"):
    _, pk = gerar_par_chaves()
    resp = client.post("/usuario/autorregistrar", json={
        "login": login, "senha": senha,
        "chave_publica": pk, "chave_privada_cifrada": CHAVE_CIFRADA
    })
    return resp, pk


def _iso(minutos=0):
    data = datetime.now(timezone.utc) + timedelta(minutes=minutos)
    return data.replace(microsecond=0).isoformat()


def _post_sem_propagar(client, caminho, corpo, token):
    with patch("node.api.threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        resp = client.post(caminho, json=corpo, headers=_auth(token))
    return resp, mock_thread


def _criar_votacao(client, token, id_votacao="vot1", **extra):
    corpo = {"id_votacao": id_votacao, "nome": "Eleicao Teste",
             "opcoes": ["Alice", "Bob"], "fim": _iso(60)}
    corpo.update(extra)
    resp, _ = _post_sem_propagar(client, "/votacao/criar", corpo, token)
    return resp


# Login / logout

def test_login_master(app_client):
    client, _ = app_client
    resp = client.post("/usuario/login", json={"login": "admin", "senha": "admin"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["tipo"] == "master"
    assert len(data["token"]) == 64
    assert data["chave_publica"] is None


def test_login_senha_errada(app_client):
    client, _ = app_client
    resp = client.post("/usuario/login", json={"login": "admin", "senha": "errada"})
    assert resp.status_code == 401


def test_login_sem_corpo(app_client):
    client, _ = app_client
    resp = client.post("/usuario/login")
    assert resp.status_code == 401


def test_login_tipo_legado_bloqueado(app_client):
    client, estado = app_client
    with open(estado.caminho_usuarios, "w") as f:
        json.dump({"manel": {"senha": hash_senha("x"), "tipo": "auditor"}}, f)
    resp = client.post("/usuario/login", json={"login": "manel", "senha": "x"})
    assert resp.status_code == 403


def test_login_nao_expoe_senha_nem_chave_privada(app_client):
    client, estado = app_client
    cadastrar_usuario("cli", "senha123", "eleitor", caminho=estado.caminho_usuarios)
    data = client.post("/usuario/login", json={"login": "cli", "senha": "senha123"}).get_json()
    assert "senha" not in data
    assert "chave_privada" not in data
    assert len(data["chave_publica"]) == 128
    assert data["chave_privada_cifrada"] is None


def test_logout_invalida_token(app_client):
    client, _ = app_client
    token = _token_master(client)
    assert client.post("/usuario/logout", headers=_auth(token)).status_code == 200
    assert client.get("/usuarios", headers=_auth(token)).status_code == 401


# Auto-cadastro

def test_autorregistrar_eleitor(app_client):
    client, estado = app_client
    resp, pk = _registrar_eleitor(client)
    assert resp.status_code == 201

    data = client.post("/usuario/login", json={"login": "eleitor1", "senha": "senha123"}).get_json()
    assert data["tipo"] == "eleitor"
    assert data["chave_publica"] == pk
    assert data["chave_privada_cifrada"] == CHAVE_CIFRADA

    with open(estado.caminho_usuarios) as f:
        assert "chave_privada" not in json.load(f)["eleitor1"]


def test_autorregistrar_login_duplicado(app_client):
    client, _ = app_client
    _registrar_eleitor(client)
    resp, _ = _registrar_eleitor(client)
    assert resp.status_code == 409


def test_autorregistrar_login_do_master_reservado(app_client):
    client, _ = app_client
    resp, _ = _registrar_eleitor(client, login="admin")
    assert resp.status_code == 409


def test_autorregistrar_login_invalido(app_client):
    client, _ = app_client
    assert _registrar_eleitor(client, login="a b")[0].status_code == 400
    assert _registrar_eleitor(client, login="registrar")[0].status_code == 400


def test_autorregistrar_senha_curta(app_client):
    client, _ = app_client
    resp, _ = _registrar_eleitor(client, senha="123")
    assert resp.status_code == 400


def test_autorregistrar_chave_publica_invalida(app_client):
    client, _ = app_client
    resp = client.post("/usuario/autorregistrar", json={
        "login": "eleitor1", "senha": "senha123",
        "chave_publica": "ff" * 64, "chave_privada_cifrada": CHAVE_CIFRADA
    })
    assert resp.status_code == 400


def test_autorregistrar_sem_chave_cifrada(app_client):
    client, _ = app_client
    _, pk = gerar_par_chaves()
    resp = client.post("/usuario/autorregistrar", json={
        "login": "eleitor1", "senha": "senha123", "chave_publica": pk
    })
    assert resp.status_code == 400


# Controle de acesso por papel

def test_rota_admin_sem_token(app_client):
    client, _ = app_client
    assert client.get("/usuarios").status_code == 401


def test_rota_admin_token_invalido(app_client):
    client, _ = app_client
    assert client.get("/usuarios", headers=_auth("x" * 64)).status_code == 401


def test_rota_admin_com_token_de_eleitor(app_client):
    client, _ = app_client
    _registrar_eleitor(client)
    token = _login(client, "eleitor1", "senha123")
    assert client.get("/usuarios", headers=_auth(token)).status_code == 403


def test_rota_eleitor_com_token_de_admin(app_client):
    client, _ = app_client
    token = _token_master(client)
    assert client.get("/eleitor/votacoes", headers=_auth(token)).status_code == 403


# Rebaixamento (so o master)

def _admin_promovido(client, login):
    _registrar_eleitor(client, login=login)
    client.post("/usuario/promover", json={"login": login}, headers=_auth(_token_master(client)))
    return _login(client, login, "senha123")


def test_master_rebaixa_admin_e_vale_na_hora(app_client):
    client, _ = app_client
    token_chefe = _admin_promovido(client, "chefe")

    resp = client.post("/usuario/rebaixar", json={"login": "chefe"}, headers=_auth(_token_master(client)))
    assert resp.status_code == 200

    # o mesmo token perde o acesso de admin e ganha o de eleitor
    assert client.get("/usuarios", headers=_auth(token_chefe)).status_code == 403
    assert client.get("/eleitor/votacoes", headers=_auth(token_chefe)).status_code == 200


def test_admin_comum_nao_rebaixa_outro_admin(app_client):
    client, _ = app_client
    _admin_promovido(client, "chefe")
    token_outro = _admin_promovido(client, "outro")

    resp = client.post("/usuario/rebaixar", json={"login": "chefe"}, headers=_auth(token_outro))
    assert resp.status_code == 403


def test_rebaixar_quem_nao_e_admin(app_client):
    client, _ = app_client
    _registrar_eleitor(client)
    token = _token_master(client)
    for login in ("eleitor1", "ninguem", "admin"):
        resp = client.post("/usuario/rebaixar", json={"login": login}, headers=_auth(token))
        assert resp.status_code == 400


def test_rebaixar_sem_token(app_client):
    client, _ = app_client
    assert client.post("/usuario/rebaixar", json={"login": "x"}).status_code == 401


# Usuarios

def test_listar_usuarios(app_client):
    client, estado = app_client
    _registrar_eleitor(client)
    cadastrar_usuario("adm1", "senha123", "admin", caminho=estado.caminho_usuarios)
    data = client.get("/usuarios", headers=_auth(_token_master(client))).get_json()
    assert data["eleitores"] == ["eleitor1"]
    assert data["admins"] == ["adm1"]


def test_promover_eleitor_vale_na_hora(app_client):
    client, _ = app_client
    _registrar_eleitor(client)
    token_eleitor = _login(client, "eleitor1", "senha123")

    resp = client.post("/usuario/promover", json={"login": "eleitor1"},
                       headers=_auth(_token_master(client)))
    assert resp.status_code == 200

    # o papel e relido a cada requisicao, o mesmo token agora e de admin
    assert client.get("/usuarios", headers=_auth(token_eleitor)).status_code == 200
    assert client.get("/eleitor/votacoes", headers=_auth(token_eleitor)).status_code == 403


def test_promover_usuario_inexistente(app_client):
    client, _ = app_client
    resp = client.post("/usuario/promover", json={"login": "ninguem"},
                       headers=_auth(_token_master(client)))
    assert resp.status_code == 400


# Criar votacao

def test_criar_votacao(app_client):
    client, _ = app_client
    resp = _criar_votacao(client, _token_master(client))
    assert resp.status_code == 201
    votacao = resp.get_json()["votacao"]
    assert votacao["id_votacao"] == "vot1"
    assert votacao["opcoes"] == ["Alice", "Bob"]
    assert votacao["ativa"] is True

    ids = [v["id_votacao"] for v in client.get("/votacoes").get_json()["votacoes"]]
    assert "vot1" in ids


def test_criar_votacao_propaga_para_peers(app_client):
    client, _ = app_client
    corpo = {"id_votacao": "vot1", "nome": "X", "opcoes": ["A", "B"]}
    _, mock_thread = _post_sem_propagar(client, "/votacao/criar", corpo, _token_master(client))
    assert mock_thread.called


def test_criar_votacao_sem_fim(app_client):
    client, _ = app_client
    resp = _criar_votacao(client, _token_master(client), fim=None)
    assert resp.status_code == 201
    assert resp.get_json()["votacao"]["fim"] is None


def test_criar_votacao_duplicada(app_client):
    client, _ = app_client
    token = _token_master(client)
    _criar_votacao(client, token)
    assert _criar_votacao(client, token).status_code == 409


def test_criar_votacao_id_invalido(app_client):
    client, _ = app_client
    assert _criar_votacao(client, _token_master(client), id_votacao="vot 1").status_code == 400


def test_criar_votacao_opcoes_invalidas(app_client):
    client, _ = app_client
    token = _token_master(client)
    assert _criar_votacao(client, token, opcoes=["Alice"]).status_code == 400
    assert _criar_votacao(client, token, opcoes=["Alice", "Alice "]).status_code == 400
    assert _criar_votacao(client, token, opcoes=["Alice", ""]).status_code == 400
    assert _criar_votacao(client, token, opcoes="Alice,Bob").status_code == 400


def test_criar_votacao_data_sem_fuso(app_client):
    client, _ = app_client
    resp = _criar_votacao(client, _token_master(client), fim="2030-01-01T10:00:00")
    assert resp.status_code == 400


def test_criar_votacao_fim_antes_do_inicio(app_client):
    client, _ = app_client
    resp = _criar_votacao(client, _token_master(client), inicio=_iso(60), fim=_iso(30))
    assert resp.status_code == 400


def test_criar_votacao_fim_no_passado(app_client):
    client, _ = app_client
    resp = _criar_votacao(client, _token_master(client), inicio=_iso(-60), fim=_iso(-30))
    assert resp.status_code == 400


def test_criar_votacao_converte_datas_para_utc(app_client):
    client, _ = app_client
    resp = _criar_votacao(client, _token_master(client),
                          inicio="2030-01-01T10:00:00-03:00", fim="2030-01-01T18:00:00-03:00")
    votacao = resp.get_json()["votacao"]
    assert votacao["inicio"] == "2030-01-01T13:00:00+00:00"
    assert votacao["fim"] == "2030-01-01T21:00:00+00:00"


# Encerrar votacao

def test_encerrar_votacao(app_client):
    client, _ = app_client
    token = _token_master(client)
    _criar_votacao(client, token)
    resp, _ = _post_sem_propagar(client, "/votacao/encerrar", {"id_votacao": "vot1"}, token)
    assert resp.status_code == 200
    assert resp.get_json()["blocos_minerados"] == []

    votacao = client.get("/votacoes").get_json()["votacoes"][0]
    assert votacao["ativa"] is False


def test_encerrar_votacao_inexistente(app_client):
    client, _ = app_client
    resp, _ = _post_sem_propagar(client, "/votacao/encerrar", {"id_votacao": "nao"}, _token_master(client))
    assert resp.status_code == 404


def test_encerrar_votacao_ja_encerrada(app_client):
    client, _ = app_client
    token = _token_master(client)
    _criar_votacao(client, token)
    _post_sem_propagar(client, "/votacao/encerrar", {"id_votacao": "vot1"}, token)
    resp, _ = _post_sem_propagar(client, "/votacao/encerrar", {"id_votacao": "vot1"}, token)
    assert resp.status_code == 409


def test_encerrar_minera_votos_pendentes(app_client, fazer_transacao_assinada):
    client, estado = app_client
    token = _token_master(client)
    _criar_votacao(client, token)

    sk, pk = gerar_par_chaves()
    autorizar_eleitor("vot1", "eleitor_teste", chave_publica=pk, caminho=estado.caminho_votacoes)
    tx = fazer_transacao_assinada(sk, pk, id_votacao="vot1", escolha="Alice")
    with patch("node.api.threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        assert client.post("/transacao", json=tx.to_dict()).status_code == 201
    assert estado.mempool.tamanho() == 1

    resp, _ = _post_sem_propagar(client, "/votacao/encerrar", {"id_votacao": "vot1"}, token)
    assert resp.get_json()["blocos_minerados"] == [1]
    assert estado.mempool.tamanho() == 0

    assert client.get("/votacao/contagem/vot1").get_json()["total_votos_confirmados"] == 1
    assert client.get("/votacao/relatorio/vot1").get_json()["vencedor"] == "Alice"


# Autorizar eleitor

def test_autorizar_eleitor(app_client):
    client, _ = app_client
    token = _token_master(client)
    _criar_votacao(client, token)
    _registrar_eleitor(client)

    resp = client.post("/votacao/autorizar", json={"id_votacao": "vot1", "login": "eleitor1"},
                       headers=_auth(token))
    assert resp.status_code == 200

    data = client.get("/votacao/vot1/eleitores", headers=_auth(token)).get_json()
    assert data["eleitores"] == ["eleitor1"]


def test_autorizar_eleitor_duplicado(app_client):
    client, _ = app_client
    token = _token_master(client)
    _criar_votacao(client, token)
    _registrar_eleitor(client)
    corpo = {"id_votacao": "vot1", "login": "eleitor1"}
    client.post("/votacao/autorizar", json=corpo, headers=_auth(token))
    resp = client.post("/votacao/autorizar", json=corpo, headers=_auth(token))
    assert resp.status_code == 409


def test_autorizar_login_que_nao_e_eleitor(app_client):
    client, estado = app_client
    token = _token_master(client)
    _criar_votacao(client, token)
    cadastrar_usuario("adm1", "senha123", "admin", caminho=estado.caminho_usuarios)
    for login in ("ninguem", "adm1", "admin"):
        resp = client.post("/votacao/autorizar", json={"id_votacao": "vot1", "login": login},
                           headers=_auth(token))
        assert resp.status_code == 404


def test_autorizar_votacao_inexistente(app_client):
    client, _ = app_client
    _registrar_eleitor(client)
    resp = client.post("/votacao/autorizar", json={"id_votacao": "nao", "login": "eleitor1"},
                       headers=_auth(_token_master(client)))
    assert resp.status_code == 404


def test_autorizar_votacao_encerrada(app_client):
    client, _ = app_client
    token = _token_master(client)
    _criar_votacao(client, token)
    _registrar_eleitor(client)
    _post_sem_propagar(client, "/votacao/encerrar", {"id_votacao": "vot1"}, token)
    resp = client.post("/votacao/autorizar", json={"id_votacao": "vot1", "login": "eleitor1"},
                       headers=_auth(token))
    assert resp.status_code == 409


def test_autorizar_guarda_chave_publica(app_client):
    client, _ = app_client
    token = _token_master(client)
    _criar_votacao(client, token)
    _, pk = _registrar_eleitor(client)
    _post_sem_propagar(client, "/votacao/autorizar", {"id_votacao": "vot1", "login": "eleitor1"}, token)

    votacao = client.get("/votacoes").get_json()["votacoes"][0]
    assert votacao["chaves_autorizadas"] == [pk]


def test_autorizar_eleitor_sem_chave_publica(app_client):
    client, estado = app_client
    token = _token_master(client)
    _criar_votacao(client, token)
    with open(estado.caminho_usuarios, "w") as f:
        json.dump({"antigo": {"senha": hash_senha("x"), "tipo": "eleitor"}}, f)

    resp, _ = _post_sem_propagar(client, "/votacao/autorizar",
                                 {"id_votacao": "vot1", "login": "antigo"}, token)
    assert resp.status_code == 400


def test_voto_exige_chave_autorizada(app_client, fazer_transacao_assinada):
    client, estado = app_client
    token = _token_master(client)
    _criar_votacao(client, token)

    sk, pk = gerar_par_chaves()
    cadastrar_usuario("eleitor_x", "senha123", "eleitor", chave_publica=pk,
                      chave_privada_cifrada=CHAVE_CIFRADA, caminho=estado.caminho_usuarios)
    tx = fazer_transacao_assinada(sk, pk, id_votacao="vot1", escolha="Alice")

    resp = client.post("/transacao", json=tx.to_dict())
    assert resp.status_code == 400
    assert "autorizado" in resp.get_json()["erro"].lower()

    resp, _ = _post_sem_propagar(client, "/votacao/autorizar",
                                 {"id_votacao": "vot1", "login": "eleitor_x"}, token)
    assert resp.status_code == 200

    with patch("node.api.threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        resp = client.post("/transacao", json=tx.to_dict())
    assert resp.status_code == 201


def test_eleitores_de_votacao_inexistente(app_client):
    client, _ = app_client
    resp = client.get("/votacao/nao/eleitores", headers=_auth(_token_master(client)))
    assert resp.status_code == 404


# Votacoes do eleitor

def test_votacoes_do_eleitor(app_client):
    client, _ = app_client
    token = _token_master(client)
    _criar_votacao(client, token, id_votacao="vot1")
    _criar_votacao(client, token, id_votacao="vot2")
    _registrar_eleitor(client)
    client.post("/votacao/autorizar", json={"id_votacao": "vot1", "login": "eleitor1"},
                headers=_auth(token))

    token_eleitor = _login(client, "eleitor1", "senha123")
    votacoes = client.get("/eleitor/votacoes", headers=_auth(token_eleitor)).get_json()["votacoes"]
    assert [v["id_votacao"] for v in votacoes] == ["vot1"]
    assert set(votacoes[0].keys()) == {"id_votacao", "nome", "opcoes", "ativa", "inicio", "fim"}


def test_votacoes_do_eleitor_sem_autorizacao(app_client):
    client, _ = app_client
    _registrar_eleitor(client)
    token = _login(client, "eleitor1", "senha123")
    assert client.get("/eleitor/votacoes", headers=_auth(token)).get_json()["votacoes"] == []


# CORS

def test_cors_em_resposta_comum(app_client):
    client, _ = app_client
    resp = client.get("/chain")
    assert resp.headers["Access-Control-Allow-Origin"] == "*"


def test_cors_preflight(app_client):
    client, _ = app_client
    resp = client.options("/votacao/criar")
    assert resp.status_code == 200
    assert "Authorization" in resp.headers["Access-Control-Allow-Headers"]