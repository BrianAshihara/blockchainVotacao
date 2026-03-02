"""
Testes para sistema/autenticacao.py

Cobre hashing de senha, autenticacao (incluindo admin hardcoded),
cadastro de usuarios com geracao de chaves ECDSA e listagem.
Usa monkeypatch para isolar o arquivo usuarios.json.
"""

import pytest

from sistema.autenticacao import (
    hash_senha, autenticar, tipo_usuario, cadastrar_usuario,
    obter_chaves_usuario, listar_eleitores
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

def test_tipo_usuario_admin():
    assert tipo_usuario("admin") == "admin"


def test_tipo_usuario_cadastrado():
    cadastrar_usuario("maria", "1234", "auditor")
    assert tipo_usuario("maria") == "auditor"


# ---- cadastrar_usuario ----

def test_cadastrar_usuario_tipo_invalido():
    with pytest.raises(ValueError):
        cadastrar_usuario("hacker", "1234", "superuser")


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
