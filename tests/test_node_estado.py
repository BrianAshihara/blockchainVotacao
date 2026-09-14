"""
Testes para node/estado.py

Cobre EstadoNo: inicializacao, persistencia da chain, adicao de blocos,
substituicao de chain e operacoes thread-safe. Usa tmp_path.
"""

import json
import os
import threading

from node.estado import EstadoNo
from core.mineracao import minerar_bloco
from core.cadeia import criar_bloco_genesis, verificar_integridade

DIFICULDADE_TESTE = 1


# ---- Inicializacao ----

def test_init_cria_diretorio(tmp_path):
    d = str(tmp_path / "novo_data")
    EstadoNo(diretorio_dados=d, porta=5000)
    assert os.path.isdir(d)


def test_init_cria_genesis(estado):
    assert estado.blocos[0].indice == 0


def test_init_chain_comprimento_um(estado):
    assert estado.comprimento_chain() == 1


def test_init_mempool_vazia(estado):
    assert estado.mempool.tamanho() == 0


def test_init_identidade_criada(estado):
    assert estado.identidade.id_no != ""


def test_init_peers_vazio(estado):
    assert estado.peers.quantidade() == 0


# ---- adicionar_bloco ----

def test_adicionar_bloco(estado, transacao_assinada):
    genesis = estado.blocos[0]
    bloco = minerar_bloco(genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    estado.adicionar_bloco(bloco)
    assert estado.comprimento_chain() == 2


def test_adicionar_bloco_persiste(tmp_path, transacao_assinada):
    d = str(tmp_path / "data_persist")
    estado1 = EstadoNo(diretorio_dados=d, porta=5000)
    genesis = estado1.blocos[0]
    bloco = minerar_bloco(genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    estado1.adicionar_bloco(bloco)
    # Recarregar
    estado2 = EstadoNo(diretorio_dados=d, porta=5000)
    assert estado2.comprimento_chain() == 2


def test_adicionar_bloco_remove_tx_da_mempool(estado, transacao_assinada):
    estado.mempool.adicionar(transacao_assinada)
    assert estado.mempool.tamanho() == 1
    genesis = estado.blocos[0]
    bloco = minerar_bloco(genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    estado.adicionar_bloco(bloco)
    assert estado.mempool.tamanho() == 0


# ---- substituir_chain ----

def test_substituir_chain(estado, chain_com_dois_blocos):
    estado.substituir_chain(chain_com_dois_blocos)
    assert estado.comprimento_chain() == 3


def test_substituir_chain_persiste(tmp_path, chain_com_dois_blocos):
    d = str(tmp_path / "data_subst")
    estado1 = EstadoNo(diretorio_dados=d, porta=5000)
    estado1.substituir_chain(chain_com_dois_blocos)
    estado2 = EstadoNo(diretorio_dados=d, porta=5000)
    assert estado2.comprimento_chain() == 3


# ---- obter_chain_dict ----

def test_obter_chain_dict(estado):
    chain_dict = estado.obter_chain_dict()
    assert isinstance(chain_dict, list)
    assert len(chain_dict) == 1
    assert "indice" in chain_dict[0]
    assert "hash_atual" in chain_dict[0]


# ---- ultimo_bloco / comprimento_chain ----

def test_ultimo_bloco(estado, transacao_assinada):
    genesis = estado.blocos[0]
    bloco = minerar_bloco(genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    estado.adicionar_bloco(bloco)
    ub = estado.ultimo_bloco()
    assert ub.indice == 1


def test_comprimento_chain(estado):
    assert estado.comprimento_chain() == len(estado.blocos)


# ---- Carregar chain existente ----

def test_carregar_chain_existente(tmp_path):
    d = str(tmp_path / "data_load")
    os.makedirs(d, exist_ok=True)
    genesis = criar_bloco_genesis(dificuldade=DIFICULDADE_TESTE)
    chain_data = [genesis.to_dict()]
    with open(os.path.join(d, "chain.json"), "w") as f:
        json.dump(chain_data, f)
    estado = EstadoNo(diretorio_dados=d, porta=5000)
    assert estado.comprimento_chain() == 1
    assert estado.blocos[0].indice == 0


# ---- Thread safety ----

def test_thread_safety_adicionar_bloco_concorrente(estado, fazer_transacao_assinada):
    from core.cripto import gerar_par_chaves

    blocos_adicionados = []
    erros = []

    def _adicionar(bloco):
        try:
            estado.adicionar_bloco(bloco)
            blocos_adicionados.append(True)
        except Exception as e:
            erros.append(str(e))

    # Criar blocos sequenciais que PODERIAM ser adicionados
    # Na pratica, apenas o primeiro sera valido, mas nao deve corromper estado
    genesis = estado.blocos[0]
    threads = []
    for i in range(5):
        sk, pk = gerar_par_chaves()
        tx = fazer_transacao_assinada(sk, pk, escolha=f"opt_{i}", timestamp=float(i))
        bloco = minerar_bloco(genesis, [tx], dificuldade=DIFICULDADE_TESTE)
        t = threading.Thread(target=_adicionar, args=(bloco,))
        threads.append(t)

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Todos devem ter sido adicionados (sem validacao de indice no adicionar_bloco)
    assert len(erros) == 0
    assert estado.comprimento_chain() == 6  # genesis + 5 blocos
 

def test_adicionar_bloco_se_ponta_aceita_bloco_que_encaixa(estado, transacao_assinada):
    bloco = minerar_bloco(estado.blocos[0], [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    assert estado.adicionar_bloco_se_ponta(bloco) is True
    assert estado.comprimento_chain() == 2


def test_adicionar_bloco_se_ponta_recusa_concorrente_na_mesma_altura(
    estado, transacao_assinada, fazer_transacao_assinada
):
    """Dois blocos minerados sobre a mesma ponta: so o primeiro entra."""
    from core.cripto import gerar_par_chaves

    genesis = estado.blocos[0]
    primeiro = minerar_bloco(genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    sk, pk = gerar_par_chaves()
    concorrente = minerar_bloco(genesis, [fazer_transacao_assinada(sk, pk)], dificuldade=DIFICULDADE_TESTE)

    assert estado.adicionar_bloco_se_ponta(primeiro) is True
    assert estado.adicionar_bloco_se_ponta(concorrente) is False
    assert estado.comprimento_chain() == 2
    assert estado.ultimo_bloco().hash_atual == primeiro.hash_atual


def test_adicionar_bloco_se_ponta_concorrente_entre_threads(estado, fazer_transacao_assinada):
    """Varios blocos disputando a mesma altura ao mesmo tempo: a cadeia continua integra."""
    from core.cripto import gerar_par_chaves

    genesis = estado.blocos[0]
    blocos = []
    for i in range(10):
        sk, pk = gerar_par_chaves()
        blocos.append(minerar_bloco(genesis, [fazer_transacao_assinada(sk, pk, timestamp=float(i + 1))],
                                    dificuldade=DIFICULDADE_TESTE))

    threads = [threading.Thread(target=estado.adicionar_bloco_se_ponta, args=(b,)) for b in blocos]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert estado.comprimento_chain() == 2
    assert verificar_integridade(estado.blocos) is True


# minerar pendentes 

def test_minerar_descarta_bloco_se_a_ponta_mudou(estado, transacao_assinada, fazer_transacao_assinada):
    """Chegou bloco de outro no durante a prova de trabalho: o bloco local ficou velho e e descartado."""
    from unittest.mock import patch
    from core import mineracao
    from core.cripto import gerar_par_chaves

    estado.mempool.adicionar(transacao_assinada)
    sk, pk = gerar_par_chaves()
    bloco_do_peer = minerar_bloco(estado.blocos[0], [fazer_transacao_assinada(sk, pk)], dificuldade=DIFICULDADE_TESTE)
    minerar_real = mineracao.minerar_bloco

    def minerar_enquanto_chega_bloco(anterior, transacoes):
        novo = minerar_real(anterior, transacoes, dificuldade=DIFICULDADE_TESTE)
        estado.adicionar_bloco_se_ponta(bloco_do_peer)
        return novo

    with patch("core.mineracao.minerar_bloco", side_effect=minerar_enquanto_chega_bloco):
        assert estado.minerar_pendentes() is None

    assert estado.comprimento_chain() == 2
    assert estado.ultimo_bloco().hash_atual == bloco_do_peer.hash_atual
    # o voto local continua na mempool para entrar no proximo bloco
    assert estado.mempool.contem(transacao_assinada.calcular_hash()) is True


def test_minerar_descarta_voto_de_quem_ja_votou_na_cadeia(
    estado, par_chaves, transacao_assinada, fazer_transacao_assinada
):
    """Voto que sobrou na mempool depois de uma ressincronizacao nao vira voto duplo."""
    sk, pk = par_chaves
    estado.adicionar_bloco(minerar_bloco(estado.blocos[0], [transacao_assinada], dificuldade=DIFICULDADE_TESTE))
    duplicado = fazer_transacao_assinada(sk, pk, id_votacao="vot1", escolha="Bob", timestamp=5.0)
    estado.mempool.adicionar(duplicado)

    assert estado.minerar_pendentes() is None
    assert estado.mempool.tamanho() == 0
    assert estado.comprimento_chain() == 2
