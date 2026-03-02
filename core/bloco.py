import hashlib
import json
import time
from typing import List

from core.transacao import Transacao


class Bloco:
    """
    Bloco da blockchain.

    Campos preservados do original (blockchain.py):
        indice, timestamp, hash_anterior, hash_atual

    Campos modificados:
        votos -> transacoes: List[Transacao]

    Campos novos:
        nonce: int              -- PoW nonce
        dificuldade: int        -- numero de zeros iniciais exigidos no hash
    """

    def __init__(self, indice: int, timestamp: float, transacoes: List[Transacao],
                 hash_anterior: str, nonce: int = 0, dificuldade: int = 4):
        self.indice = indice
        self.timestamp = timestamp
        self.transacoes = transacoes
        self.hash_anterior = hash_anterior
        self.nonce = nonce
        self.dificuldade = dificuldade
        self.hash_atual = self.gerar_hash()

    def gerar_hash(self) -> str:
        """
        SHA-256 do conteudo do bloco.
        Usa json.dumps(sort_keys=True) para ser determinístico entre nos.
        """
        conteudo = json.dumps({
            "indice": self.indice,
            "timestamp": self.timestamp,
            "transacoes": [t.to_dict() for t in self.transacoes],
            "hash_anterior": self.hash_anterior,
            "nonce": self.nonce,
            "dificuldade": self.dificuldade
        }, sort_keys=True).encode()
        return hashlib.sha256(conteudo).hexdigest()

    def to_dict(self) -> dict:
        return {
            "indice": self.indice,
            "timestamp": self.timestamp,
            "transacoes": [t.to_dict() for t in self.transacoes],
            "hash_anterior": self.hash_anterior,
            "nonce": self.nonce,
            "dificuldade": self.dificuldade,
            "hash_atual": self.hash_atual
        }

    @staticmethod
    def from_dict(data: dict) -> "Bloco":
        transacoes = [Transacao.from_dict(t) for t in data.get("transacoes", [])]
        bloco = Bloco(
            indice=data["indice"],
            timestamp=data["timestamp"],
            transacoes=transacoes,
            hash_anterior=data["hash_anterior"],
            nonce=data.get("nonce", 0),
            dificuldade=data.get("dificuldade", 4)
        )
        bloco.hash_atual = data["hash_atual"]
        return bloco
