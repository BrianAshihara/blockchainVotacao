import threading
from typing import List

from core.transacao import Transacao


class Mempool:
    """
    Pool de transacoes pendentes aguardando mineracao.
    Thread-safe: acessado por threads do Flask e de mineracao.
    """

    def __init__(self):
        self._transacoes: dict[str, Transacao] = {}
        self._lock = threading.Lock()

    def adicionar(self, tx: Transacao) -> bool:
        """Adiciona transacao se nao for duplicata."""
        tx_hash = tx.calcular_hash()
        with self._lock:
            if tx_hash in self._transacoes:
                return False
            self._transacoes[tx_hash] = tx
            return True

    def remover(self, tx_hash: str) -> None:
        """Remove transacao (apos mineracao em bloco)."""
        with self._lock:
            self._transacoes.pop(tx_hash, None)

    def remover_varias(self, tx_hashes: List[str]) -> None:
        """Remove multiplas transacoes de uma vez."""
        with self._lock:
            for h in tx_hashes:
                self._transacoes.pop(h, None)

    def listar(self) -> List[Transacao]:
        """Retorna copia da lista de transacoes pendentes."""
        with self._lock:
            return list(self._transacoes.values())

    def contem(self, tx_hash: str) -> bool:
        with self._lock:
            return tx_hash in self._transacoes

    def tamanho(self) -> int:
        with self._lock:
            return len(self._transacoes)

    def obter_para_mineracao(self, limite: int = 10) -> List[Transacao]:
        """
        Retorna ate `limite` transacoes para incluir no proximo bloco.
        Ordenadas por timestamp (FIFO).
        """
        with self._lock:
            ordenadas = sorted(self._transacoes.values(), key=lambda t: t.timestamp)
            return ordenadas[:limite]
