import json
import os
import threading
from typing import Set


class RegistroPeers:
    """
    Registro de peers conhecidos.
    Thread-safe. Persistido em JSON.
    """

    def __init__(self, caminho: str = "data/peers.json"):
        self.caminho = caminho
        self._lock = threading.Lock()
        self._peers: Set[str] = set()
        self._carregar()

    def _carregar(self):
        if os.path.exists(self.caminho):
            with open(self.caminho, "r") as f:
                self._peers = set(json.load(f))

    def _salvar(self):
        os.makedirs(os.path.dirname(self.caminho), exist_ok=True)
        with open(self.caminho, "w") as f:
            json.dump(list(self._peers), f, indent=4)

    def adicionar(self, endereco: str) -> bool:
        """Adiciona peer. Retorna True se era novo."""
        with self._lock:
            if endereco not in self._peers:
                self._peers.add(endereco)
                self._salvar()
                return True
            return False

    def remover(self, endereco: str):
        with self._lock:
            self._peers.discard(endereco)
            self._salvar()

    def listar(self) -> list[str]:
        with self._lock:
            return list(self._peers)

    def quantidade(self) -> int:
        with self._lock:
            return len(self._peers)
