"""
Fixtures compartilhadas para a suite de testes do blockchainVotacao.

Fornece:
- Pares de chaves ECDSA reais (sem mock de criptografia)
- Transacoes assinadas
- Blocos genesis e chains pre-construidas
- Instancias de EstadoNo isoladas via tmp_path
- Factory de test_client Flask
"""

import time
import pytest

from core.cripto import gerar_par_chaves, assinar
from core.transacao import Transacao
from core.bloco import Bloco
from core.cadeia import criar_bloco_genesis
from core.mineracao import minerar_bloco
from core.mempool import Mempool
from node.estado import EstadoNo
from node.api import criar_app


DIFICULDADE_TESTE = 1


# --------------- Pares de chaves ---------------

@pytest.fixture
def par_chaves():
    return gerar_par_chaves()


@pytest.fixture
def par_chaves_secundario():
    return gerar_par_chaves()


@pytest.fixture
def par_chaves_terceiro():
    return gerar_par_chaves()


# --------------- Transacoes ---------------

@pytest.fixture
def transacao_assinada(par_chaves):
    sk, pk = par_chaves
    tx = Transacao(
        id_votacao="vot1",
        chave_publica=pk,
        escolha="Alice",
        timestamp=1000000.0
    )
    tx.assinatura = assinar(sk, tx.dados_para_assinar())
    return tx


@pytest.fixture
def transacao_assinada_secundaria(par_chaves_secundario):
    sk, pk = par_chaves_secundario
    tx = Transacao(
        id_votacao="vot1",
        chave_publica=pk,
        escolha="Bob",
        timestamp=1000001.0
    )
    tx.assinatura = assinar(sk, tx.dados_para_assinar())
    return tx


@pytest.fixture
def transacao_sem_assinatura(par_chaves):
    _, pk = par_chaves
    return Transacao(
        id_votacao="vot1",
        chave_publica=pk,
        escolha="Alice",
        timestamp=1000000.0
    )


@pytest.fixture
def fazer_transacao_assinada():
    def _criar(sk, pk, id_votacao="vot1", escolha="Alice", timestamp=None):
        ts = timestamp or time.time()
        tx = Transacao(
            id_votacao=id_votacao,
            chave_publica=pk,
            escolha=escolha,
            timestamp=ts
        )
        tx.assinatura = assinar(sk, tx.dados_para_assinar())
        return tx
    return _criar


# --------------- Blocos e chains ---------------

@pytest.fixture
def bloco_genesis():
    return criar_bloco_genesis(dificuldade=DIFICULDADE_TESTE)


@pytest.fixture
def chain_com_genesis(bloco_genesis):
    return [bloco_genesis]


@pytest.fixture
def chain_com_um_bloco(bloco_genesis, transacao_assinada):
    bloco_1 = minerar_bloco(bloco_genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    return [bloco_genesis, bloco_1]


@pytest.fixture
def chain_com_dois_blocos(bloco_genesis, transacao_assinada, transacao_assinada_secundaria):
    bloco_1 = minerar_bloco(bloco_genesis, [transacao_assinada], dificuldade=DIFICULDADE_TESTE)
    bloco_2 = minerar_bloco(bloco_1, [transacao_assinada_secundaria], dificuldade=DIFICULDADE_TESTE)
    return [bloco_genesis, bloco_1, bloco_2]


# --------------- Mempool ---------------

@pytest.fixture
def mempool():
    return Mempool()


# --------------- EstadoNo ---------------

@pytest.fixture
def estado(tmp_path):
    return EstadoNo(diretorio_dados=str(tmp_path / "data"), porta=5000)


@pytest.fixture
def estado_factory(tmp_path):
    _counter = [0]

    def _criar(porta=5000):
        _counter[0] += 1
        d = str(tmp_path / f"node_{_counter[0]}")
        return EstadoNo(diretorio_dados=d, porta=porta)
    return _criar


# --------------- Flask test client ---------------

@pytest.fixture
def app_client(estado):
    app = criar_app(estado)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client, estado
