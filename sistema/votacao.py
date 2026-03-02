import json
import os

CAMINHO_VOTACOES_PADRAO = "data/votacoes.json"


def _carregar_votacoes(caminho: str = None) -> dict:
    caminho = caminho or CAMINHO_VOTACOES_PADRAO
    if os.path.exists(caminho):
        with open(caminho, "r") as f:
            return json.load(f)
    return {}


def _salvar_votacoes(votacoes: dict, caminho: str = None):
    caminho = caminho or CAMINHO_VOTACOES_PADRAO
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w") as f:
        json.dump(votacoes, f, indent=4)


def criar_votacao(id_votacao: str, nome_votacao: str, opcoes: list, caminho: str = None) -> bool:
    """Cria uma nova sessao de votacao."""
    votacoes = _carregar_votacoes(caminho)
    if id_votacao in votacoes:
        return False
    votacoes[id_votacao] = {
        "nome": nome_votacao,
        "opcoes": opcoes,
        "ativa": True,
        "eleitores": []
    }
    _salvar_votacoes(votacoes, caminho)
    return True


def listar_votacoes(apenas_ativas: bool = False, caminho: str = None) -> list[tuple[str, str]]:
    votacoes = _carregar_votacoes(caminho)
    resultado = []
    for id_votacao, dados in votacoes.items():
        if apenas_ativas and not dados.get("ativa", False):
            continue
        nome = dados.get("nome", "Sem nome")
        resultado.append((id_votacao, nome))
    return resultado


def obter_nome_votacao(id_votacao: str, caminho: str = None) -> str:
    votacoes = _carregar_votacoes(caminho)
    return votacoes.get(id_votacao, {}).get("nome", "Sem nome")


def encerrar_votacao(id_votacao: str, caminho: str = None) -> bool:
    votacoes = _carregar_votacoes(caminho)
    if id_votacao not in votacoes:
        return False
    votacoes[id_votacao]["ativa"] = False
    _salvar_votacoes(votacoes, caminho)
    return True


def autorizar_eleitor(id_votacao: str, login_eleitor: str, caminho: str = None) -> bool:
    votacoes = _carregar_votacoes(caminho)
    if id_votacao in votacoes:
        if login_eleitor not in votacoes[id_votacao]["eleitores"]:
            votacoes[id_votacao]["eleitores"].append(login_eleitor)
            _salvar_votacoes(votacoes, caminho)
            return True
    return False


def eleitor_autorizado(id_votacao: str, login_eleitor: str, caminho: str = None) -> bool:
    votacoes = _carregar_votacoes(caminho)
    return login_eleitor in votacoes.get(id_votacao, {}).get("eleitores", [])


def votacao_ativa(id_votacao: str, caminho: str = None) -> bool:
    votacoes = _carregar_votacoes(caminho)
    return votacoes.get(id_votacao, {}).get("ativa", False)


def opcoes_disponiveis(id_votacao: str, caminho: str = None) -> list:
    votacoes = _carregar_votacoes(caminho)
    return votacoes.get(id_votacao, {}).get("opcoes", [])


def obter_votacao_dict(id_votacao: str, caminho: str = None) -> dict | None:
    """Retorna dados de uma votacao como dict (sem eleitores, para propagacao)."""
    votacoes = _carregar_votacoes(caminho)
    dados = votacoes.get(id_votacao)
    if dados is None:
        return None
    return {
        "id_votacao": id_votacao,
        "nome": dados["nome"],
        "opcoes": dados["opcoes"],
        "ativa": dados["ativa"]
    }


def obter_todas_votacoes_dict(caminho: str = None) -> list[dict]:
    """Retorna todas as votacoes como lista de dicts (sem eleitores, para sync)."""
    votacoes = _carregar_votacoes(caminho)
    resultado = []
    for id_votacao, dados in votacoes.items():
        resultado.append({
            "id_votacao": id_votacao,
            "nome": dados["nome"],
            "opcoes": dados["opcoes"],
            "ativa": dados["ativa"]
        })
    return resultado


def merge_votacao(dados_votacao: dict, caminho: str = None) -> bool:
    """
    Merge uma votacao recebida de um peer.
    - Se nao existe localmente, cria (sem eleitores — eleitores sao locais).
    - Se ja existe e o peer encerrou (ativa=False), encerra localmente tambem.
    Retorna True se houve alteracao.
    """
    votacoes = _carregar_votacoes(caminho)
    id_votacao = dados_votacao["id_votacao"]

    if id_votacao not in votacoes:
        votacoes[id_votacao] = {
            "nome": dados_votacao["nome"],
            "opcoes": dados_votacao["opcoes"],
            "ativa": dados_votacao["ativa"],
            "eleitores": []
        }
        _salvar_votacoes(votacoes, caminho)
        return True

    # Se ja existe, so atualiza ativa=False (encerramento se propaga)
    if not dados_votacao["ativa"] and votacoes[id_votacao]["ativa"]:
        votacoes[id_votacao]["ativa"] = False
        _salvar_votacoes(votacoes, caminho)
        return True

    return False
