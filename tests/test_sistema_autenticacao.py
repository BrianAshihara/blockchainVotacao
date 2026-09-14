"""
Testes para sistema/autenticacao.py

Cobre hashing de senha, autenticacao (incluindo master hardcoded),
cadastro de usuarios com geracao de chaves ECDSA, auto-registro
de eleitor, promocao de eleitor para admin, listagem de papeis.
Usa monkeypatch para isolar o arquivo usuarios.json.
"""

import pytest

import json

from core.cripto import gerar_par_chaves
from sistema.autenticacao import (
    hash_senha, autenticar, tipo_usuario, cadastrar_usuario,
    obter_chaves_usuario, listar_eleitores, listar_admins,
    autorregistrar_eleitor, promover_para_admin, obter_usuario_publico,
    rebaixar_para_eleitor
)


@pytest.fixture(autouse=True)
def isolar_arquivo_usuarios(tmp_path, monkeypatch):
    caminho = str(tmp_path / "usuarios.json")
    monkeypatch.setattr("sistema.autenticacao.CAMINHO_USUARIOS", caminho)


# ---- hash_senha ----

def test_hash_senha_formato_sha256():
    h = hash_senha("minha_senha")
    assert isinstance(h, str)
    assert len(h) == 64
    int(h, 16)


def test_hash_senha_deterministico():
    assert hash_senha("abc") == hash_senha("abc")


def test_hash_senha_senhas_diferentes():
    assert hash_senha("senha1") != hash_senha("senha2")


# ---- autenticar ----

def test_autenticar_admin_hardcoded():
    assert autenticar("admin", "admin") is True


def test_autenticar_admin_senha_errada():
    assert autenticar("admin", "errada") is False


def test_autenticar_usuario_cadastrado():
    cadastrar_usuario("joao", "1234", "eleitor")
    assert autenticar("joao", "1234") is True


def test_autenticar_usuario_inexistente():
    assert autenticar("fantasma", "x") is False


# ---- tipo_usuario ----

def test_tipo_usuario_master_hardcoded():
    """Login hardcoded 'admin' agora retorna o papel 'master'."""
    assert tipo_usuario("admin") == "master"


def test_tipo_usuario_cadastrado_eleitor():
    cadastrar_usuario("maria", "1234", "eleitor")
    assert tipo_usuario("maria") == "eleitor"


def test_tipo_usuario_cadastrado_admin():
    cadastrar_usuario("clara", "1234", "admin")
    assert tipo_usuario("clara") == "admin"


def test_tipo_usuario_inexistente():
    assert tipo_usuario("ninguem") is None


# ---- cadastrar_usuario ----

def test_cadastrar_usuario_tipo_invalido_superuser():
    with pytest.raises(ValueError):
        cadastrar_usuario("hacker", "1234", "superuser")


def test_cadastrar_usuario_tipo_auditor_rejeitado():
    """O papel 'auditor' foi removido do escopo e nao e mais aceito."""
    with pytest.raises(ValueError):
        cadastrar_usuario("aud", "1234", "auditor")


def test_cadastrar_usuario_duplicado():
    cadastrar_usuario("ana", "1234", "eleitor")
    assert cadastrar_usuario("ana", "5678", "eleitor") is False


# ---- obter_chaves_usuario ----

def test_obter_chaves_usuario_validas():
    cadastrar_usuario("carlos", "1234", "eleitor")
    chaves = obter_chaves_usuario("carlos")
    assert chaves is not None
    sk, pk = chaves
    assert len(sk) == 64   # chave privada SECP256k1
    assert len(pk) == 128  # chave publica SECP256k1


def test_obter_chaves_usuario_inexistente():
    assert obter_chaves_usuario("ninguem") is None


# ---- listar_eleitores ----

def test_listar_eleitores():
    cadastrar_usuario("eleitor1", "1234", "eleitor")
    cadastrar_usuario("eleitor2", "5678", "eleitor")
    cadastrar_usuario("adm", "admin", "admin")
    eleitores = listar_eleitores()
    assert "eleitor1" in eleitores
    assert "eleitor2" in eleitores
    assert "adm" not in eleitores


# ---- autorregistrar_eleitor ----

def test_autorregistrar_eleitor_cria_com_tipo_eleitor():
    assert autorregistrar_eleitor("novo", "senha123") is True
    assert tipo_usuario("novo") == "eleitor"


def test_autorregistrar_eleitor_gera_chaves():
    autorregistrar_eleitor("rafa", "senha")
    chaves = obter_chaves_usuario("rafa")
    assert chaves is not None
    sk, pk = chaves
    assert len(sk) == 64 and len(pk) == 128


def test_autorregistrar_eleitor_duplicado_falha():
    autorregistrar_eleitor("dup", "senha")
    assert autorregistrar_eleitor("dup", "outra") is False


def test_autorregistrar_eleitor_pode_logar():
    autorregistrar_eleitor("logavel", "minhasenha")
    assert autenticar("logavel", "minhasenha") is True


# ---- promover_para_admin ----

def test_promover_eleitor_para_admin():
    cadastrar_usuario("joao", "1234", "eleitor")
    assert promover_para_admin("joao") is True
    assert tipo_usuario("joao") == "admin"


def test_promover_usuario_inexistente_falha():
    assert promover_para_admin("ninguem") is False


def test_promover_admin_existente_falha():
    """Promocao deve ser idempotente para admins existentes (retorna False)."""
    cadastrar_usuario("ja_adm", "1234", "admin")
    assert promover_para_admin("ja_adm") is False


def test_promover_master_e_proibido():
    """O master (login hardcoded 'admin') nao pode ser promovido nem alterado."""
    assert promover_para_admin("admin") is False
    # tipo_usuario continua retornando master
    assert tipo_usuario("admin") == "master"


def test_promover_de_novo_nao_altera():
    cadastrar_usuario("up", "1234", "eleitor")
    promover_para_admin("up")
    # Tentar "promover" de novo retorna False (ja e admin)
    assert promover_para_admin("up") is False
    assert tipo_usuario("up") == "admin"


#  rebaixar para eleitor 

def test_rebaixar_admin_para_eleitor():
    cadastrar_usuario("chefe", "1234", "eleitor")
    promover_para_admin("chefe")
    assert rebaixar_para_eleitor("chefe") is True
    assert tipo_usuario("chefe") == "eleitor"


def test_rebaixar_eleitor_falha():
    cadastrar_usuario("comum", "1234", "eleitor")
    assert rebaixar_para_eleitor("comum") is False
    assert tipo_usuario("comum") == "eleitor"


def test_rebaixar_inexistente_falha():
    assert rebaixar_para_eleitor("ninguem") is False


def test_rebaixar_master_e_proibido():
    assert rebaixar_para_eleitor("admin") is False
    assert tipo_usuario("admin") == "master"


def test_rebaixado_pode_ser_promovido_de_novo():
    cadastrar_usuario("vaivem", "1234", "eleitor")
    promover_para_admin("vaivem")
    rebaixar_para_eleitor("vaivem")
    assert promover_para_admin("vaivem") is True
    assert tipo_usuario("vaivem") == "admin"


# listar admins 

def test_listar_admins_retorna_apenas_admins():
    cadastrar_usuario("e1", "x", "eleitor")
    cadastrar_usuario("a1", "x", "admin")
    cadastrar_usuario("a2", "x", "admin")
    admins = listar_admins()
    assert set(admins) == {"a1", "a2"}
    assert "e1" not in admins


def test_listar_admins_nao_inclui_master():
    """O master e hardcoded e nao deve aparecer em listar_admins (so usuarios cadastrados)."""
    admins = listar_admins()
    assert "admin" not in admins


def test_listar_admins_inclui_promovidos():
    cadastrar_usuario("promov", "x", "eleitor")
    promover_para_admin("promov")
    assert "promov" in listar_admins()


# ---- cadastro com chaves geradas no cliente (frontend) ----

def test_cadastro_com_chave_publica_nao_guarda_chave_privada(tmp_path):
    caminho = str(tmp_path / "usuarios.json")
    _, pk = gerar_par_chaves()
    assert autorregistrar_eleitor("web", "senha123", chave_publica=pk, chave_privada_cifrada="blob", caminho=caminho) is True
    with open(caminho) as f:
        salvo = json.load(f)["web"]
    assert "chave_privada" not in salvo
    assert salvo["chave_publica"] == pk
    assert salvo["chave_privada_cifrada"] == "blob"
    assert salvo["tipo"] == "eleitor"


def test_obter_chaves_usuario_cadastro_web_retorna_none():
    _, pk = gerar_par_chaves()
    autorregistrar_eleitor("web2", "senha123", chave_publica=pk, chave_privada_cifrada="blob")
    assert obter_chaves_usuario("web2") is None


def test_obter_usuario_publico_sem_dados_sensiveis():
    cadastrar_usuario("cli", "1234", "eleitor")
    dados = obter_usuario_publico("cli")
    assert set(dados.keys()) == {"login", "tipo", "chave_publica", "chave_privada_cifrada"}
    assert dados["tipo"] == "eleitor"
    assert len(dados["chave_publica"]) == 128
    assert dados["chave_privada_cifrada"] is None


def test_obter_usuario_publico_master():
    dados = obter_usuario_publico("admin")
    assert dados["tipo"] == "master"
    assert dados["chave_publica"] is None


def test_obter_usuario_publico_inexistente():
    assert obter_usuario_publico("ninguem") is None


def test_funcoes_aceitam_caminho_explicito(tmp_path):
    """O no passa o usuarios.json do seu diretorio de dados."""
    caminho = str(tmp_path / "no_a" / "usuarios.json")
    cadastrar_usuario("ze", "1234", "eleitor", caminho=caminho)
    assert autenticar("ze", "1234", caminho=caminho) is True
    assert tipo_usuario("ze", caminho=caminho) == "eleitor"
    assert listar_eleitores(caminho=caminho) == ["ze"]
    assert promover_para_admin("ze", caminho=caminho) is True
    assert listar_admins(caminho=caminho) == ["ze"]
    # arquivo padrao (isolado pelo fixture) nao foi tocado
    assert tipo_usuario("ze") is None
