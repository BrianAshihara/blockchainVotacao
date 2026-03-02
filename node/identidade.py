import json
import os
import uuid

from core.cripto import gerar_par_chaves


class IdentidadeNo:
    """
    Identidade persistente de um no na rede.
    Cada instancia tem um ID unico e um par de chaves.
    """

    def __init__(self, caminho_arquivo: str = "data/node_identity.json"):
        self.caminho = caminho_arquivo
        self.id_no: str = ""
        self.chave_privada: str = ""
        self.chave_publica: str = ""
        self.carregar_ou_criar()

    def carregar_ou_criar(self):
        if os.path.exists(self.caminho):
            with open(self.caminho, "r") as f:
                dados = json.load(f)
                self.id_no = dados["id_no"]
                self.chave_privada = dados["chave_privada"]
                self.chave_publica = dados["chave_publica"]
        else:
            self.id_no = str(uuid.uuid4())
            self.chave_privada, self.chave_publica = gerar_par_chaves()
            self.salvar()

    def salvar(self):
        os.makedirs(os.path.dirname(self.caminho), exist_ok=True)
        with open(self.caminho, "w") as f:
            json.dump({
                "id_no": self.id_no,
                "chave_privada": self.chave_privada,
                "chave_publica": self.chave_publica
            }, f, indent=4)
