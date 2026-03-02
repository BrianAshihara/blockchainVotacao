import hashlib
import json
import os

from core.cripto import gerar_par_chaves

CAMINHO_USUARIOS = "data/usuarios.json"


def hash_senha(senha: str) -> str:
    """Preservado de sistema.py."""
    return hashlib.sha256(senha.encode()).hexdigest()


def _carregar_usuarios() -> dict:
    if os.path.exists(CAMINHO_USUARIOS):
        with open(CAMINHO_USUARIOS, "r") as f:
            return json.load(f)
    return {}


def _salvar_usuarios(usuarios: dict):
    os.makedirs(os.path.dirname(CAMINHO_USUARIOS), exist_ok=True)
    with open(CAMINHO_USUARIOS, "w") as f:
        json.dump(usuarios, f, indent=4)


def autenticar(login: str, senha: str) -> bool:
    """Preservado de sistema.py."""
    if login == "admin" and senha == "admin":
        return True
    usuarios = _carregar_usuarios()
    if login in usuarios:
        return usuarios[login]["senha"] == hash_senha(senha)
    return False


def tipo_usuario(login: str) -> str | None:
    """Preservado de sistema.py."""
    if login == "admin":
        return "admin"
    usuarios = _carregar_usuarios()
    return usuarios.get(login, {}).get("tipo", None)


def cadastrar_usuario(login: str, senha: str, tipo: str) -> bool:
    """
    Adaptado de sistema.py.
    Agora tambem gera par de chaves ECDSA para o usuario.
    """
    if tipo not in ["admin", "eleitor", "auditor"]:
        raise ValueError("Tipo de usuario invalido.")
    usuarios = _carregar_usuarios()
    if login in usuarios:
        return False

    chave_privada, chave_publica = gerar_par_chaves()
    usuarios[login] = {
        "senha": hash_senha(senha),
        "tipo": tipo,
        "chave_privada": chave_privada,
        "chave_publica": chave_publica
    }
    _salvar_usuarios(usuarios)
    return True


def obter_chaves_usuario(login: str) -> tuple[str, str] | None:
    """Retorna (chave_privada, chave_publica) do usuario."""
    usuarios = _carregar_usuarios()
    usuario = usuarios.get(login)
    if usuario and "chave_privada" in usuario:
        return usuario["chave_privada"], usuario["chave_publica"]
    return None


def listar_eleitores() -> list[str]:
    """Preservado de sistema.py."""
    usuarios = _carregar_usuarios()
    return [login for login, dados in usuarios.items() if dados["tipo"] == "eleitor"]
