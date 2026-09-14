# Testes para node/sessoes.py

import threading

from node.sessoes import RegistroSessoes


def test_criar_e_obter_sessao():
    reg = RegistroSessoes()
    token = reg.criar("joao")
    assert len(token) == 64
    assert reg.obter(token) == "joao"


def test_token_desconhecido_retorna_none():
    reg = RegistroSessoes()
    assert reg.obter("f" * 64) is None


def test_tokens_diferentes_para_mesmo_login():
    reg = RegistroSessoes()
    t1 = reg.criar("joao")
    t2 = reg.criar("joao")
    assert t1 != t2
    assert reg.obter(t1) == reg.obter(t2) == "joao"


def test_remover_sessao():
    reg = RegistroSessoes()
    token = reg.criar("joao")
    reg.remover(token)
    assert reg.obter(token) is None
    reg.remover(token)


def test_sessao_expirada():
    reg = RegistroSessoes(duracao=-1)
    token = reg.criar("joao")
    assert reg.obter(token) is None
    assert reg.quantidade() == 0


def test_criacao_concorrente():
    reg = RegistroSessoes()
    tokens = []
    lock = threading.Lock()

    def criar(i):
        t = reg.criar(f"user{i}")
        with lock:
            tokens.append(t)

    threads = [threading.Thread(target=criar, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(set(tokens)) == 50
    assert reg.quantidade() == 50