"""
Testes para sistema/votacao.py

Cobre CRUD de sessoes de votacao, autorizacao de eleitores,
status de sessao, exportacao dict e logica de merge.
Todos os testes usam tmp_path via parametro `caminho`.
"""

import json
import threading

import pytest

from sistema.votacao import (
    criar_votacao, listar_votacoes, obter_nome_votacao, encerrar_votacao,
    autorizar_eleitor, eleitor_autorizado, votacao_ativa, opcoes_disponiveis,
    obter_votacao_dict, obter_todas_votacoes_dict, merge_votacao,
    chave_autorizada, obter_total_eleitores, votacao_recebida_valida
)
from core.cripto import gerar_par_chaves

CHAVE_A = "aa" * 64
CHAVE_B = "bb" * 64


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


# votacao_recebida_valida

def _votacao_recebida(**campos):
    dados = {"id_votacao": "v1", "nome": "Teste", "opcoes": ["A", "B"], "ativa": True,
             "chaves_autorizadas": [gerar_par_chaves()[1]],
             "inicio": "2026-01-01T10:00:00+00:00", "fim": None}
    dados.update(campos)
    return dados


def test_votacao_recebida_valida():
    assert votacao_recebida_valida(_votacao_recebida()) is True


def test_votacao_recebida_sem_campos_opcionais():
    assert votacao_recebida_valida({"id_votacao": "v1", "nome": "Teste", "opcoes": ["A", "B"], "ativa": True})


@pytest.mark.parametrize("campos", [
    {"id_votacao": "../etc"},
    {"id_votacao": 10},
    {"nome": "  "},
    {"opcoes": ["A"]},
    {"opcoes": ["A", "A"]},
    {"opcoes": ["A", ""]},
    {"opcoes": "A,B"},
    {"ativa": "false"},
    {"chaves_autorizadas": ["nao-e-chave"]},
    {"chaves_autorizadas": [CHAVE_A]},
    {"chaves_autorizadas": "chave"},
    {"inicio": "ontem"},
    {"fim": 123},
])
def test_votacao_recebida_invalida(campos):
    assert votacao_recebida_valida(_votacao_recebida(**campos)) is False


def test_votacao_recebida_nao_e_dict():
    assert votacao_recebida_valida(None) is False
    assert votacao_recebida_valida(["v1"]) is False


# merge_votacao

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


def test_merges_concorrentes_nao_perdem_chaves_nem_corrompem(caminho_votacoes):
    # Rajada de propagacoes como a que corrompeu o votacoes.json do no B
    criar_votacao("v1", "Teste", ["A"], caminho=caminho_votacoes)
    chaves = [f"{i:02x}" * 64 for i in range(40)]

    def receber(chave):
        merge_votacao({"id_votacao": "v1", "nome": "Teste", "opcoes": ["A"], "ativa": True,
                       "chaves_autorizadas": [chave]}, caminho=caminho_votacoes)

    threads = [threading.Thread(target=receber, args=(c,)) for c in chaves]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    with open(caminho_votacoes) as f:
        salvo = json.load(f)
    assert sorted(salvo["v1"]["chaves_autorizadas"]) == sorted(chaves)


# chaves autorizadas (replicadas entre os nos)

def test_autorizar_eleitor_guarda_chave(caminho_votacoes):
    criar_votacao("v1", "Teste", ["A"], caminho=caminho_votacoes)
    autorizar_eleitor("v1", "joao", chave_publica=CHAVE_A, caminho=caminho_votacoes)
    assert chave_autorizada("v1", CHAVE_A, caminho=caminho_votacoes) is True
    assert eleitor_autorizado("v1", "joao", caminho=caminho_votacoes) is True


def test_chave_nao_autorizada(caminho_votacoes):
    criar_votacao("v1", "Teste", ["A"], caminho=caminho_votacoes)
    autorizar_eleitor("v1", "joao", chave_publica=CHAVE_A, caminho=caminho_votacoes)
    assert chave_autorizada("v1", CHAVE_B, caminho=caminho_votacoes) is False


def test_chave_autorizada_votacao_inexistente(caminho_votacoes):
    assert chave_autorizada("nao_existe", CHAVE_A, caminho=caminho_votacoes) is False


def test_autorizar_mesmo_login_com_chave_nova(caminho_votacoes):
    """Login ja autorizado mas chave nova (ex: sessao antiga) ainda altera o registro."""
    criar_votacao("v1", "Teste", ["A"], caminho=caminho_votacoes)
    autorizar_eleitor("v1", "joao", caminho=caminho_votacoes)
    assert autorizar_eleitor("v1", "joao", chave_publica=CHAVE_A, caminho=caminho_votacoes) is True
    assert chave_autorizada("v1", CHAVE_A, caminho=caminho_votacoes) is True


def test_dict_de_propagacao_leva_as_chaves(caminho_votacoes):
    criar_votacao("v1", "Teste", ["A"], caminho=caminho_votacoes)
    autorizar_eleitor("v1", "joao", chave_publica=CHAVE_A, caminho=caminho_votacoes)
    d = obter_votacao_dict("v1", caminho=caminho_votacoes)
    assert d["chaves_autorizadas"] == [CHAVE_A]
    assert "eleitores" not in d


def test_merge_une_chaves_autorizadas(caminho_votacoes):
    """Autorizacao feita em outro no chega por propagacao e passa a valer aqui."""
    criar_votacao("v1", "Teste", ["A"], caminho=caminho_votacoes)
    autorizar_eleitor("v1", "joao", chave_publica=CHAVE_A, caminho=caminho_votacoes)

    dados = {"id_votacao": "v1", "nome": "Teste", "opcoes": ["A"], "ativa": True,
             "chaves_autorizadas": [CHAVE_B]}
    assert merge_votacao(dados, caminho=caminho_votacoes) is True
    assert chave_autorizada("v1", CHAVE_A, caminho=caminho_votacoes) is True
    assert chave_autorizada("v1", CHAVE_B, caminho=caminho_votacoes) is True
    assert merge_votacao(dados, caminho=caminho_votacoes) is False


def test_merge_de_votacao_nova_traz_as_chaves(caminho_votacoes):
    dados = {"id_votacao": "v1", "nome": "Teste", "opcoes": ["A"], "ativa": True,
             "chaves_autorizadas": [CHAVE_A]}
    merge_votacao(dados, caminho=caminho_votacoes)
    assert chave_autorizada("v1", CHAVE_A, caminho=caminho_votacoes) is True
    assert obter_total_eleitores("v1", caminho=caminho_votacoes) == 1


def test_total_eleitores_conta_chaves(caminho_votacoes):
    criar_votacao("v1", "Teste", ["A"], caminho=caminho_votacoes)
    autorizar_eleitor("v1", "joao", chave_publica=CHAVE_A, caminho=caminho_votacoes)
    autorizar_eleitor("v1", "maria", chave_publica=CHAVE_B, caminho=caminho_votacoes)
    assert obter_total_eleitores("v1", caminho=caminho_votacoes) == 2


def test_total_eleitores_sessao_antiga_sem_chaves(caminho_votacoes):
    """Retrocompatibilidade: sessao criada antes das chaves conta pelos logins."""
    criar_votacao("v1", "Teste", ["A"], caminho=caminho_votacoes)
    autorizar_eleitor("v1", "joao", caminho=caminho_votacoes)
    assert obter_total_eleitores("v1", caminho=caminho_votacoes) == 1
