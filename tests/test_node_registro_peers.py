"""
Testes para node/registro_peers.py

Cobre registro de peers com thread-safety, persistencia, adicionar/remover/listar.
Usa tmp_path para isolamento de arquivo.
"""

import threading

from node.registro_peers import RegistroPeers


def test_registro_vazio_inicialmente(tmp_path):
    reg = RegistroPeers(caminho=str(tmp_path / "peers.json"))
    assert reg.quantidade() == 0
    assert reg.listar() == []


def test_adicionar_peer_novo(tmp_path):
    reg = RegistroPeers(caminho=str(tmp_path / "peers.json"))
    assert reg.adicionar("localhost:5001") is True
    assert "localhost:5001" in reg.listar()


def test_adicionar_peer_duplicado(tmp_path):
    reg = RegistroPeers(caminho=str(tmp_path / "peers.json"))
    reg.adicionar("localhost:5001")
    assert reg.adicionar("localhost:5001") is False


def test_adicionar_multiplos_peers(tmp_path):
    reg = RegistroPeers(caminho=str(tmp_path / "peers.json"))
    reg.adicionar("peer1:5000")
    reg.adicionar("peer2:5001")
    reg.adicionar("peer3:5002")
    assert reg.quantidade() == 3


def test_remover_peer_existente(tmp_path):
    reg = RegistroPeers(caminho=str(tmp_path / "peers.json"))
    reg.adicionar("peer1:5000")
    reg.remover("peer1:5000")
    assert "peer1:5000" not in reg.listar()
    assert reg.quantidade() == 0


def test_remover_peer_inexistente_sem_erro(tmp_path):
    reg = RegistroPeers(caminho=str(tmp_path / "peers.json"))
    reg.remover("fantasma:9999")  # nao deve levantar excecao


def test_persistencia_apos_adicionar(tmp_path):
    caminho = str(tmp_path / "peers.json")
    reg1 = RegistroPeers(caminho=caminho)
    reg1.adicionar("peer1:5000")
    reg2 = RegistroPeers(caminho=caminho)
    assert "peer1:5000" in reg2.listar()


def test_persistencia_apos_remover(tmp_path):
    caminho = str(tmp_path / "peers.json")
    reg1 = RegistroPeers(caminho=caminho)
    reg1.adicionar("peer1:5000")
    reg1.adicionar("peer2:5001")
    reg1.remover("peer1:5000")
    reg2 = RegistroPeers(caminho=caminho)
    assert "peer1:5000" not in reg2.listar()
    assert "peer2:5001" in reg2.listar()


def test_listar_retorna_lista(tmp_path):
    reg = RegistroPeers(caminho=str(tmp_path / "peers.json"))
    reg.adicionar("peer1:5000")
    resultado = reg.listar()
    assert isinstance(resultado, list)


def test_thread_safety_adicionar_concorrente(tmp_path):
    reg = RegistroPeers(caminho=str(tmp_path / "peers.json"))
    threads = []
    for i in range(30):
        t = threading.Thread(target=reg.adicionar, args=(f"peer_{i}:5000",))
        threads.append(t)
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert reg.quantidade() == 30


def test_arquivo_inexistente_inicializa_vazio(tmp_path):
    caminho = str(tmp_path / "nao_existe" / "peers.json")
    reg = RegistroPeers(caminho=caminho)
    assert reg.quantidade() == 0


def test_listar_nao_contem_duplicatas(tmp_path):
    reg = RegistroPeers(caminho=str(tmp_path / "peers.json"))
    reg.adicionar("peer:5000")
    reg.adicionar("peer:5000")
    assert len(reg.listar()) == 1
