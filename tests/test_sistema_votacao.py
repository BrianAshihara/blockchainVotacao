"""
Testes para sistema/votacao.py

Cobre CRUD de sessoes de votacao, autorizacao de eleitores,
status de sessao, exportacao dict e logica de merge.
Todos os testes usam tmp_path via parametro `caminho`.
"""

import pytest

from sistema.votacao import (
    criar_votacao, listar_votacoes, obter_nome_votacao, encerrar_votacao,
    autorizar_eleitor, eleitor_autorizado, votacao_ativa, opcoes_disponiveis,
    obter_votacao_dict, obter_todas_votacoes_dict, merge_votacao
)


@pytest.fixture
def caminho_votacoes(tmp_path):
    return str(tmp_path / "votacoes.json")


# ---- criar_votacao ----

def test_criar_votacao(caminho_votacoes):
    resultado = criar_votacao("v1", "Eleicao 2024", ["Alice", "Bob"], caminho=caminho_votacoes)
    assert resultado is True
    lista = listar_votacoes(caminho=caminho_votacoes)
    assert len(lista) == 1
    assert lista[0] == ("v1", "Eleicao 2024")


def test_criar_votacao_duplicada(caminho_votacoes):
    criar_votacao("v1", "Eleicao", ["A", "B"], caminho=caminho_votacoes)
    resultado = criar_votacao("v1", "Outra", ["C", "D"], caminho=caminho_votacoes)
    assert resultado is False


# ---- listar_votacoes ----

def test_listar_votacoes_vazio(caminho_votacoes):
    assert listar_votacoes(caminho=caminho_votacoes) == []


def test_listar_votacoes_todas(caminho_votacoes):
    criar_votacao("v1", "Primeira", ["A"], caminho=caminho_votacoes)
    criar_votacao("v2", "Segunda", ["B"], caminho=caminho_votacoes)
    lista = listar_votacoes(caminho=caminho_votacoes)
    ids = [item[0] for item in lista]
    assert "v1" in ids
    assert "v2" in ids


def test_listar_votacoes_apenas_ativas(caminho_votacoes):
    criar_votacao("v1", "Ativa", ["A"], caminho=caminho_votacoes)
    criar_votacao("v2", "Encerrada", ["B"], caminho=caminho_votacoes)
    encerrar_votacao("v2", caminho=caminho_votacoes)
    lista = listar_votacoes(apenas_ativas=True, caminho=caminho_votacoes)
    ids = [item[0] for item in lista]
    assert "v1" in ids
    assert "v2" not in ids


# ---- encerrar_votacao ----

def test_encerrar_votacao(caminho_votacoes):
    criar_votacao("v1", "Teste", ["A"], caminho=caminho_votacoes)
    resultado = encerrar_votacao("v1", caminho=caminho_votacoes)
    assert resultado is True
    assert votacao_ativa("v1", caminho=caminho_votacoes) is False


def test_encerrar_votacao_inexistente(caminho_votacoes):
    assert encerrar_votacao("nao_existe", caminho=caminho_votacoes) is False


# ---- autorizar_eleitor ----

def test_autorizar_eleitor(caminho_votacoes):
    criar_votacao("v1", "Teste", ["A"], caminho=caminho_votacoes)
    resultado = autorizar_eleitor("v1", "joao", caminho=caminho_votacoes)
    assert resultado is True
    assert eleitor_autorizado("v1", "joao", caminho=caminho_votacoes) is True


def test_autorizar_eleitor_duplicado(caminho_votacoes):
    criar_votacao("v1", "Teste", ["A"], caminho=caminho_votacoes)
    autorizar_eleitor("v1", "joao", caminho=caminho_votacoes)
    resultado = autorizar_eleitor("v1", "joao", caminho=caminho_votacoes)
    assert resultado is False


def test_autorizar_eleitor_votacao_inexistente(caminho_votacoes):
    resultado = autorizar_eleitor("nao_existe", "joao", caminho=caminho_votacoes)
    assert resultado is False


# ---- eleitor_autorizado ----

def test_eleitor_autorizado_nao_autorizado(caminho_votacoes):
    criar_votacao("v1", "Teste", ["A"], caminho=caminho_votacoes)
    assert eleitor_autorizado("v1", "maria", caminho=caminho_votacoes) is False


# ---- votacao_ativa ----

def test_votacao_ativa_sim(caminho_votacoes):
    criar_votacao("v1", "Teste", ["A"], caminho=caminho_votacoes)
    assert votacao_ativa("v1", caminho=caminho_votacoes) is True


def test_votacao_ativa_nao(caminho_votacoes):
    assert votacao_ativa("nao_existe", caminho=caminho_votacoes) is False


# ---- opcoes_disponiveis ----

def test_opcoes_disponiveis(caminho_votacoes):
    criar_votacao("v1", "Teste", ["Alice", "Bob", "Carlos"], caminho=caminho_votacoes)
    opcoes = opcoes_disponiveis("v1", caminho=caminho_votacoes)
    assert opcoes == ["Alice", "Bob", "Carlos"]


def test_opcoes_disponiveis_inexistente(caminho_votacoes):
    assert opcoes_disponiveis("nao_existe", caminho=caminho_votacoes) == []


# ---- obter_votacao_dict ----

def test_obter_votacao_dict(caminho_votacoes):
    criar_votacao("v1", "Eleicao", ["A", "B"], caminho=caminho_votacoes)
    autorizar_eleitor("v1", "joao", caminho=caminho_votacoes)
    d = obter_votacao_dict("v1", caminho=caminho_votacoes)
    assert d is not None
    assert d["id_votacao"] == "v1"
    assert d["nome"] == "Eleicao"
    assert d["opcoes"] == ["A", "B"]
    assert d["ativa"] is True
    assert "eleitores" not in d  # eleitores nao devem ser propagados


def test_obter_votacao_dict_inexistente(caminho_votacoes):
    assert obter_votacao_dict("nao_existe", caminho=caminho_votacoes) is None


# ---- obter_todas_votacoes_dict ----

def test_obter_todas_votacoes_dict(caminho_votacoes):
    criar_votacao("v1", "Primeira", ["A"], caminho=caminho_votacoes)
    criar_votacao("v2", "Segunda", ["B"], caminho=caminho_votacoes)
    resultado = obter_todas_votacoes_dict(caminho=caminho_votacoes)
    assert len(resultado) == 2


# ---- merge_votacao ----

def test_merge_votacao_nova(caminho_votacoes):
    dados = {"id_votacao": "v1", "nome": "Teste", "opcoes": ["A", "B"], "ativa": True}
    resultado = merge_votacao(dados, caminho=caminho_votacoes)
    assert resultado is True
    assert votacao_ativa("v1", caminho=caminho_votacoes) is True


def test_merge_votacao_encerramento(caminho_votacoes):
    criar_votacao("v1", "Teste", ["A", "B"], caminho=caminho_votacoes)
    dados = {"id_votacao": "v1", "nome": "Teste", "opcoes": ["A", "B"], "ativa": False}
    resultado = merge_votacao(dados, caminho=caminho_votacoes)
    assert resultado is True
    assert votacao_ativa("v1", caminho=caminho_votacoes) is False


def test_merge_votacao_ja_conhecida(caminho_votacoes):
    criar_votacao("v1", "Teste", ["A", "B"], caminho=caminho_votacoes)
    dados = {"id_votacao": "v1", "nome": "Teste", "opcoes": ["A", "B"], "ativa": True}
    resultado = merge_votacao(dados, caminho=caminho_votacoes)
    assert resultado is False
