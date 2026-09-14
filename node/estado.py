import json
import os
import threading
from typing import List

from core.bloco import Bloco
from core.cadeia import criar_bloco_genesis, eleitor_ja_votou, verificar_integridade
from core.mempool import Mempool
from node.identidade import IdentidadeNo, NosConfiaveis
from node.registro_peers import RegistroPeers
from node.sessoes import RegistroSessoes


class EstadoNo:
    """
    Estado completo de um no.
    Centraliza chain, mempool, identidade, peers.
    Todo o file I/O de blockchain vive aqui (extraido de blockchain.py Blockchain).
    """

    def __init__(self, diretorio_dados: str = "data", porta: int = 5000,
                 usar_tls: bool = False, require_auth: bool = False):
        self.diretorio = diretorio_dados
        self.porta = porta
        self.usar_tls = usar_tls
        self.require_auth = require_auth
        self._lock = threading.Lock()
        self._mining_lock = threading.Lock()
        self._sync_lock = threading.Lock()

        os.makedirs(diretorio_dados, exist_ok=True)

        self.identidade = IdentidadeNo(
            caminho_arquivo=os.path.join(diretorio_dados, "node_identity.json")
        )

        self.peers = RegistroPeers(
            caminho=os.path.join(diretorio_dados, "peers.json")
        )

        self.nos_confiaveis = NosConfiaveis(
            caminho=os.path.join(diretorio_dados, "nos_confiaveis.json")
        )

        self.mempool = Mempool()

        self.caminho_votacoes = os.path.join(diretorio_dados, "votacoes.json")
        self.caminho_usuarios = os.path.join(diretorio_dados, "usuarios.json")
        self.caminho_chain = os.path.join(diretorio_dados, "chain.json")
        self.sessoes = RegistroSessoes()
        self.blocos: List[Bloco] = self._carregar_ou_criar_chain()

    def _carregar_ou_criar_chain(self) -> List[Bloco]:
        """Adaptado de blockchain.py carregar_ou_criar_blockchain()."""
        if os.path.exists(self.caminho_chain):
            with open(self.caminho_chain, "r") as f:
                dados = json.load(f)
                return [Bloco.from_dict(b) for b in dados]
        else:
            genesis = criar_bloco_genesis()
            self._salvar_chain([genesis])
            return [genesis]

    def _salvar_chain(self, blocos: List[Bloco] = None):
        """Adaptado de blockchain.py salvar_blockchain()."""
        if blocos is None:
            blocos = self.blocos
        os.makedirs(self.diretorio, exist_ok=True)
        with open(self.caminho_chain, "w") as f:
            json.dump([b.to_dict() for b in blocos], f, indent=4)

    def adicionar_bloco(self, bloco: Bloco) -> bool:
        """Adiciona bloco validado a chain e persiste. Thread-safe."""
        with self._lock:
            self.blocos.append(bloco)
            self._salvar_chain()
            for tx in bloco.transacoes:
                self.mempool.remover(tx.calcular_hash())
            return True

    def adicionar_bloco_se_ponta(self, bloco: Bloco) -> bool:
        with self._lock:
            ponta = self.blocos[-1]
            if bloco.indice != ponta.indice + 1 or bloco.hash_anterior != ponta.hash_atual:
                return False
            self.blocos.append(bloco)
            self._salvar_chain()
            for tx in bloco.transacoes:
                self.mempool.remover(tx.calcular_hash())
            return True

    def substituir_chain(self, nova_chain: List[Bloco]) -> bool:
        """Substitui chain inteira (consensus). Thread-safe."""
        with self._lock:
            self.blocos = nova_chain
            self._salvar_chain()
            return True

    def obter_chain_dict(self) -> list:
        with self._lock:
            return [b.to_dict() for b in self.blocos]

    def ultimo_bloco(self) -> Bloco:
        with self._lock:
            return self.blocos[-1]

    def comprimento_chain(self) -> int:
        with self._lock:
            return len(self.blocos)

    def minerar_pendentes(self):
        """
        Minera transacoes pendentes se houver. Retorna o novo bloco ou None.
        Usa _mining_lock para impedir mineracao concorrente.
        """
        acquired = self._mining_lock.acquire(blocking=False)
        if not acquired:
            return None

        try:
            bloco_anterior = self.ultimo_bloco()

            # depois de uma ressincronizacao pode sobrar na mempool voto de quem ja
            # votou na cadeia vencedora: descarta em vez de minerar voto duplo
            transacoes = []
            ja_no_bloco = set()
            for tx in self.mempool.obter_para_mineracao():
                eleitor = (tx.chave_publica, tx.id_votacao)
                if eleitor in ja_no_bloco or eleitor_ja_votou(self.blocos, tx.chave_publica, tx.id_votacao):
                    self.mempool.remover(tx.calcular_hash())
                    continue
                ja_no_bloco.add(eleitor)
                transacoes.append(tx)
            if not transacoes:
                return None

            from core.mineracao import minerar_bloco
            novo_bloco = minerar_bloco(bloco_anterior, transacoes)

            # se chegou bloco de outro no durante a prova de trabalho, este ficou velho
            if not self.adicionar_bloco_se_ponta(novo_bloco):
                return None
            return novo_bloco
        finally:
            self._mining_lock.release()
