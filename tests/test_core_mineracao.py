"""
Testes para core/mineracao.py

Cobre mineracao com proof-of-work e verificacao de PoW.
Todos os testes usam dificuldade=1 para execucao rapida.
"""

from core.mineracao import minerar_bloco, verificar_pow
from core.bloco import Bloco

DIFICULDADE_TESTE = 1


# ---- minerar_bloco ----

def test_minerar_bloco_retorna_bloco(bloco_genesis, transacao_assinada):
    bloco = minerar_bloco(bloco_genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    assert isinstance(bloco, Bloco)


def test_minerar_bloco_indice_correto(bloco_genesis, transacao_assinada):
    bloco = minerar_bloco(bloco_genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    assert bloco.indice == bloco_genesis.indice + 1


def test_minerar_bloco_hash_anterior_correto(bloco_genesis, transacao_assinada):
    bloco = minerar_bloco(bloco_genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    assert bloco.hash_anterior == bloco_genesis.hash_atual


def test_minerar_bloco_pow_valido(bloco_genesis, transacao_assinada):
    bloco = minerar_bloco(bloco_genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    prefixo = "0" * DIFICULDADE_TESTE
    assert bloco.hash_atual.startswith(prefixo)


def test_minerar_bloco_hash_atual_verificavel(bloco_genesis, transacao_assinada):
    bloco = minerar_bloco(bloco_genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    assert bloco.hash_atual == bloco.gerar_hash()


def test_minerar_bloco_contem_transacoes(bloco_genesis, transacao_assinada):
    bloco = minerar_bloco(bloco_genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    assert len(bloco.transacoes) == 1
    assert bloco.transacoes[0].escolha == transacao_assinada.escolha


def test_minerar_bloco_sem_transacoes(bloco_genesis):
    bloco = minerar_bloco(bloco_genesis, [], dificuldade=DIFICULDADE_TESTE)
    assert len(bloco.transacoes) == 0
    assert bloco.hash_atual.startswith("0")


def test_minerar_bloco_dificuldade_diferente(bloco_genesis, transacao_assinada):
    bloco = minerar_bloco(bloco_genesis, [transacao_assinada], dificuldade=2)
    assert bloco.hash_atual.startswith("00")


# ---- verificar_pow ----

def test_verificar_pow_valido(bloco_genesis, transacao_assinada):
    bloco = minerar_bloco(bloco_genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    assert verificar_pow(bloco) is True


def test_verificar_pow_invalido_nonce_adulterado(bloco_genesis, transacao_assinada):
    bloco = minerar_bloco(bloco_genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    bloco.nonce += 999999
    assert verificar_pow(bloco) is False
