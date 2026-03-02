"""
Testes para network/sincronizacao.py

Cobre sincronizacao de chain (com recuperacao de txs orfas), registro em peers,
sincronizacao de votacoes e o procedimento de startup de 3 etapas.
Chamadas HTTP mockadas.
"""

from unittest.mock import patch, MagicMock, call
import requests

from network.sincronizacao import (
    sincronizar_chain, registrar_nos_peers, sincronizar_votacoes,
    iniciar_sincronizacao
)
from core.mineracao import minerar_bloco
from core.cadeia import criar_bloco_genesis
from core.cripto import gerar_par_chaves

DIFICULDADE_TESTE = 1


# ==================== sincronizar_chain ====================

def test_sincronizar_chain_sem_peers(estado):
    resultado = sincronizar_chain(estado)
    assert resultado is False


@patch("network.sincronizacao.resolver_conflitos")
def test_sincronizar_chain_local_ja_mais_longa(mock_resolver, estado):
    estado.peers.adicionar("peer:5000")
    mock_resolver.return_value = None
    resultado = sincronizar_chain(estado)
    assert resultado is False


@patch("network.sincronizacao.resolver_conflitos")
def test_sincronizar_chain_substitui_por_mais_longa(mock_resolver, estado, chain_com_dois_blocos):
    estado.peers.adicionar("peer:5000")
    mock_resolver.return_value = chain_com_dois_blocos
    resultado = sincronizar_chain(estado)
    assert resultado is True
    assert estado.comprimento_chain() == 3


@patch("network.sincronizacao.resolver_conflitos")
def test_sincronizar_chain_recupera_txs_orfas(
    mock_resolver, estado, par_chaves, fazer_transacao_assinada
):
    sk, pk = par_chaves
    tx_local = fazer_transacao_assinada(sk, pk, escolha="LocalOnly", timestamp=1.0)

    # Adicionar bloco com tx_local na chain local
    genesis = estado.blocos[0]
    bloco_local = minerar_bloco(genesis, [tx_local], dificuldade=DIFICULDADE_TESTE)
    estado.adicionar_bloco(bloco_local)

    # Chain remota mais longa SEM tx_local
    genesis_novo = criar_bloco_genesis(dificuldade=DIFICULDADE_TESTE)
    sk2, pk2 = gerar_par_chaves()
    tx_remota = fazer_transacao_assinada(sk2, pk2, escolha="Remote", timestamp=2.0)
    b1 = minerar_bloco(genesis_novo, [tx_remota], dificuldade=DIFICULDADE_TESTE)
    b2 = minerar_bloco(b1, [], dificuldade=DIFICULDADE_TESTE)
    remote_chain = [genesis_novo, b1, b2]

    estado.peers.adicionar("peer:5000")
    mock_resolver.return_value = remote_chain
    sincronizar_chain(estado)

    # tx_local deve ter sido recuperada para a mempool
    assert estado.mempool.contem(tx_local.calcular_hash()) is True


@patch("network.sincronizacao.resolver_conflitos")
def test_sincronizar_chain_remove_txs_ja_na_nova_chain(
    mock_resolver, estado, transacao_assinada, chain_com_um_bloco
):
    # Adicionar tx na mempool
    estado.mempool.adicionar(transacao_assinada)
    estado.peers.adicionar("peer:5000")

    # Chain remota ja contem essa tx
    mock_resolver.return_value = chain_com_um_bloco
    sincronizar_chain(estado)

    # tx ja esta na nova chain, deve ter sido removida da mempool
    assert estado.mempool.contem(transacao_assinada.calcular_hash()) is False


# ==================== registrar_nos_peers ====================

@patch("network.sincronizacao.registrar_em_peer")
def test_registrar_nos_peers_chama_todos(mock_registrar, estado):
    estado.peers.adicionar("peer1:5000")
    estado.peers.adicionar("peer2:5001")
    mock_registrar.return_value = True
    registrar_nos_peers(estado, "localhost:5000")
    assert mock_registrar.call_count == 2


@patch("network.sincronizacao.registrar_em_peer")
def test_registrar_nos_peers_sem_peers(mock_registrar, estado):
    registrar_nos_peers(estado, "localhost:5000")
    mock_registrar.assert_not_called()


# ==================== sincronizar_votacoes ====================

def test_sincronizar_votacoes_merge_dados(estado):
    estado.peers.adicionar("peer1:5000")
    votacao_data = {
        "votacoes": [
            {"id_votacao": "v1", "nome": "Teste", "opcoes": ["A", "B"], "ativa": True}
        ]
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = votacao_data

    with patch("network.sincronizacao.requests.get", return_value=mock_resp):
        with patch("sistema.votacao.merge_votacao") as mock_merge:
            mock_merge.return_value = True
            sincronizar_votacoes(estado)
            mock_merge.assert_called_once()


def test_sincronizar_votacoes_sem_peers(estado):
    sincronizar_votacoes(estado)


def test_sincronizar_votacoes_peer_falha(estado):
    estado.peers.adicionar("peer1:5000")
    with patch("network.sincronizacao.requests.get") as mock_get:
        mock_get.side_effect = requests.exceptions.ConnectionError("falha")
        sincronizar_votacoes(estado)
        # Nenhum merge deve ter ocorrido - apenas verificamos que nao levantou excecao


# ==================== iniciar_sincronizacao ====================

@patch("network.sincronizacao.sincronizar_votacoes")
@patch("network.sincronizacao.sincronizar_chain")
@patch("network.sincronizacao.registrar_nos_peers")
def test_iniciar_sincronizacao_executa_tres_etapas(
    mock_registrar, mock_sync_chain, mock_sync_votacoes, estado
):
    iniciar_sincronizacao(estado, "localhost:5000")
    mock_registrar.assert_called_once_with(estado, "localhost:5000")
    mock_sync_chain.assert_called_once_with(estado)
    mock_sync_votacoes.assert_called_once_with(estado)


@patch("network.sincronizacao.resolver_conflitos")
def test_sincronizar_chain_persiste_nova_chain(mock_resolver, tmp_path, chain_com_dois_blocos):
    from node.estado import EstadoNo
    d = str(tmp_path / "persist_test")
    estado = EstadoNo(diretorio_dados=d, porta=5000)
    estado.peers.adicionar("peer:5000")
    mock_resolver.return_value = chain_com_dois_blocos
    sincronizar_chain(estado)

    # Recarregar do disco
    estado2 = EstadoNo(diretorio_dados=d, porta=5000)
    assert estado2.comprimento_chain() == 3
