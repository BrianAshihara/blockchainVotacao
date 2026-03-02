"""
Testes para core/bloco.py

Cobre a classe Bloco: construcao, geracao de hash, serializacao dict,
desserializacao e valores padrao. Usa dificuldade=1 para testes rapidos.
"""

from core.bloco import Bloco
from core.transacao import Transacao


def _tx_simples(escolha="A", timestamp=1.0):
    return Transacao(id_votacao="v1", chave_publica="pk", escolha=escolha, timestamp=timestamp)


# ---- Construtor ----

def test_construtor_atribui_campos():
    tx = _tx_simples()
    b = Bloco(indice=1, timestamp=100.0, transacoes=[tx],
              hash_anterior="a" * 64, nonce=5, dificuldade=2)
    assert b.indice == 1
    assert b.timestamp == 100.0
    assert len(b.transacoes) == 1
    assert b.hash_anterior == "a" * 64
    assert b.nonce == 5
    assert b.dificuldade == 2


def test_construtor_calcula_hash_atual_automaticamente():
    b = Bloco(indice=0, timestamp=0.0, transacoes=[], hash_anterior="0" * 64)
    assert isinstance(b.hash_atual, str)
    assert len(b.hash_atual) == 64


# ---- gerar_hash ----

def test_gerar_hash_formato_sha256():
    b = Bloco(indice=0, timestamp=0.0, transacoes=[], hash_anterior="0" * 64)
    h = b.gerar_hash()
    assert len(h) == 64
    int(h, 16)


def test_gerar_hash_deterministico():
    b = Bloco(indice=0, timestamp=0.0, transacoes=[], hash_anterior="0" * 64)
    assert b.gerar_hash() == b.gerar_hash()


def test_gerar_hash_muda_com_nonce():
    b = Bloco(indice=0, timestamp=0.0, transacoes=[], hash_anterior="0" * 64, nonce=0)
    h1 = b.gerar_hash()
    b.nonce = 999
    h2 = b.gerar_hash()
    assert h1 != h2


def test_gerar_hash_muda_com_transacoes():
    b1 = Bloco(indice=0, timestamp=0.0, transacoes=[], hash_anterior="0" * 64)
    b2 = Bloco(indice=0, timestamp=0.0, transacoes=[_tx_simples()], hash_anterior="0" * 64)
    assert b1.gerar_hash() != b2.gerar_hash()


def test_gerar_hash_muda_com_hash_anterior():
    b1 = Bloco(indice=0, timestamp=0.0, transacoes=[], hash_anterior="0" * 64)
    b2 = Bloco(indice=0, timestamp=0.0, transacoes=[], hash_anterior="a" * 64)
    assert b1.gerar_hash() != b2.gerar_hash()


# ---- to_dict ----

def test_to_dict_contem_todos_campos():
    b = Bloco(indice=0, timestamp=0.0, transacoes=[], hash_anterior="0" * 64)
    d = b.to_dict()
    assert set(d.keys()) == {"indice", "timestamp", "transacoes", "hash_anterior",
                              "nonce", "dificuldade", "hash_atual"}


def test_to_dict_transacoes_como_lista_de_dicts():
    b = Bloco(indice=0, timestamp=0.0, transacoes=[_tx_simples()], hash_anterior="0" * 64)
    d = b.to_dict()
    assert isinstance(d["transacoes"], list)
    assert isinstance(d["transacoes"][0], dict)


# ---- from_dict ----

def test_from_dict_round_trip():
    tx = _tx_simples()
    b = Bloco(indice=1, timestamp=100.0, transacoes=[tx],
              hash_anterior="a" * 64, nonce=42, dificuldade=2)
    b2 = Bloco.from_dict(b.to_dict())
    assert b2.indice == b.indice
    assert b2.timestamp == b.timestamp
    assert b2.hash_anterior == b.hash_anterior
    assert b2.nonce == b.nonce
    assert b2.dificuldade == b.dificuldade
    assert b2.hash_atual == b.hash_atual


def test_from_dict_preserva_hash_atual_original():
    b = Bloco(indice=0, timestamp=0.0, transacoes=[], hash_anterior="0" * 64)
    d = b.to_dict()
    d["hash_atual"] = "custom_" + "f" * 58
    b2 = Bloco.from_dict(d)
    assert b2.hash_atual == d["hash_atual"]


def test_from_dict_transacoes_como_objetos():
    b = Bloco(indice=0, timestamp=0.0, transacoes=[_tx_simples()], hash_anterior="0" * 64)
    b2 = Bloco.from_dict(b.to_dict())
    assert isinstance(b2.transacoes[0], Transacao)


def test_from_dict_nonce_padrao_zero():
    d = {"indice": 0, "timestamp": 0.0, "transacoes": [],
         "hash_anterior": "0" * 64, "dificuldade": 4, "hash_atual": "a" * 64}
    b = Bloco.from_dict(d)
    assert b.nonce == 0


def test_from_dict_dificuldade_padrao_quatro():
    d = {"indice": 0, "timestamp": 0.0, "transacoes": [],
         "hash_anterior": "0" * 64, "nonce": 0, "hash_atual": "a" * 64}
    b = Bloco.from_dict(d)
    assert b.dificuldade == 4


def test_bloco_sem_transacoes():
    b = Bloco(indice=0, timestamp=0.0, transacoes=[], hash_anterior="0" * 64)
    assert len(b.transacoes) == 0
    assert isinstance(b.hash_atual, str)
