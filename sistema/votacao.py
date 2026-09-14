import re
from datetime import datetime, timezone

from core.cripto import chave_publica_valida
from sistema.armazenamento import carregar_json, salvar_json, travar

CAMINHO_VOTACOES_PADRAO = "data/votacoes.json"
ID_VOTACAO_VALIDO = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _carregar_votacoes(caminho: str = None) -> dict:
    return carregar_json(caminho or CAMINHO_VOTACOES_PADRAO, {})


def _salvar_votacoes(votacoes: dict, caminho: str = None):
    salvar_json(caminho or CAMINHO_VOTACOES_PADRAO, votacoes)


def criar_votacao(id_votacao: str, nome_votacao: str, opcoes: list,
                  inicio: str = None, fim: str = None, caminho: str = None) -> bool:
    # Cria uma nova sessao de votacao.
    caminho = caminho or CAMINHO_VOTACOES_PADRAO
    with travar(caminho):
        votacoes = _carregar_votacoes(caminho)
        if id_votacao in votacoes:
            return False
        if inicio is None:
            inicio = datetime.now(timezone.utc).isoformat()
        votacoes[id_votacao] = {
            "nome": nome_votacao,
            "opcoes": opcoes,
            "ativa": True,
            "eleitores": [],
            "chaves_autorizadas": [],
            "inicio": inicio,
            "fim": fim
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
    caminho = caminho or CAMINHO_VOTACOES_PADRAO
    with travar(caminho):
        votacoes = _carregar_votacoes(caminho)
        if id_votacao not in votacoes:
            return False
        votacoes[id_votacao]["ativa"] = False
        _salvar_votacoes(votacoes, caminho)
        return True


def autorizar_eleitor(id_votacao: str, login_eleitor: str, chave_publica: str = None,
                      caminho: str = None) -> bool:
    """
    Autoriza um eleitor na sessao.

    O login fica so neste no (serve para listar as votacoes do eleitor), enquanto
    a chave publica entra em chaves_autorizadas, que e propagada para os peers e
    conferida por todos os nos na validacao do voto.
    """
    caminho = caminho or CAMINHO_VOTACOES_PADRAO
    with travar(caminho):
        votacoes = _carregar_votacoes(caminho)
        if id_votacao not in votacoes:
            return False

        dados = votacoes[id_votacao]
        eleitores = dados.setdefault("eleitores", [])
        chaves = dados.setdefault("chaves_autorizadas", [])

        alterou = False
        if login_eleitor not in eleitores:
            eleitores.append(login_eleitor)
            alterou = True
        if chave_publica and chave_publica not in chaves:
            chaves.append(chave_publica)
            alterou = True

        if alterou:
            _salvar_votacoes(votacoes, caminho)
        return alterou


def eleitor_autorizado(id_votacao: str, login_eleitor: str, caminho: str = None) -> bool:
    votacoes = _carregar_votacoes(caminho)
    return login_eleitor in votacoes.get(id_votacao, {}).get("eleitores", [])


def chave_autorizada(id_votacao: str, chave_publica: str, caminho: str = None) -> bool:
    """Checagem usada na validacao do voto, independente do login (que e local)."""
    votacoes = _carregar_votacoes(caminho)
    dados = votacoes.get(id_votacao)
    if dados is None:
        return False
    return chave_publica in dados.get("chaves_autorizadas", [])


def votacao_ativa(id_votacao: str, caminho: str = None) -> bool:
    votacoes = _carregar_votacoes(caminho)
    dados = votacoes.get(id_votacao, {})
    if not dados.get("ativa", False):
        return False
    agora = datetime.now(timezone.utc)
    inicio = dados.get("inicio")
    if inicio and datetime.fromisoformat(inicio) > agora:
        return False
    fim = dados.get("fim")
    if fim and datetime.fromisoformat(fim) < agora:
        return False
    return True


def opcoes_disponiveis(id_votacao: str, caminho: str = None) -> list:
    votacoes = _carregar_votacoes(caminho)
    return votacoes.get(id_votacao, {}).get("opcoes", [])


def obter_votacao_dict(id_votacao: str, caminho: str = None) -> dict | None:
    """Dados da votacao para propagacao (sem os logins, que sao locais)."""
    votacoes = _carregar_votacoes(caminho)
    dados = votacoes.get(id_votacao)
    if dados is None:
        return None
    return {
        "id_votacao": id_votacao,
        "nome": dados["nome"],
        "opcoes": dados["opcoes"],
        "ativa": dados["ativa"],
        "chaves_autorizadas": dados.get("chaves_autorizadas", []),
        "inicio": dados.get("inicio"),
        "fim": dados.get("fim")
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
            "ativa": dados["ativa"],
            "chaves_autorizadas": dados.get("chaves_autorizadas", []),
            "inicio": dados.get("inicio"),
            "fim": dados.get("fim")
        })
    return resultado


def votacao_recebida_valida(dados) -> bool:
    # confere o formato antes do merge, mesmo vindo de no confiavel
    if not isinstance(dados, dict):
        return False
    if not isinstance(dados.get("id_votacao"), str) or not ID_VOTACAO_VALIDO.match(dados["id_votacao"]):
        return False
    if not isinstance(dados.get("nome"), str) or not dados["nome"].strip():
        return False
    opcoes = dados.get("opcoes")
    if not isinstance(opcoes, list) or len(opcoes) < 2:
        return False
    if not all(isinstance(o, str) and o.strip() for o in opcoes) or len(set(opcoes)) != len(opcoes):
        return False
    if not isinstance(dados.get("ativa"), bool):
        return False
    chaves = dados.get("chaves_autorizadas", [])
    if not isinstance(chaves, list) or not all(chave_publica_valida(c) for c in chaves):
        return False
    for campo in ("inicio", "fim"):
        valor = dados.get(campo)
        if valor is None:
            continue
        try:
            datetime.fromisoformat(valor)
        except (TypeError, ValueError):
            return False
    return True


def merge_votacao(dados_votacao: dict, caminho: str = None) -> bool:
    """
    Merge uma votacao recebida de um peer.
    - Se nao existe localmente, cria (sem eleitores — os logins sao locais).
    - Une as chaves autorizadas: uma autorizacao feita em qualquer no vale em todos.
    - Se ja existe e o peer encerrou (ativa=False), encerra localmente tambem.
    Retorna True se houve alteracao.
    """
    caminho = caminho or CAMINHO_VOTACOES_PADRAO
    id_votacao = dados_votacao["id_votacao"]
    chaves_recebidas = dados_votacao.get("chaves_autorizadas", [])

    with travar(caminho):
        votacoes = _carregar_votacoes(caminho)

        if id_votacao not in votacoes:
            votacoes[id_votacao] = {
                "nome": dados_votacao["nome"],
                "opcoes": dados_votacao["opcoes"],
                "ativa": dados_votacao["ativa"],
                "eleitores": [],
                "chaves_autorizadas": list(chaves_recebidas),
                "inicio": dados_votacao.get("inicio"),
                "fim": dados_votacao.get("fim")
            }
            _salvar_votacoes(votacoes, caminho)
            return True

        dados = votacoes[id_votacao]
        alterou = False

        chaves = dados.setdefault("chaves_autorizadas", [])
        for chave in chaves_recebidas:
            if chave not in chaves:
                chaves.append(chave)
                alterou = True

        if not dados_votacao["ativa"] and dados["ativa"]:
            dados["ativa"] = False
            alterou = True

        if alterou:
            _salvar_votacoes(votacoes, caminho)
        return alterou


def listar_votacoes_expiradas(caminho: str = None) -> list[str]:
    """Retorna IDs de sessoes onde ativa==True mas fim ja passou."""
    votacoes = _carregar_votacoes(caminho)
    agora = datetime.now(timezone.utc)
    expiradas = []
    for id_votacao, dados in votacoes.items():
        if not dados.get("ativa", False):
            continue
        fim = dados.get("fim")
        if fim and datetime.fromisoformat(fim) <= agora:
            expiradas.append(id_votacao)
    return expiradas


def listar_votacoes_eleitor(login_eleitor: str, apenas_ativas: bool = False,
                            caminho: str = None) -> list[tuple[str, str]]:
    """Retorna votacoes que o eleitor esta autorizado a participar."""
    votacoes = _carregar_votacoes(caminho)
    resultado = []
    for id_votacao, dados in votacoes.items():
        if login_eleitor not in dados.get("eleitores", []):
            continue
        if apenas_ativas and not votacao_ativa(id_votacao, caminho):
            continue
        resultado.append((id_votacao, dados.get("nome", "Sem nome")))
    return resultado


def obter_total_eleitores(id_votacao: str, caminho: str = None) -> int:
    """
    Numero de eleitores autorizados. Usa as chaves (replicadas entre os nos) e
    cai para os logins locais em sessoes antigas, criadas antes das chaves.
    """
    dados = _carregar_votacoes(caminho).get(id_votacao, {})
    chaves = dados.get("chaves_autorizadas", [])
    if chaves:
        return len(chaves)
    return len(dados.get("eleitores", []))