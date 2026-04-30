"""
Testes para sistema/autenticacao.py

Cobre hashing de senha, autenticacao (incluindo master hardcoded),
cadastro de usuarios com geracao de chaves ECDSA, auto-registro
de eleitor, promocao de eleitor para admin, listagem de papeis.
Usa monkeypatch para isolar o arquivo usuarios.json.
"""

import pytest

from sistema.autenticacao import (
    hash_senha, autenticar, tipo_usuario, cadastrar_usuario,
    obter_chaves_usuario, listar_eleitores, listar_admins,
    autorregistrar_eleitor, promover_para_admin
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


def test_promocao_e_unidirecional():
    """Apos promocao, nao deve haver caminho de democao via API publica."""
    cadastrar_usuario("up", "1234", "eleitor")
    promover_para_admin("up")
    # Tentar "promover" de novo retorna False (ja e admin)
    assert promover_para_admin("up") is False
    assert tipo_usuario("up") == "admin"


# ---- listar_admins ----

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
