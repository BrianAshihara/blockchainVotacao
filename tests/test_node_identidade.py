"""
Testes para node/identidade.py

Cobre persistencia de identidade do no: criacao nova, carregamento existente,
salvamento, e integridade das chaves ECDSA. Usa tmp_path para isolamento.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from node.identidade import IdentidadeNo, NosConfiaveis, _dados_mensagem, verificar_mensagem
from core.cripto import assinar, gerar_par_chaves, verificar_assinatura


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


# mensagens assinadas entre nos

CONTEUDO = {"id_votacao": "v1", "ativa": False}


def test_mensagem_assinada_valida(tmp_path):
    ident = IdentidadeNo(caminho_arquivo=str(tmp_path / "id.json"))
    mensagem = ident.assinar_mensagem(CONTEUDO)
    assert verificar_mensagem(CONTEUDO, mensagem, [ident.chave_publica]) == (True, "")


def test_mensagem_de_no_nao_confiavel(tmp_path):
    ident = IdentidadeNo(caminho_arquivo=str(tmp_path / "id.json"))
    outro = IdentidadeNo(caminho_arquivo=str(tmp_path / "outro.json"))
    valida, motivo = verificar_mensagem(CONTEUDO, ident.assinar_mensagem(CONTEUDO), [outro.chave_publica])
    assert valida is False
    assert "confiaveis" in motivo


def test_mensagem_com_conteudo_alterado(tmp_path):
    ident = IdentidadeNo(caminho_arquivo=str(tmp_path / "id.json"))
    mensagem = ident.assinar_mensagem(CONTEUDO)
    valida, motivo = verificar_mensagem({"id_votacao": "v1", "ativa": True}, mensagem, [ident.chave_publica])
    assert valida is False
    assert "Assinatura" in motivo


def test_mensagem_com_chave_trocada(tmp_path):
    # assinada por um no, mas declarando a chave de outro que esta na lista
    ident = IdentidadeNo(caminho_arquivo=str(tmp_path / "id.json"))
    confiavel = IdentidadeNo(caminho_arquivo=str(tmp_path / "confiavel.json"))
    mensagem = dict(ident.assinar_mensagem(CONTEUDO), chave_publica=confiavel.chave_publica)
    assert verificar_mensagem(CONTEUDO, mensagem, [confiavel.chave_publica])[0] is False


def test_mensagem_expirada(tmp_path):
    ident = IdentidadeNo(caminho_arquivo=str(tmp_path / "id.json"))
    mensagem = ident.assinar_mensagem(CONTEUDO)
    antigo = (datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat()
    mensagem["timestamp"] = antigo
    mensagem["assinatura"] = assinar(ident.chave_privada, _dados_mensagem(CONTEUDO, antigo))
    valida, motivo = verificar_mensagem(CONTEUDO, mensagem, [ident.chave_publica])
    assert valida is False
    assert "expirado" in motivo


def test_mensagem_timestamp_sem_fuso(tmp_path):
    ident = IdentidadeNo(caminho_arquivo=str(tmp_path / "id.json"))
    mensagem = dict(ident.assinar_mensagem(CONTEUDO), timestamp="2026-01-01T10:00:00")
    assert verificar_mensagem(CONTEUDO, mensagem, [ident.chave_publica]) == (False, "Timestamp invalido")


def test_mensagem_sem_campos_de_assinatura(tmp_path):
    ident = IdentidadeNo(caminho_arquivo=str(tmp_path / "id.json"))
    valida, motivo = verificar_mensagem(CONTEUDO, {}, [ident.chave_publica])
    assert valida is False
    assert "sem assinatura" in motivo


def test_mensagem_assinatura_nao_hex(tmp_path):
    ident = IdentidadeNo(caminho_arquivo=str(tmp_path / "id.json"))
    mensagem = dict(ident.assinar_mensagem(CONTEUDO), assinatura="zz")
    assert verificar_mensagem(CONTEUDO, mensagem, [ident.chave_publica])[0] is False


# lista de nos confiaveis

def test_nos_confiaveis_vazio_inicialmente(tmp_path):
    assert NosConfiaveis(caminho=str(tmp_path / "confiaveis.json")).listar() == []


def test_nos_confiaveis_adicionar_e_persistir(tmp_path):
    caminho = str(tmp_path / "confiaveis.json")
    _, chave = gerar_par_chaves()
    assert NosConfiaveis(caminho=caminho).adicionar(chave.upper()) is True
    assert NosConfiaveis(caminho=caminho).listar() == [chave]


def test_nos_confiaveis_adicionar_duplicada(tmp_path):
    confiaveis = NosConfiaveis(caminho=str(tmp_path / "confiaveis.json"))
    _, chave = gerar_par_chaves()
    confiaveis.adicionar(chave)
    assert confiaveis.adicionar(chave) is False
    assert len(confiaveis.listar()) == 1


def test_nos_confiaveis_recusa_chave_invalida(tmp_path):
    confiaveis = NosConfiaveis(caminho=str(tmp_path / "confiaveis.json"))
    with pytest.raises(ValueError):
        confiaveis.adicionar("abc123")
    assert confiaveis.listar() == []
