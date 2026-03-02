"""
Testes para core/transacao.py

Cobre a classe Transacao: construcao, serializacao canonica,
hashing, round-trip via dict e defaults de timestamp.
"""

import json
import time

from core.transacao import Transacao
from core.cripto import gerar_par_chaves, assinar


# ---- Construtor ----

def test_construtor_campos_obrigatorios():
    tx = Transacao(id_votacao="v1", chave_publica="pk_hex", escolha="Alice")
    assert tx.id_votacao == "v1"
    assert tx.chave_publica == "pk_hex"
    assert tx.escolha == "Alice"


def test_construtor_timestamp_padrao():
    antes = time.time()
    tx = Transacao(id_votacao="v1", chave_publica="pk", escolha="A")
    depois = time.time()
    assert antes <= tx.timestamp <= depois


def test_construtor_timestamp_explicito():
    tx = Transacao(id_votacao="v1", chave_publica="pk", escolha="A", timestamp=12345.0)
    assert tx.timestamp == 12345.0


def test_construtor_assinatura_none_por_padrao():
    tx = Transacao(id_votacao="v1", chave_publica="pk", escolha="A")
    assert tx.assinatura is None


# ---- dados_para_assinar ----

def test_dados_para_assinar_exclui_assinatura():
    tx = Transacao(id_votacao="v1", chave_publica="pk", escolha="A",
                   timestamp=1.0, assinatura="sig_hex")
    dados = tx.dados_para_assinar()
    assert "assinatura" not in dados
    assert "sig_hex" not in dados


def test_dados_para_assinar_formato_json_canonico():
    tx = Transacao(id_votacao="v1", chave_publica="pk", escolha="A", timestamp=1.0)
    dados = tx.dados_para_assinar()
    parsed = json.loads(dados)
    chaves = list(parsed.keys())
    assert chaves == sorted(chaves), "JSON deve usar sort_keys=True"


def test_dados_para_assinar_deterministico():
    tx1 = Transacao(id_votacao="v1", chave_publica="pk", escolha="A", timestamp=1.0)
    tx2 = Transacao(id_votacao="v1", chave_publica="pk", escolha="A", timestamp=1.0)
    assert tx1.dados_para_assinar() == tx2.dados_para_assinar()


def test_dados_para_assinar_diferente_para_campos_distintos():
    tx_base = Transacao(id_votacao="v1", chave_publica="pk", escolha="A", timestamp=1.0)
    tx_diff = Transacao(id_votacao="v2", chave_publica="pk", escolha="A", timestamp=1.0)
    assert tx_base.dados_para_assinar() != tx_diff.dados_para_assinar()


# ---- calcular_hash ----

def test_calcular_hash_formato_sha256():
    tx = Transacao(id_votacao="v1", chave_publica="pk", escolha="A", timestamp=1.0)
    h = tx.calcular_hash()
    assert isinstance(h, str)
    assert len(h) == 64
    int(h, 16)


def test_calcular_hash_deterministico():
    tx = Transacao(id_votacao="v1", chave_publica="pk", escolha="A", timestamp=1.0)
    assert tx.calcular_hash() == tx.calcular_hash()


def test_calcular_hash_diferente_para_transacoes_distintas():
    tx1 = Transacao(id_votacao="v1", chave_publica="pk", escolha="A", timestamp=1.0)
    tx2 = Transacao(id_votacao="v1", chave_publica="pk", escolha="B", timestamp=1.0)
    assert tx1.calcular_hash() != tx2.calcular_hash()


# ---- to_dict / from_dict ----

def test_to_dict_contem_todos_campos():
    tx = Transacao(id_votacao="v1", chave_publica="pk", escolha="A",
                   timestamp=1.0, assinatura="sig")
    d = tx.to_dict()
    assert set(d.keys()) == {"id_votacao", "chave_publica", "escolha",
                              "timestamp", "assinatura", "tx_hash"}


def test_to_dict_tx_hash_consistente():
    tx = Transacao(id_votacao="v1", chave_publica="pk", escolha="A", timestamp=1.0)
    d = tx.to_dict()
    assert d["tx_hash"] == tx.calcular_hash()


def test_from_dict_round_trip():
    tx = Transacao(id_votacao="v1", chave_publica="pk", escolha="A",
                   timestamp=1.0, assinatura="sig")
    tx2 = Transacao.from_dict(tx.to_dict())
    assert tx2.id_votacao == tx.id_votacao
    assert tx2.chave_publica == tx.chave_publica
    assert tx2.escolha == tx.escolha
    assert tx2.timestamp == tx.timestamp
    assert tx2.assinatura == tx.assinatura


def test_from_dict_com_assinatura_real(par_chaves):
    sk, pk = par_chaves
    tx = Transacao(id_votacao="v1", chave_publica=pk, escolha="A", timestamp=1.0)
    tx.assinatura = assinar(sk, tx.dados_para_assinar())
    tx2 = Transacao.from_dict(tx.to_dict())
    assert tx2.assinatura == tx.assinatura
    assert tx2.calcular_hash() == tx.calcular_hash()
