"""
Testes para core/validacao.py

Cobre validacao de transacoes (campos, assinaturas, voto duplo, mempool)
e validacao de blocos (indice, hash chain, PoW, assinaturas de tx).
Modulo critico — testa integracao cruzada com cripto.py.
"""

from core.validacao import (validar_transacao, validar_bloco, validar_conteudo_bloco,
                            validar_votos_do_bloco, validar_votos_da_cadeia)
from core.transacao import Transacao
from core.cripto import gerar_par_chaves, assinar
from core.mineracao import minerar_bloco, verificar_pow
from core.cadeia import criar_bloco_genesis, verificar_integridade
from sistema.votacao import autorizar_eleitor, criar_votacao

DIFICULDADE_TESTE = 1


def _sessao_com_autorizados(tmp_path, chaves):
    caminho = str(tmp_path / "votacoes.json")
    criar_votacao("vot1", "Teste", ["Alice", "Bob"], caminho=caminho)
    for i, chave in enumerate(chaves):
        autorizar_eleitor("vot1", f"eleitor{i}", chave_publica=chave, caminho=caminho)
    return caminho


# validar_transacao

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


# check 6: chave precisa estar autorizada na sessao

def test_validar_transacao_eleitor_autorizado(transacao_assinada, chain_com_genesis, tmp_path):
    caminho = _sessao_com_autorizados(tmp_path, [transacao_assinada.chave_publica])
    valida, msg = validar_transacao(transacao_assinada, chain_com_genesis, [],
                                    caminho_votacoes=caminho)
    assert valida is True
    assert msg == ""


def test_validar_transacao_eleitor_nao_autorizado(transacao_assinada, chain_com_genesis, tmp_path):
    caminho = _sessao_com_autorizados(tmp_path, [])
    valida, msg = validar_transacao(transacao_assinada, chain_com_genesis, [],
                                    caminho_votacoes=caminho)
    assert valida is False
    assert "autorizado" in msg.lower()


def test_validar_transacao_chave_de_outro_eleitor_nao_serve(
    transacao_assinada, par_chaves_secundario, chain_com_genesis, tmp_path
):
    _, pk2 = par_chaves_secundario
    caminho = _sessao_com_autorizados(tmp_path, [pk2])
    valida, msg = validar_transacao(transacao_assinada, chain_com_genesis, [],
                                    caminho_votacoes=caminho)
    assert valida is False
    assert "autorizado" in msg.lower()


# check 7: escolha precisa estar entre as opcoes

def test_validar_transacao_opcao_inexistente(par_chaves, chain_com_genesis, fazer_transacao_assinada, tmp_path):
    sk, pk = par_chaves
    caminho = _sessao_com_autorizados(tmp_path, [pk])
    tx = fazer_transacao_assinada(sk, pk, escolha="Carlos")
    valida, msg = validar_transacao(tx, chain_com_genesis, [], caminho_votacoes=caminho)
    assert valida is False
    assert "opcao" in msg.lower()


# votos dentro de blocos recebidos

def test_votos_do_bloco_validos(bloco_genesis, transacao_assinada, tmp_path):
    caminho = _sessao_com_autorizados(tmp_path, [transacao_assinada.chave_publica])
    bloco = minerar_bloco(bloco_genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    assert validar_votos_do_bloco(bloco, [bloco_genesis], caminho) == (True, "")


def test_votos_do_bloco_votacao_desconhecida(bloco_genesis, transacao_assinada, tmp_path):
    caminho = str(tmp_path / "votacoes.json")
    bloco = minerar_bloco(bloco_genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    valido, msg = validar_votos_do_bloco(bloco, [bloco_genesis], caminho)
    assert valido is False
    assert "desconhecida" in msg


def test_votos_do_bloco_opcao_invalida(bloco_genesis, par_chaves, fazer_transacao_assinada, tmp_path):
    sk, pk = par_chaves
    caminho = _sessao_com_autorizados(tmp_path, [pk])
    bloco = minerar_bloco(bloco_genesis, [fazer_transacao_assinada(sk, pk, escolha="Carlos")],
                          dificuldade=DIFICULDADE_TESTE)
    valido, msg = validar_votos_do_bloco(bloco, [bloco_genesis], caminho)
    assert valido is False
    assert "Opcao invalida" in msg


def test_votos_do_bloco_chave_nao_autorizada(bloco_genesis, transacao_assinada, tmp_path):
    caminho = _sessao_com_autorizados(tmp_path, [])
    bloco = minerar_bloco(bloco_genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    valido, msg = validar_votos_do_bloco(bloco, [bloco_genesis], caminho)
    assert valido is False
    assert "autorizado" in msg


def test_votos_do_bloco_voto_duplo_contra_a_cadeia(
    chain_com_um_bloco, par_chaves, fazer_transacao_assinada, tmp_path
):
    # a chain_com_um_bloco ja tem um voto desta chave em vot1
    sk, pk = par_chaves
    caminho = _sessao_com_autorizados(tmp_path, [pk])
    outro_voto = fazer_transacao_assinada(sk, pk, escolha="Bob", timestamp=5.0)
    bloco = minerar_bloco(chain_com_um_bloco[-1], [outro_voto], dificuldade=DIFICULDADE_TESTE)
    valido, msg = validar_votos_do_bloco(bloco, chain_com_um_bloco, caminho)
    assert valido is False
    assert "Voto duplo" in msg


def test_votos_do_bloco_voto_duplo_no_mesmo_bloco(bloco_genesis, par_chaves, fazer_transacao_assinada, tmp_path):
    sk, pk = par_chaves
    caminho = _sessao_com_autorizados(tmp_path, [pk])
    v1 = fazer_transacao_assinada(sk, pk, escolha="Alice", timestamp=1.0)
    v2 = fazer_transacao_assinada(sk, pk, escolha="Bob", timestamp=2.0)
    bloco = minerar_bloco(bloco_genesis, [v1, v2], dificuldade=DIFICULDADE_TESTE)
    valido, msg = validar_votos_do_bloco(bloco, [bloco_genesis], caminho)
    assert valido is False
    assert "Voto duplo" in msg


def test_votos_da_cadeia_valida(chain_com_dois_blocos, par_chaves, par_chaves_secundario, tmp_path):
    caminho = _sessao_com_autorizados(tmp_path, [par_chaves[1], par_chaves_secundario[1]])
    assert validar_votos_da_cadeia(chain_com_dois_blocos, caminho) == (True, "")


def test_votos_da_cadeia_voto_duplo_entre_blocos(bloco_genesis, par_chaves, fazer_transacao_assinada, tmp_path):
    sk, pk = par_chaves
    caminho = _sessao_com_autorizados(tmp_path, [pk])
    b1 = minerar_bloco(bloco_genesis, [fazer_transacao_assinada(sk, pk, escolha="Alice", timestamp=1.0)],
                       dificuldade=DIFICULDADE_TESTE)
    b2 = minerar_bloco(b1, [fazer_transacao_assinada(sk, pk, escolha="Bob", timestamp=2.0)],
                       dificuldade=DIFICULDADE_TESTE)
    valido, msg = validar_votos_da_cadeia([bloco_genesis, b1, b2], caminho)
    assert valido is False
    assert msg.startswith("Bloco 2")


# dificuldade minima

def test_conteudo_bloco_abaixo_da_dificuldade_minima(bloco_genesis, transacao_assinada, monkeypatch):
    monkeypatch.setattr("core.mineracao.DIFICULDADE_MINIMA", 2)
    bloco = minerar_bloco(bloco_genesis, [transacao_assinada], dificuldade=1)
    valido, msg = validar_conteudo_bloco(bloco)
    assert valido is False
    assert "minimo" in msg


def test_conteudo_bloco_sem_prova_de_trabalho_recusado(bloco_genesis, transacao_assinada):
    # com dificuldade 0 qualquer hash passaria no PoW
    bloco = minerar_bloco(bloco_genesis, [transacao_assinada], dificuldade=0)
    assert validar_conteudo_bloco(bloco)[0] is False


def test_conteudo_bloco_acima_da_minima_aceito(bloco_genesis, transacao_assinada):
    bloco = minerar_bloco(bloco_genesis, [transacao_assinada], dificuldade=2)
    assert validar_conteudo_bloco(bloco) == (True, "")


def test_integridade_recusa_bloco_abaixo_da_minima(bloco_genesis, transacao_assinada, monkeypatch):
    monkeypatch.setattr("core.mineracao.DIFICULDADE_MINIMA", 2)
    chain = [bloco_genesis, minerar_bloco(bloco_genesis, [transacao_assinada], dificuldade=1)]
    assert verificar_integridade(chain) is False


def test_verificar_pow_recusa_abaixo_da_minima(bloco_genesis, monkeypatch):
    monkeypatch.setattr("core.mineracao.DIFICULDADE_MINIMA", 2)
    bloco = minerar_bloco(bloco_genesis, [], dificuldade=1)
    assert verificar_pow(bloco) is False


# validar_bloco

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

# validar_conteudo_bloco (usado antes de ressincronizar)

def test_conteudo_valido_de_bloco_que_nao_encaixa_na_cadeia_local(bloco_genesis, transacao_assinada):
    bloco_1 = minerar_bloco(bloco_genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    bloco_2 = minerar_bloco(bloco_1, [], dificuldade=DIFICULDADE_TESTE)
    valido, msg = validar_conteudo_bloco(bloco_2)
    assert valido is True
    assert msg == ""


def test_conteudo_hash_adulterado(bloco_genesis, transacao_assinada):
    bloco = minerar_bloco(bloco_genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    bloco.hash_atual = "0" * 64
    valido, msg = validar_conteudo_bloco(bloco)
    assert valido is False
    assert "hash" in msg.lower()


def test_conteudo_assinatura_invalida(bloco_genesis, par_chaves):
    _, pk = par_chaves
    tx = Transacao(id_votacao="v1", chave_publica=pk, escolha="A", timestamp=1.0)
    tx.assinatura = "ff" * 32
    bloco = minerar_bloco(bloco_genesis, [tx], dificuldade=DIFICULDADE_TESTE)
    valido, msg = validar_conteudo_bloco(bloco)
    assert valido is False
    assert "assinatura" in msg.lower()
