import hashlib
import json
import time


class Transacao:
    """
    Representa um voto como transacao assinada.

    Campos:
        id_votacao: str          -- identifica qual votacao
        chave_publica: str       -- hex da chave publica do eleitor
        escolha: str             -- candidato/opcao escolhida
        timestamp: float         -- Unix timestamp
        assinatura: str          -- hex da assinatura ECDSA
    """

    def __init__(self, id_votacao: str, chave_publica: str, escolha: str,
                 timestamp: float = None, assinatura: str = None):
        self.id_votacao = id_votacao
        self.chave_publica = chave_publica
        self.escolha = escolha
        self.timestamp = timestamp or time.time()
        self.assinatura = assinatura

    def dados_para_assinar(self) -> str:
        """
        Retorna a string canonica que sera assinada.
        NAO inclui a assinatura.
        """
        return json.dumps({
            "id_votacao": self.id_votacao,
            "chave_publica": self.chave_publica,
            "escolha": self.escolha,
            "timestamp": self.timestamp
        }, sort_keys=True)

    def calcular_hash(self) -> str:
        """Hash unico da transacao (usado como TX ID)."""
        return hashlib.sha256(self.dados_para_assinar().encode()).hexdigest()

    def to_dict(self) -> dict:
        return {
            "id_votacao": self.id_votacao,
            "chave_publica": self.chave_publica,
            "escolha": self.escolha,
            "timestamp": self.timestamp,
            "assinatura": self.assinatura,
            "tx_hash": self.calcular_hash()
        }

    @staticmethod
    def from_dict(data: dict) -> "Transacao":
        return Transacao(
            id_votacao=data["id_votacao"],
            chave_publica=data["chave_publica"],
            escolha=data["escolha"],
            timestamp=data["timestamp"],
            assinatura=data["assinatura"]
        )
