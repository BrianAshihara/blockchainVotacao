"""
Testes para node/identidade.py

Cobre persistencia de identidade do no: criacao nova, carregamento existente,
salvamento, e integridade das chaves ECDSA. Usa tmp_path para isolamento.
"""

import json
import uuid

from node.identidade import IdentidadeNo
from core.cripto import assinar, verificar_assinatura


def test_criar_nova_identidade(tmp_path):
    caminho = str(tmp_path / "identity.json")
    ident = IdentidadeNo(caminho_arquivo=caminho)
    assert ident.id_no != ""
    assert ident.chave_privada != ""
    assert ident.chave_publica != ""


def test_id_no_formato_uuid(tmp_path):
    caminho = str(tmp_path / "identity.json")
    ident = IdentidadeNo(caminho_arquivo=caminho)
    parsed = uuid.UUID(ident.id_no)
    assert str(parsed) == ident.id_no


def test_chaves_hex_validos(tmp_path):
    caminho = str(tmp_path / "identity.json")
    ident = IdentidadeNo(caminho_arquivo=caminho)
    int(ident.chave_privada, 16)
    int(ident.chave_publica, 16)


def test_chave_publica_comprimento_secp256k1(tmp_path):
    caminho = str(tmp_path / "identity.json")
    ident = IdentidadeNo(caminho_arquivo=caminho)
    assert len(ident.chave_publica) == 128


def test_chave_privada_comprimento_secp256k1(tmp_path):
    caminho = str(tmp_path / "identity.json")
    ident = IdentidadeNo(caminho_arquivo=caminho)
    assert len(ident.chave_privada) == 64


def test_salvar_cria_arquivo_json(tmp_path):
    caminho = str(tmp_path / "subdir" / "identity.json")
    IdentidadeNo(caminho_arquivo=caminho)
    with open(caminho, "r") as f:
        dados = json.load(f)
    assert "id_no" in dados
    assert "chave_privada" in dados
    assert "chave_publica" in dados


def test_carregar_identidade_existente(tmp_path):
    caminho = str(tmp_path / "identity.json")
    ident1 = IdentidadeNo(caminho_arquivo=caminho)
    ident2 = IdentidadeNo(caminho_arquivo=caminho)
    assert ident2.id_no == ident1.id_no
    assert ident2.chave_privada == ident1.chave_privada
    assert ident2.chave_publica == ident1.chave_publica


def test_persistencia_round_trip(tmp_path):
    caminho = str(tmp_path / "identity.json")
    ident = IdentidadeNo(caminho_arquivo=caminho)
    original_id = ident.id_no
    original_sk = ident.chave_privada
    original_pk = ident.chave_publica
    # Recarregar
    ident2 = IdentidadeNo(caminho_arquivo=caminho)
    assert ident2.id_no == original_id
    assert ident2.chave_privada == original_sk
    assert ident2.chave_publica == original_pk


def test_chaves_funcionais_para_assinatura(tmp_path):
    caminho = str(tmp_path / "identity.json")
    ident = IdentidadeNo(caminho_arquivo=caminho)
    dados = "dados de teste"
    sig = assinar(ident.chave_privada, dados)
    assert verificar_assinatura(ident.chave_publica, dados, sig) is True


def test_duas_instancias_caminhos_diferentes(tmp_path):
    ident1 = IdentidadeNo(caminho_arquivo=str(tmp_path / "id1.json"))
    ident2 = IdentidadeNo(caminho_arquivo=str(tmp_path / "id2.json"))
    assert ident1.id_no != ident2.id_no
