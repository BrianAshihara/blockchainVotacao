# blockchain.py

import hashlib
import json
import os
import time
from typing import List, Dict


class Bloco:
    def __init__(self, indice: int, timestamp: str, votos: List[Dict], hash_anterior: str):
        self.indice = indice
        self.timestamp = timestamp
        self.votos = votos  # cada voto: {"eleitor_hash": ..., "escolha": ...}
        self.hash_anterior = hash_anterior
        self.hash_atual = self.gerar_hash()

    def gerar_hash(self):
        conteudo = f"{self.indice}{self.timestamp}{self.votos}{self.hash_anterior}".encode()
        return hashlib.sha256(conteudo).hexdigest()

    def to_dict(self):
        return {
            "indice": self.indice,
            "timestamp": self.timestamp,
            "votos": self.votos,
            "hash_anterior": self.hash_anterior,
            "hash_atual": self.hash_atual
        }

    @staticmethod
    def from_dict(data):
        bloco = Bloco(
            indice=data["indice"],
            timestamp=data["timestamp"],
            votos=data["votos"],
            hash_anterior=data["hash_anterior"]
        )
        # Força manter o hash calculado igual ao salvo
        bloco.hash_atual = data["hash_atual"]
        return bloco


class Blockchain:
    def __init__(self, arquivo_blockchain: str):
        self.arquivo_blockchain = arquivo_blockchain
        self.blocos = self.carregar_ou_criar_blockchain()

    def carregar_ou_criar_blockchain(self):
        if os.path.exists(self.arquivo_blockchain):
            with open(self.arquivo_blockchain, "r") as f:
                dados = json.load(f)
                return [Bloco.from_dict(b) for b in dados]
        else:
            genesis = Bloco(0, time.ctime(), [], "0")
            self.salvar_blockchain([genesis])
            return [genesis]

    def salvar_blockchain(self, blocos=None):
        if blocos is None:
            blocos = self.blocos
        with open(self.arquivo_blockchain, "w") as f:
            json.dump([b.to_dict() for b in blocos], f, indent=4)

    def eleitor_ja_votou(self, eleitor_hash: str) -> bool:
        for bloco in self.blocos:
            for voto in bloco.votos:
                if voto["eleitor_hash"] == eleitor_hash:
                    return True
        return False

    def adicionar_voto(self, eleitor_login: str, escolha: str) -> bool:
        eleitor_hash = hashlib.sha256(eleitor_login.encode()).hexdigest()
        if self.eleitor_ja_votou(eleitor_hash):
            return False

        voto = {"eleitor_hash": eleitor_hash, "escolha": escolha}
        ultimo_bloco = self.blocos[-1]
        novo_bloco = Bloco(
            indice=ultimo_bloco.indice + 1,
            timestamp=time.ctime(),
            votos=[voto],
            hash_anterior=ultimo_bloco.hash_atual
        )
        self.blocos.append(novo_bloco)
        self.salvar_blockchain()
        return True

    def verificar_integridade(self) -> bool:
        for i in range(1, len(self.blocos)):
            bloco_atual = self.blocos[i]
            bloco_anterior = self.blocos[i - 1]
            if bloco_atual.hash_anterior != bloco_anterior.hash_atual:
                return False
            if bloco_atual.hash_atual != bloco_atual.gerar_hash():
                return False
        return True

    def gerar_relatorio(self):
        resultados = {}
        for bloco in self.blocos:
            for voto in bloco.votos:
                escolha = voto["escolha"]
                resultados[escolha] = resultados.get(escolha, 0) + 1

        if not resultados:
            return {"vencedor": None, "total": 0, "detalhes": {}}

        vencedor = max(resultados, key=resultados.get)
        return {
            "vencedor": vencedor,
            "total": sum(resultados.values()),
            "detalhes": resultados
        }
