import json
import os
import uuid
from datetime import datetime, timezone

from core.cripto import assinar, chave_publica_valida, gerar_par_chaves, verificar_assinatura
from sistema.armazenamento import carregar_json, salvar_json, travar

VALIDADE_MENSAGEM_SEGUNDOS = 300


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

    def assinar_mensagem(self, conteudo) -> dict:
        timestamp = datetime.now(timezone.utc).isoformat()
        return {
            "id_no": self.id_no,
            "chave_publica": self.chave_publica,
            "timestamp": timestamp,
            "assinatura": assinar(self.chave_privada, _dados_mensagem(conteudo, timestamp))
        }


def _dados_mensagem(conteudo, timestamp: str) -> str:
    return json.dumps({"conteudo": conteudo, "timestamp": timestamp}, sort_keys=True)


def verificar_mensagem(conteudo, mensagem: dict, chaves_confiaveis) -> tuple[bool, str]:
    chave_publica = mensagem.get("chave_publica")
    timestamp = mensagem.get("timestamp")
    assinatura = mensagem.get("assinatura")
    if not all(isinstance(c, str) and c for c in (chave_publica, timestamp, assinatura)):
        return False, "Mensagem sem assinatura do no"

    if chave_publica not in chaves_confiaveis:
        return False, "No nao esta na lista de nos confiaveis"

    try:
        momento = datetime.fromisoformat(timestamp)
    except ValueError:
        return False, "Timestamp invalido"
    if momento.tzinfo is None:
        return False, "Timestamp invalido"
    if abs((datetime.now(timezone.utc) - momento).total_seconds()) > VALIDADE_MENSAGEM_SEGUNDOS:
        return False, "Timestamp expirado (max 5 min)"

    try:
        valida = verificar_assinatura(chave_publica, _dados_mensagem(conteudo, timestamp), assinatura)
    except ValueError:
        valida = False
    if not valida:
        return False, "Assinatura do no invalida"
    return True, ""


class NosConfiaveis:
    # chaves publicas dos nos que podem enviar sessoes de votacao para este no

    def __init__(self, caminho: str = "data/nos_confiaveis.json"):
        self.caminho = caminho

    def listar(self) -> list[str]:
        return list(carregar_json(self.caminho, []))

    def adicionar(self, chave_publica: str) -> bool:
        chave_publica = chave_publica.strip().lower()
        if not chave_publica_valida(chave_publica):
            raise ValueError(f"Chave publica invalida: {chave_publica[:16]}...")
        with travar(self.caminho):
            chaves = self.listar()
            if chave_publica in chaves:
                return False
            chaves.append(chave_publica)
            salvar_json(self.caminho, chaves)
            return True
