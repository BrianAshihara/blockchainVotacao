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
from core.cadeia import criar_bloco_genesis

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
