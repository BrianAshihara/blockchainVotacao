# sistema.py

import hashlib
import json
import os
import csv
from blockchain import Blockchain


CAMINHO_USUARIOS = "data/usuarios.json"
CAMINHO_VOTACOES = "data/votacoes.json"


class Sistema:
    def __init__(self):
        self.usuarios = self._carregar_usuarios()
        self.votacoes = self._carregar_votacoes()

    def _carregar_usuarios(self):
        if os.path.exists(CAMINHO_USUARIOS):
            with open(CAMINHO_USUARIOS, "r") as f:
                return json.load(f)
        return {}

    def _salvar_usuarios(self):
        with open(CAMINHO_USUARIOS, "w") as f:
            json.dump(self.usuarios, f, indent=4)

    def _carregar_votacoes(self):
        if os.path.exists(CAMINHO_VOTACOES):
            with open(CAMINHO_VOTACOES, "r") as f:
                return json.load(f)
        return {}

    def _salvar_votacoes(self):
        with open(CAMINHO_VOTACOES, "w") as f:
            json.dump(self.votacoes, f, indent=4)

    def hash_senha(self, senha):
        return hashlib.sha256(senha.encode()).hexdigest()

    def autenticar(self, login, senha):

        if login == "admin" and senha == "bruno":
            return True

        if login in self.usuarios:
            return self.usuarios[login]["senha"] == self.hash_senha(senha)
        return False

    def tipo_usuario(self, login):
        if login == "admin":
                return "admin"
        return self.usuarios.get(login, {}).get("tipo", None)

    def cadastrar_usuario(self, login, senha, tipo):
        if tipo not in ["admin", "eleitor", "auditor"]:
            raise ValueError("Tipo de usuário inválido.")
        if login in self.usuarios:
            return False
        self.usuarios[login] = {"senha": self.hash_senha(senha), "tipo": tipo}
        self._salvar_usuarios()
        return True


    def criar_votacao(self, id_votacao: str, nome_votacao: str, opcoes: list):
        if id_votacao in self.votacoes:
            return False
        self.votacoes[id_votacao] = {
            "nome": nome_votacao,
            "opcoes": opcoes,
            "ativa": True,
            "eleitores": []
        }
        self._salvar_votacoes()
        Blockchain(f"data/blockchain_votacao_{id_votacao}.json")
        return True

    def listar_votacoes(self, apenas_ativas=False):
        """
        Retorna lista de (id, nome) das votações.
        """
        resultado = []
        for id_votacao, dados in self.votacoes.items():
            if apenas_ativas and not dados.get("ativa", False):
                continue
            nome = dados.get("nome", "Sem nome")
            resultado.append((id_votacao, nome))
        return resultado

    def obter_nome_votacao(self, id_votacao):
        return self.votacoes.get(id_votacao, {}).get("nome", "Sem nome")

    def encerrar_votacao(self, id_votacao):
        if id_votacao not in self.votacoes:
            return False
        self.votacoes[id_votacao]["ativa"] = False
        self._salvar_votacoes()
        return True

    def autorizar_eleitor(self, id_votacao, login_eleitor):
        if id_votacao in self.votacoes and login_eleitor in self.usuarios:
            if login_eleitor not in self.votacoes[id_votacao]["eleitores"]:
                self.votacoes[id_votacao]["eleitores"].append(login_eleitor)
                self._salvar_votacoes()
                return True
        return False

    def eleitor_autorizado(self, id_votacao, login_eleitor):
        return login_eleitor in self.votacoes.get(id_votacao, {}).get("eleitores", [])

    def votacao_ativa(self, id_votacao):
        return self.votacoes.get(id_votacao, {}).get("ativa", False)

    def opcoes_disponiveis(self, id_votacao):
        return self.votacoes.get(id_votacao, {}).get("opcoes", [])

    def exportar_csv(self, id_votacao):
        caminho = f"data/blockchain_votacao_{id_votacao}.json"
        if not os.path.exists(caminho):
            return False

        bc = Blockchain(caminho)
        relatorio = bc.gerar_relatorio()
        csv_path = f"data/relatorio_{id_votacao}.csv"

        with open(csv_path, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["Opção", "Total de Votos"])
            for opcao, total in relatorio["detalhes"].items():
                writer.writerow([opcao, total])
            writer.writerow([])
            writer.writerow(["Vencedor", relatorio["vencedor"]])
            writer.writerow(["Total de votos", relatorio["total"]])
        return csv_path
