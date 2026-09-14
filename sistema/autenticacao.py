import hashlib

from core.cripto import gerar_par_chaves
from sistema.armazenamento import carregar_json, salvar_json, travar

CAMINHO_USUARIOS = "data/usuarios.json"


def hash_senha(senha: str) -> str:
    """Preservado de sistema.py."""
    return hashlib.sha256(senha.encode()).hexdigest()


def _carregar_usuarios(caminho: str = None) -> dict:
    return carregar_json(caminho or CAMINHO_USUARIOS, {})


def _salvar_usuarios(usuarios: dict, caminho: str = None):
    salvar_json(caminho or CAMINHO_USUARIOS, usuarios)


def autenticar(login: str, senha: str, caminho: str = None) -> bool:
    """Preservado de sistema.py."""
    if login == "admin" and senha == "admin":
        return True
    usuarios = _carregar_usuarios(caminho)
    if login in usuarios:
        return usuarios[login]["senha"] == hash_senha(senha)
    return False


def tipo_usuario(login: str, caminho: str = None) -> str | None:
    """Retorna o tipo do usuario: master, admin, eleitor ou None."""
    if login == "admin":
        return "master"
    usuarios = _carregar_usuarios(caminho)
    return usuarios.get(login, {}).get("tipo", None)


def cadastrar_usuario(login: str, senha: str, tipo: str, chave_publica: str = None,
                      chave_privada_cifrada: str = None, caminho: str = None) -> bool:
    """
    Cadastra usuario com par de chaves ECDSA.
    Tipos validos: admin, eleitor (master e hardcoded, nunca via cadastro).

    Cadastro pelo frontend: o par e gerado no navegador e aqui chegam so a
    chave publica e a chave privada ja cifrada com a senha do usuario.
    Cadastro pela CLI (sem chave_publica): o par e gerado aqui, como antes.
    """
    if tipo not in ["admin", "eleitor"]:
        raise ValueError("Tipo de usuario invalido.")
    caminho = caminho or CAMINHO_USUARIOS
    with travar(caminho):
        usuarios = _carregar_usuarios(caminho)
        if login in usuarios:
            return False

        usuario = {
            "senha": hash_senha(senha),
            "tipo": tipo
        }
        if chave_publica:
            usuario["chave_publica"] = chave_publica
            usuario["chave_privada_cifrada"] = chave_privada_cifrada
        else:
            chave_privada, chave_publica = gerar_par_chaves()
            usuario["chave_privada"] = chave_privada
            usuario["chave_publica"] = chave_publica

        usuarios[login] = usuario
        _salvar_usuarios(usuarios, caminho)
        return True


def autorregistrar_eleitor(login: str, senha: str, chave_publica: str = None,
                           chave_privada_cifrada: str = None, caminho: str = None) -> bool:
    """Self-registration: qualquer pessoa pode se registrar como eleitor."""
    return cadastrar_usuario(login, senha, "eleitor", chave_publica=chave_publica,
                             chave_privada_cifrada=chave_privada_cifrada, caminho=caminho)


def promover_para_admin(login: str, caminho: str = None) -> bool:

    # Promove um eleitor para admin.
    # Retorna False se usuario nao encontrado, ja e admin, ou e master.
    
    if login == "admin":
        return False
    caminho = caminho or CAMINHO_USUARIOS
    with travar(caminho):
        usuarios = _carregar_usuarios(caminho)
        if login not in usuarios:
            return False
        if usuarios[login].get("tipo") != "eleitor":
            return False
        usuarios[login]["tipo"] = "admin"
        _salvar_usuarios(usuarios, caminho)
        return True


def rebaixar_para_eleitor(login: str, caminho: str = None) -> bool:
    
    # Volta um admin para eleitor. Quem pode fazer isso (so o master) e conferido na API.
    # Retorna false se usuario nao encontrado, nao e admin, ou e o master.
    
    if login == "admin":
        return False
    caminho = caminho or CAMINHO_USUARIOS
    with travar(caminho):
        usuarios = _carregar_usuarios(caminho)
        if usuarios.get(login, {}).get("tipo") != "admin":
            return False
        usuarios[login]["tipo"] = "eleitor"
        _salvar_usuarios(usuarios, caminho)
        return True


def obter_chaves_usuario(login: str, caminho: str = None) -> tuple[str, str] | None:
    """Retorna (chave_privada, chave_publica) do usuario."""
    usuarios = _carregar_usuarios(caminho)
    usuario = usuarios.get(login)
    if usuario and "chave_privada" in usuario:
        return usuario["chave_privada"], usuario["chave_publica"]
    return None


def obter_usuario_publico(login: str, caminho: str = None) -> dict | None:
    """
    Dados do usuario que podem sair do no: sem hash de senha e sem chave
    privada em claro (so a versao cifrada, quando o cadastro foi pelo frontend).
    """
    if login == "admin":
        return {"login": login, "tipo": "master", "chave_publica": None, "chave_privada_cifrada": None}
    usuario = _carregar_usuarios(caminho).get(login)
    if usuario is None:
        return None
    return {
        "login": login,
        "tipo": usuario.get("tipo"),
        "chave_publica": usuario.get("chave_publica"),
        "chave_privada_cifrada": usuario.get("chave_privada_cifrada")
    }


def listar_eleitores(caminho: str = None) -> list[str]:
    """Retorna logins de todos os usuarios com tipo eleitor."""
    usuarios = _carregar_usuarios(caminho)
    return [login for login, dados in usuarios.items() if dados["tipo"] == "eleitor"]


def listar_admins(caminho: str = None) -> list[str]:
    """Retorna logins de todos os usuarios com tipo admin (nao inclui master)."""
    usuarios = _carregar_usuarios(caminho)
    return [login for login, dados in usuarios.items() if dados["tipo"] == "admin"]