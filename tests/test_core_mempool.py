"""
Testes para core/mempool.py

Cobre operacoes thread-safe da mempool: adicionar, remover, listar,
contem, tamanho, obtencao para mineracao com FIFO.
Inclui testes de thread-safety com threads concorrentes.
"""

import threading

from core.mempool import Mempool
from core.transacao import Transacao
from core.cripto import gerar_par_chaves, assinar


def _tx_rapida(escolha="A", timestamp=1.0):
    """Cria transacao simples (sem assinatura real) para testes de mempool."""
    return Transacao(id_votacao="v1", chave_publica=f"pk_{escolha}",
                     escolha=escolha, timestamp=timestamp)


# ---- Estado inicial ----

def test_mempool_vazia_inicialmente(mempool):
    assert mempool.tamanho() == 0
    assert mempool.listar() == []


# ---- adicionar ----

def test_adicionar_transacao(mempool):
    tx = _tx_rapida()
    assert mempool.adicionar(tx) is True
    assert mempool.tamanho() == 1


def test_adicionar_duplicata_rejeitada(mempool):
    tx = _tx_rapida()
    mempool.adicionar(tx)
    assert mempool.adicionar(tx) is False
    assert mempool.tamanho() == 1


def test_adicionar_transacoes_diferentes(mempool):
    tx1 = _tx_rapida(escolha="A", timestamp=1.0)
    tx2 = _tx_rapida(escolha="B", timestamp=2.0)
    assert mempool.adicionar(tx1) is True
    assert mempool.adicionar(tx2) is True
    assert mempool.tamanho() == 2


# ---- remover ----

def test_remover_transacao_existente(mempool):
    tx = _tx_rapida()
    mempool.adicionar(tx)
    mempool.remover(tx.calcular_hash())
    assert mempool.tamanho() == 0
    assert mempool.contem(tx.calcular_hash()) is False


def test_remover_transacao_inexistente_sem_erro(mempool):
    mempool.remover("hash_inexistente")  # nao deve levantar excecao


def test_remover_varias(mempool):
    tx1 = _tx_rapida(escolha="A", timestamp=1.0)
    tx2 = _tx_rapida(escolha="B", timestamp=2.0)
    tx3 = _tx_rapida(escolha="C", timestamp=3.0)
    mempool.adicionar(tx1)
    mempool.adicionar(tx2)
    mempool.adicionar(tx3)
    mempool.remover_varias([tx1.calcular_hash(), tx2.calcular_hash()])
    assert mempool.tamanho() == 1
    assert mempool.contem(tx3.calcular_hash()) is True


def test_remover_varias_com_hash_inexistente(mempool):
    tx = _tx_rapida()
    mempool.adicionar(tx)
    mempool.remover_varias([tx.calcular_hash(), "hash_fantasma"])
    assert mempool.tamanho() == 0


# ---- listar ----

def test_listar_retorna_copia(mempool):
    tx = _tx_rapida()
    mempool.adicionar(tx)
    lista = mempool.listar()
    lista.clear()
    assert mempool.tamanho() == 1, "listar() deve retornar copia independente"


# ---- contem ----

def test_contem_positivo(mempool):
    tx = _tx_rapida()
    mempool.adicionar(tx)
    assert mempool.contem(tx.calcular_hash()) is True


def test_contem_negativo(mempool):
    assert mempool.contem("hash_qualquer") is False


# ---- tamanho ----

def test_tamanho_apos_operacoes(mempool):
    tx1 = _tx_rapida(escolha="A", timestamp=1.0)
    tx2 = _tx_rapida(escolha="B", timestamp=2.0)
    mempool.adicionar(tx1)
    mempool.adicionar(tx2)
    assert mempool.tamanho() == 2
    mempool.remover(tx1.calcular_hash())
    assert mempool.tamanho() == 1


# ---- obter_para_mineracao ----

def test_obter_para_mineracao_limite(mempool):
    for i in range(15):
        mempool.adicionar(_tx_rapida(escolha=f"opt_{i}", timestamp=float(i)))
    resultado = mempool.obter_para_mineracao(limite=5)
    assert len(resultado) == 5


def test_obter_para_mineracao_fifo(mempool):
    tx_tarde = _tx_rapida(escolha="tarde", timestamp=999.0)
    tx_cedo = _tx_rapida(escolha="cedo", timestamp=1.0)
    mempool.adicionar(tx_tarde)
    mempool.adicionar(tx_cedo)
    resultado = mempool.obter_para_mineracao(limite=10)
    assert resultado[0].timestamp <= resultado[1].timestamp


def test_obter_para_mineracao_mempool_vazia(mempool):
    assert mempool.obter_para_mineracao() == []


def test_obter_para_mineracao_menos_que_limite(mempool):
    tx = _tx_rapida()
    mempool.adicionar(tx)
    resultado = mempool.obter_para_mineracao(limite=10)
    assert len(resultado) == 1


# ---- Thread safety ----

def test_thread_safety_adicionar_concorrente(fazer_transacao_assinada):
    pool = Mempool()
    resultados = []

    def _add(tx):
        resultados.append(pool.adicionar(tx))

    threads = []
    for i in range(50):
        sk, pk = gerar_par_chaves()
        tx = fazer_transacao_assinada(sk, pk, escolha=f"opt_{i}", timestamp=float(i))
        t = threading.Thread(target=_add, args=(tx,))
        threads.append(t)

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert pool.tamanho() == 50
    assert all(resultados)


def test_thread_safety_adicionar_e_remover_concorrente(fazer_transacao_assinada):
    pool = Mempool()
    hashes_para_remover = []

    # Primeiro, adicionar 20 transacoes para depois remover
    for i in range(20):
        sk, pk = gerar_par_chaves()
        tx = fazer_transacao_assinada(sk, pk, escolha=f"rem_{i}", timestamp=float(i))
        pool.adicionar(tx)
        hashes_para_remover.append(tx.calcular_hash())

    # Threads: 20 adicionam novas txs, 20 removem as existentes
    threads = []

    for h in hashes_para_remover:
        t = threading.Thread(target=pool.remover, args=(h,))
        threads.append(t)

    novos_hashes = []
    for i in range(20):
        sk, pk = gerar_par_chaves()
        tx = fazer_transacao_assinada(sk, pk, escolha=f"new_{i}", timestamp=float(100 + i))
        novos_hashes.append(tx.calcular_hash())
        t = threading.Thread(target=pool.adicionar, args=(tx,))
        threads.append(t)

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Todas as removidas devem estar fora, todas as novas devem estar dentro
    for h in hashes_para_remover:
        assert pool.contem(h) is False
    for h in novos_hashes:
        assert pool.contem(h) is True
    assert pool.tamanho() == 20
