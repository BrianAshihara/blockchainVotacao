"""
Testes de integracao — rede P2P com 3 nos reais.

Inicia 3 processos run_node.py com --host 127.0.0.1 em portas
diferentes, executa um fluxo completo de votacao e verifica que
transacoes, blocos e sessoes de votacao propagam corretamente.

Executar:
    python -m pytest tests/test_integracao_rede.py -v
"""

import os
import sys
import time
import subprocess
import signal

import pytest
import requests

# Adiciona raiz do projeto ao path para imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.cripto import gerar_par_chaves, assinar
from core.transacao import Transacao

# ---------------------------------------------------------------------------
# Configuracao
# ---------------------------------------------------------------------------
HOST = "127.0.0.1"
PORTA_A = 5050
PORTA_B = 5051
PORTA_C = 5052
URL_A = f"http://{HOST}:{PORTA_A}"
URL_B = f"http://{HOST}:{PORTA_B}"
URL_C = f"http://{HOST}:{PORTA_C}"

ID_VOTACAO = "integracao_v1"
NOME_VOTACAO = "Teste de Integracao"
OPCOES = ["Sim", "Nao", "Abstencao"]

SK_ELEITOR, PK_ELEITOR = gerar_par_chaves()


def esperar_no(url, timeout=15):
    """Aguarda ate o no responder em GET /no/info."""
    inicio = time.time()
    while time.time() - inicio < timeout:
        try:
            resp = requests.get(f"{url}/no/info", timeout=2)
            if resp.status_code == 200:
                return True
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(0.3)
    raise TimeoutError(f"No em {url} nao respondeu em {timeout}s")


def _token_master():
    resp = requests.post(f"{URL_A}/usuario/login", json={"login": "admin", "senha": "admin"}, timeout=5)
    return resp.json()["token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def esperar_propagacao(condicao_fn, timeout=10, intervalo=0.5):
    """Aguarda ate condicao_fn() retornar True ou timeout."""
    inicio = time.time()
    while time.time() - inicio < timeout:
        if condicao_fn():
            return True
        time.sleep(intervalo)
    return False


# ---------------------------------------------------------------------------
# Fixture — inicia 3 nos como subprocessos
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def rede(tmp_path_factory):
    """Inicia 3 nos P2P e aguarda estarem prontos."""
    dir_a = str(tmp_path_factory.mktemp("node_a"))
    dir_b = str(tmp_path_factory.mktemp("node_b"))
    dir_c = str(tmp_path_factory.mktemp("node_c"))

    python = sys.executable
    projeto = os.path.join(os.path.dirname(__file__), "..")

    # cada no confia nos outros dois, como o operador faria na montagem do cluster
    chaves = {}
    for d in (dir_a, dir_b, dir_c):
        saida = subprocess.run([python, "run_node.py", "--dados", d, "--mostrar-chave"],
                               cwd=projeto, capture_output=True, text=True, check=True)
        chaves[d] = saida.stdout.strip()

    def confiaveis(proprio):
        return ["--nos-confiaveis", *[c for d, c in chaves.items() if d != proprio]]

    # a mineracao automatica fica longe para nao se adiantar ao POST /minerar do test_06
    sem_auto_mineracao = ["--intervalo-mineracao", "600"]

    # log em arquivo: um PIPE que ninguem le enche e trava o no
    logs = [open(os.path.join(d, "no.log"), "w") for d in (dir_a, dir_b, dir_c)]

    # No A — sem peers (primeiro a iniciar)
    proc_a = subprocess.Popen(
        [python, "run_node.py",
         "--host", HOST, "--porta", str(PORTA_A), "--dados", dir_a, *sem_auto_mineracao,
         *confiaveis(dir_a)],
        cwd=projeto,
        stdout=logs[0],
        stderr=subprocess.STDOUT,
    )

    # Esperar A ficar pronto antes de iniciar B e C
    esperar_no(URL_A)

    # No B — peer de A
    proc_b = subprocess.Popen(
        [python, "run_node.py",
         "--host", HOST, "--porta", str(PORTA_B), "--dados", dir_b, *sem_auto_mineracao,
         *confiaveis(dir_b), "--peers", f"{HOST}:{PORTA_A}"],
        cwd=projeto,
        stdout=logs[1],
        stderr=subprocess.STDOUT,
    )

    # No C — peers de A e B
    proc_c = subprocess.Popen(
        [python, "run_node.py",
         "--host", HOST, "--porta", str(PORTA_C), "--dados", dir_c, *sem_auto_mineracao,
         *confiaveis(dir_c), "--peers", f"{HOST}:{PORTA_A}", f"{HOST}:{PORTA_B}"],
        cwd=projeto,
        stdout=logs[2],
        stderr=subprocess.STDOUT,
    )

    esperar_no(URL_B)
    esperar_no(URL_C)

    # Aguarda handshake bidirecional completar
    time.sleep(2)

    yield {
        "urls": [URL_A, URL_B, URL_C],
        "dirs": [dir_a, dir_b, dir_c],
    }

    # Teardown — encerrar processos
    for proc in [proc_a, proc_b, proc_c]:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    for log in logs:
        log.close()


# ---------------------------------------------------------------------------
# Testes de integracao (executados em ordem)
# ---------------------------------------------------------------------------

class TestIntegracaoRede:
    """Testes de integracao P2P — executados em sequencia sobre a mesma rede."""

    def test_01_peers_registrados_com_ip_real(self, rede):
        """Verifica que peers usam IP real (127.0.0.1), nao localhost."""
        for url in rede["urls"]:
            resp = requests.get(f"{url}/peers", timeout=5)
            assert resp.status_code == 200
            peers = resp.json()["peers"]
            assert len(peers) >= 1, f"No em {url} deveria ter pelo menos 1 peer"
            for peer in peers:
                assert peer.startswith(HOST), (
                    f"Peer '{peer}' deveria comecar com {HOST}, "
                    f"nao com localhost"
                )

    def test_02_todos_nos_conhecem_todos(self, rede):
        """Verifica que cada no conhece os outros 2 (handshake bidirecional)."""
        for url in rede["urls"]:
            resp = requests.get(f"{url}/peers", timeout=5)
            peers = resp.json()["peers"]
            assert len(peers) == 2, (
                f"No em {url} deveria conhecer 2 peers, "
                f"mas conhece {len(peers)}: {peers}"
            )

    def test_03_votacao_propaga_para_todos_nos(self, rede):
        """Cria votacao no No A e verifica que propaga para B e C."""
        token = _token_master()
        resp = requests.post(f"{URL_A}/votacao/criar", headers=_auth(token), timeout=5,
                             json={"id_votacao": ID_VOTACAO, "nome": NOME_VOTACAO, "opcoes": OPCOES})
        assert resp.status_code == 201, resp.json()

        resp = requests.post(f"{URL_A}/usuario/autorregistrar", timeout=5, json={
            "login": "eleitor_integracao", "senha": "senha123",
            "chave_publica": PK_ELEITOR, "chave_privada_cifrada": "{}"})
        assert resp.status_code == 201, resp.json()

        resp = requests.post(f"{URL_A}/votacao/autorizar", headers=_auth(token), timeout=5,
                             json={"id_votacao": ID_VOTACAO, "login": "eleitor_integracao"})
        assert resp.status_code == 200, resp.json()

        # Aguardar propagacao da sessao e da chave autorizada
        def votacao_em_todos():
            for url in [URL_B, URL_C]:
                resp = requests.get(f"{url}/votacoes", timeout=5)
                votacoes = {v["id_votacao"]: v for v in resp.json().get("votacoes", [])}
                if PK_ELEITOR not in votacoes.get(ID_VOTACAO, {}).get("chaves_autorizadas", []):
                    return False
            return True

        assert esperar_propagacao(votacao_em_todos), (
            "Votacao nao propagou para todos os nos em tempo"
        )

    def test_03b_sessao_sem_assinatura_recusada_em_todos_nos(self, rede):
        # tentativa de encerrar a votacao de fora da rede de nos confiaveis
        encerramento = {"id_votacao": ID_VOTACAO, "nome": NOME_VOTACAO, "opcoes": OPCOES, "ativa": False}
        for url in rede["urls"]:
            resp = requests.post(f"{url}/votacao", json=encerramento, timeout=5)
            assert resp.status_code == 401, f"No {url} aceitou sessao sem assinatura"
            votacoes = {v["id_votacao"]: v for v in requests.get(f"{url}/votacoes", timeout=5).json()["votacoes"]}
            assert votacoes[ID_VOTACAO]["ativa"] is True

    def test_04_transacao_aceita_e_na_mempool(self, rede):
        """Cria transacao assinada e submete ao No A."""
        tx = Transacao(
            id_votacao=ID_VOTACAO,
            chave_publica=PK_ELEITOR,
            escolha="Sim",
        )
        tx.assinatura = assinar(SK_ELEITOR, tx.dados_para_assinar())

        resp = requests.post(f"{URL_A}/transacao", json=tx.to_dict(), timeout=5)
        assert resp.status_code == 201, f"Transacao rejeitada: {resp.json()}"

        # Verificar mempool do No A
        resp = requests.get(f"{URL_A}/mempool", timeout=5)
        assert resp.json()["total"] >= 1

    def test_04b_chave_nao_autorizada_rejeitada_em_todos_nos(self, rede):
        sk, pk = gerar_par_chaves()
        tx = Transacao(id_votacao=ID_VOTACAO, chave_publica=pk, escolha="Nao")
        tx.assinatura = assinar(sk, tx.dados_para_assinar())

        for url in rede["urls"]:
            resp = requests.post(f"{url}/transacao", json=tx.to_dict(), timeout=5)
            assert resp.status_code == 400, f"No {url} aceitou voto nao autorizado"
            assert "autorizado" in resp.json()["erro"].lower()

    def test_05_transacao_propaga_para_peers(self, rede):
        """Verifica que a transacao submetida ao A propagou para B e C."""
        def mempool_em_todos():
            for url in [URL_B, URL_C]:
                resp = requests.get(f"{url}/mempool", timeout=5)
                if resp.json()["total"] < 1:
                    return False
            return True

        assert esperar_propagacao(mempool_em_todos), (
            "Transacao nao propagou para todos os nos"
        )

    def test_06_minerar_bloco_e_propaga(self, rede):
        """Minera bloco no No A e verifica propagacao para B e C."""
        resp = requests.post(f"{URL_A}/minerar", timeout=120)
        assert resp.status_code == 201, f"Mineracao falhou: {resp.json()}"

        bloco = resp.json()["bloco"]
        assert bloco["indice"] == 1

        # Aguardar propagacao do bloco
        def chain_atualizada():
            for url in [URL_B, URL_C]:
                resp = requests.get(f"{url}/chain/comprimento", timeout=5)
                if resp.json()["comprimento"] < 2:
                    return False
            return True

        assert esperar_propagacao(chain_atualizada), (
            "Bloco minerado nao propagou para todos os nos"
        )

        # Todos devem ter comprimento 2 (genesis + bloco minerado)
        for url in rede["urls"]:
            resp = requests.get(f"{url}/chain/comprimento", timeout=5)
            assert resp.json()["comprimento"] == 2

    def test_07_mempool_vazia_apos_mineracao(self, rede):
        """Mempool deve estar vazia em todos os nos apos mineracao."""
        def mempool_vazia():
            for url in rede["urls"]:
                resp = requests.get(f"{url}/mempool", timeout=5)
                if resp.json()["total"] != 0:
                    return False
            return True

        assert esperar_propagacao(mempool_vazia), (
            "Mempool deveria estar vazia apos mineracao"
        )

    def test_08a_relatorio_slim_durante_sessao_ativa(self, rede):
        """Sessao ativa: relatorio retorna payload slim (apenas total, sem breakdown)."""
        resp = requests.get(f"{URL_A}/votacao/relatorio/{ID_VOTACAO}", timeout=5)
        assert resp.status_code == 200
        slim = resp.json()
        assert slim["ativa"] is True
        assert slim["total_votos_confirmados"] == 1
        # Breakdown NAO deve estar exposto durante sessao ativa
        assert "detalhes" not in slim
        assert "vencedor" not in slim

    def test_08b_contagem_endpoint_publico(self, rede):
        """GET /votacao/contagem/<id> retorna apenas total, em qualquer estado."""
        for url in rede["urls"]:
            resp = requests.get(f"{url}/votacao/contagem/{ID_VOTACAO}", timeout=5)
            assert resp.status_code == 200
            assert resp.json()["total_votos_confirmados"] == 1

    def test_08c_relatorio_completo_apos_encerramento(self, rede):
        """Apos encerrar sessao e propagar, relatorio completo expoe breakdown e vencedor."""
        resp = requests.post(f"{URL_A}/votacao/encerrar", headers=_auth(_token_master()), timeout=30,
                             json={"id_votacao": ID_VOTACAO})
        assert resp.status_code == 200, resp.json()

        # Aguardar encerramento propagar para todos os nos
        def encerrada_em_todos():
            for url in rede["urls"]:
                r = requests.get(f"{url}/votacao/relatorio/{ID_VOTACAO}", timeout=5)
                d = r.json()
                if d.get("ativa") is True:
                    return False
            return True

        assert esperar_propagacao(encerrada_em_todos), (
            "Encerramento nao propagou para todos os nos"
        )

        # Relatorio completo deve estar disponivel em qualquer no
        for url in rede["urls"]:
            resp = requests.get(f"{url}/votacao/relatorio/{ID_VOTACAO}", timeout=5)
            assert resp.status_code == 200
            relatorio = resp.json()
            assert relatorio["detalhes"]["Sim"]["votos"] == 1
            assert relatorio["detalhes"]["Sim"]["percentual"] == 100.0
            assert relatorio["vencedor"] == "Sim"
            assert relatorio["total_votos_confirmados"] == 1
            assert relatorio["total_eleitores_autorizados"] == 1
            assert relatorio["blocos_com_votos"] == 1

    def test_09_integridade_chain_todos_nos(self, rede):
        """Chain deve ser valida e integra em todos os nos."""
        for url in rede["urls"]:
            resp = requests.get(f"{url}/chain/integridade", timeout=5)
            assert resp.status_code == 200
            assert resp.json()["valida"] is True, (
                f"Chain invalida no no {url}"
            )

    def test_10_chains_identicas_em_todos_nos(self, rede):
        """Todos os nos devem ter exatamente a mesma chain."""
        chains = []
        for url in rede["urls"]:
            resp = requests.get(f"{url}/chain", timeout=5)
            blocos = resp.json()["blocos"]
            chains.append(blocos)

        # Comparar hashes de todos os blocos
        hashes_a = [b["hash_atual"] for b in chains[0]]
        hashes_b = [b["hash_atual"] for b in chains[1]]
        hashes_c = [b["hash_atual"] for b in chains[2]]

        assert hashes_a == hashes_b, "Chain de A difere de B"
        assert hashes_a == hashes_c, "Chain de A difere de C"
