"""
Testes para core/validacao.py

Cobre validacao de transacoes (campos, assinaturas, voto duplo, mempool)
e validacao de blocos (indice, hash chain, PoW, assinaturas de tx).
Modulo critico — testa integracao cruzada com cripto.py.
"""

from core.validacao import validar_transacao, validar_bloco
from core.transacao import Transacao
from core.cripto import gerar_par_chaves, assinar
from core.mineracao import minerar_bloco
from core.cadeia import criar_bloco_genesis

DIFICULDADE_TESTE = 1


# ==================== validar_transacao ====================

def test_validar_transacao_valida(transacao_assinada, chain_com_genesis):
    valida, msg = validar_transacao(transacao_assinada, chain_com_genesis, [])
    assert valida is True
    assert msg == ""


def test_validar_transacao_sem_id_votacao(par_chaves, chain_com_genesis):
    sk, pk = par_chaves
    tx = Transacao(id_votacao="", chave_publica=pk, escolha="A", timestamp=1.0)
    tx.assinatura = assinar(sk, tx.dados_para_assinar())
    valida, msg = validar_transacao(tx, chain_com_genesis, [])
    assert valida is False
    assert "ausentes" in msg.lower() or "obrigatorios" in msg.lower()


def test_validar_transacao_sem_chave_publica(chain_com_genesis):
    tx = Transacao(id_votacao="v1", chave_publica="", escolha="A", timestamp=1.0)
    tx.assinatura = "fake_sig"
    valida, msg = validar_transacao(tx, chain_com_genesis, [])
    assert valida is False


def test_validar_transacao_sem_escolha(par_chaves, chain_com_genesis):
    sk, pk = par_chaves
    tx = Transacao(id_votacao="v1", chave_publica=pk, escolha="", timestamp=1.0)
    tx.assinatura = assinar(sk, tx.dados_para_assinar())
    valida, msg = validar_transacao(tx, chain_com_genesis, [])
    assert valida is False


def test_validar_transacao_sem_assinatura(transacao_sem_assinatura, chain_com_genesis):
    valida, msg = validar_transacao(transacao_sem_assinatura, chain_com_genesis, [])
    assert valida is False
    assert "ausentes" in msg.lower() or "obrigatorios" in msg.lower()


def test_validar_transacao_assinatura_invalida(par_chaves, par_chaves_secundario, chain_com_genesis):
    sk, pk = par_chaves
    sk2, pk2 = par_chaves_secundario
    tx = Transacao(id_votacao="v1", chave_publica=pk, escolha="A", timestamp=1.0)
    tx.assinatura = assinar(sk2, tx.dados_para_assinar())  # assinada com chave errada
    valida, msg = validar_transacao(tx, chain_com_genesis, [])
    assert valida is False
    assert "assinatura" in msg.lower()


def test_validar_transacao_assinatura_adulterada(par_chaves, chain_com_genesis):
    sk, pk = par_chaves
    tx = Transacao(id_votacao="v1", chave_publica=pk, escolha="A", timestamp=1.0)
    tx.assinatura = assinar(sk, tx.dados_para_assinar())
    tx.assinatura = "ff" * (len(tx.assinatura) // 2)  # adulterada
    valida, msg = validar_transacao(tx, chain_com_genesis, [])
    assert valida is False


def test_validar_transacao_duplo_voto_na_cadeia(transacao_assinada, chain_com_um_bloco):
    valida, msg = validar_transacao(transacao_assinada, chain_com_um_bloco, [])
    assert valida is False
    assert "cadeia" in msg.lower()


def test_validar_transacao_duplo_voto_na_mempool(par_chaves, chain_com_genesis, fazer_transacao_assinada):
    sk, pk = par_chaves
    tx1 = fazer_transacao_assinada(sk, pk, escolha="A", timestamp=1.0)
    tx2 = fazer_transacao_assinada(sk, pk, escolha="B", timestamp=2.0)
    valida, msg = validar_transacao(tx2, chain_com_genesis, [tx1])
    assert valida is False
    assert "mempool" in msg.lower()


def test_validar_transacao_votacao_diferente_ok(par_chaves, chain_com_um_bloco, fazer_transacao_assinada):
    sk, pk = par_chaves
    tx = fazer_transacao_assinada(sk, pk, id_votacao="vot2", escolha="C", timestamp=2.0)
    valida, msg = validar_transacao(tx, chain_com_um_bloco, [])
    assert valida is True


def test_validar_transacao_outro_eleitor_mesma_votacao_ok(
    par_chaves_secundario, chain_com_um_bloco, fazer_transacao_assinada
):
    sk2, pk2 = par_chaves_secundario
    tx = fazer_transacao_assinada(sk2, pk2, id_votacao="vot1", escolha="B", timestamp=2.0)
    valida, msg = validar_transacao(tx, chain_com_um_bloco, [])
    assert valida is True


# ==================== validar_bloco ====================

def test_validar_bloco_valido(bloco_genesis, transacao_assinada):
    bloco = minerar_bloco(bloco_genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    valido, msg = validar_bloco(bloco, bloco_genesis)
    assert valido is True
    assert msg == ""


def test_validar_bloco_indice_incorreto(bloco_genesis, transacao_assinada):
    bloco = minerar_bloco(bloco_genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    bloco.indice = 99
    valido, msg = validar_bloco(bloco, bloco_genesis)
    assert valido is False
    assert "indice" in msg.lower()


def test_validar_bloco_hash_anterior_errado(bloco_genesis, transacao_assinada):
    bloco = minerar_bloco(bloco_genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    bloco.hash_anterior = "f" * 64
    valido, msg = validar_bloco(bloco, bloco_genesis)
    assert valido is False
    assert "anterior" in msg.lower()


def test_validar_bloco_hash_atual_adulterado(bloco_genesis, transacao_assinada):
    bloco = minerar_bloco(bloco_genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    bloco.hash_atual = "a" * 64
    valido, msg = validar_bloco(bloco, bloco_genesis)
    assert valido is False
    assert "hash" in msg.lower()


def test_validar_bloco_pow_invalido(bloco_genesis, transacao_assinada):
    bloco = minerar_bloco(bloco_genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    # Mudar nonce para invalidar PoW mas recalcular hash
    bloco.nonce = bloco.nonce + 1000000
    bloco.hash_atual = bloco.gerar_hash()
    if bloco.hash_atual.startswith("0"):
        # Caso raro: tentar outro nonce
        bloco.nonce += 1
        bloco.hash_atual = bloco.gerar_hash()
    valido, msg = validar_bloco(bloco, bloco_genesis)
    # Pode falhar por hash_anterior ou PoW dependendo do nonce
    assert valido is False


def test_validar_bloco_transacao_assinatura_invalida(bloco_genesis, par_chaves):
    sk, pk = par_chaves
    tx = Transacao(id_votacao="v1", chave_publica=pk, escolha="A", timestamp=1.0)
    tx.assinatura = "ff" * 32  # assinatura invalida
    bloco = minerar_bloco(bloco_genesis, [tx], dificuldade=DIFICULDADE_TESTE)
    valido, msg = validar_bloco(bloco, bloco_genesis)
    assert valido is False
    assert "assinatura" in msg.lower()


def test_validar_bloco_sem_transacoes(bloco_genesis):
    bloco = minerar_bloco(bloco_genesis, [], dificuldade=DIFICULDADE_TESTE)
    valido, msg = validar_bloco(bloco, bloco_genesis)
    assert valido is True


def test_validar_bloco_multiplas_transacoes_validas(
    bloco_genesis, transacao_assinada, transacao_assinada_secundaria
):
    bloco = minerar_bloco(
        bloco_genesis, [transacao_assinada, transacao_assinada_secundaria],
        dificuldade=DIFICULDADE_TESTE
    )
    valido, msg = validar_bloco(bloco, bloco_genesis)
    assert valido is True


def test_validar_bloco_uma_tx_invalida_entre_varias(
    bloco_genesis, transacao_assinada, par_chaves_secundario
):
    _, pk2 = par_chaves_secundario
    tx_ruim = Transacao(id_votacao="v1", chave_publica=pk2, escolha="B", timestamp=2.0)
    tx_ruim.assinatura = "ff" * 32
    bloco = minerar_bloco(
        bloco_genesis, [transacao_assinada, tx_ruim],
        dificuldade=DIFICULDADE_TESTE
    )
    valido, msg = validar_bloco(bloco, bloco_genesis)
    assert valido is False
