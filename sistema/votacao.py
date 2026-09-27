import re
from datetime import datetime, timezone

from core.cripto import chave_publica_valida
from sistema.armazenamento import carregar_json, salvar_json, travar
from sistema.autenticacao import LOGIN_VALIDO

CAMINHO_VOTACOES_PADRAO = "data/votacoes.json"
ID_VOTACAO_VALIDO = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _carregar_votacoes(caminho: str = None) -> dict:
    return carregar_json(caminho or CAMINHO_VOTACOES_PADRAO, {})


def _salvar_votacoes(votacoes: dict, caminho: str = None):
    salvar_json(caminho or CAMINHO_VOTACOES_PADRAO, votacoes)


def criar_votacao(id_votacao: str, nome_votacao: str, opcoes: list,
                  inicio: str = None, fim: str = None, criador: str = None,
                  caminho: str = None) -> bool:
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
            "fim": fim,
            "criador": criador,
            "delegados": {}
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

        alterou = _incluir_eleitor(votacoes[id_votacao], login_eleitor, chave_publica)
        if alterou:
            _salvar_votacoes(votacoes, caminho)
        return alterou


def autorizar_eleitores(id_votacao: str, eleitores: list[tuple[str, str]], caminho: str = None) -> list[str]:
    """Autorizacao em lote com uma leitura e uma escrita. Retorna os logins que mudaram algo."""
    caminho = caminho or CAMINHO_VOTACOES_PADRAO
    with travar(caminho):
        votacoes = _carregar_votacoes(caminho)
        if id_votacao not in votacoes:
            return []

        dados = votacoes[id_votacao]
        alterados = [login for login, chave in eleitores if _incluir_eleitor(dados, login, chave)]
        if alterados:
            _salvar_votacoes(votacoes, caminho)
        return alterados


def _incluir_eleitor(dados: dict, login_eleitor: str, chave_publica: str | None) -> bool:
    eleitores = dados.setdefault("eleitores", [])
    chaves = dados.setdefault("chaves_autorizadas", [])

    alterou = False
    if login_eleitor not in eleitores:
        eleitores.append(login_eleitor)
        alterou = True
    if chave_publica and chave_publica not in chaves:
        chaves.append(chave_publica)
        alterou = True
    return alterou


def eleitor_autorizado(id_votacao: str, login_eleitor: str, caminho: str = None) -> bool:
    votacoes = _carregar_votacoes(caminho)
    return login_eleitor in votacoes.get(id_votacao, {}).get("eleitores", [])


def papel_na_votacao(id_votacao: str, login: str, caminho: str = None) -> str | None:
    # "criador" gerencia a votacao e delega; "delegado" so autoriza eleitores
    dados = _carregar_votacoes(caminho).get(id_votacao)
    if dados is None:
        return None
    if dados.get("criador") == login:
        return "criador"
    if login in delegados_ativos(dados):
        return "delegado"
    return None


def delegados_ativos(dados: dict) -> list[str]:
    return sorted(login for login, d in dados.get("delegados", {}).items() if d.get("ativo"))


def definir_delegado(id_votacao: str, login: str, ativo: bool, caminho: str = None) -> bool:
    """
    Concede ou revoga a delegacao. Guarda a data da mudanca porque a revogacao
    tambem precisa se propagar, e no merge vale a mudanca mais recente.
    """
    caminho = caminho or CAMINHO_VOTACOES_PADRAO
    with travar(caminho):
        votacoes = _carregar_votacoes(caminho)
        if id_votacao not in votacoes:
            return False
        delegados = votacoes[id_votacao].setdefault("delegados", {})
        if delegados.get(login, {}).get("ativo", False) == ativo:
            return False
        delegados[login] = {"ativo": ativo, "atualizado_em": datetime.now(timezone.utc).isoformat()}
        _salvar_votacoes(votacoes, caminho)
        return True


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


def _votacao_para_propagar(id_votacao: str, dados: dict) -> dict:
    # sem os logins dos eleitores, que sao locais
    return {
        "id_votacao": id_votacao,
        "nome": dados["nome"],
        "opcoes": dados["opcoes"],
        "ativa": dados["ativa"],
        "chaves_autorizadas": dados.get("chaves_autorizadas", []),
        "inicio": dados.get("inicio"),
        "fim": dados.get("fim"),
        "criador": dados.get("criador"),
        "delegados": dados.get("delegados", {})
    }


def obter_votacao_dict(id_votacao: str, caminho: str = None) -> dict | None:
    dados = _carregar_votacoes(caminho).get(id_votacao)
    if dados is None:
        return None
    return _votacao_para_propagar(id_votacao, dados)


def obter_todas_votacoes_dict(caminho: str = None) -> list[dict]:
    votacoes = _carregar_votacoes(caminho)
    return [_votacao_para_propagar(id_votacao, dados) for id_votacao, dados in votacoes.items()]


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
        if valor is not None and not _data_iso_valida(valor):
            return False
    criador = dados.get("criador")
    if criador is not None and not _login_valido(criador):
        return False
    delegados = dados.get("delegados", {})
    if not isinstance(delegados, dict):
        return False
    for login, delegacao in delegados.items():
        if not _login_valido(login) or not isinstance(delegacao, dict):
            return False
        if not isinstance(delegacao.get("ativo"), bool) or not _data_com_fuso(delegacao.get("atualizado_em")):
            return False
    return True


def _login_valido(valor) -> bool:
    return isinstance(valor, str) and LOGIN_VALIDO.match(valor) is not None


def _data_iso_valida(valor) -> bool:
    try:
        datetime.fromisoformat(valor)
        return True
    except (TypeError, ValueError):
        return False


def _data_com_fuso(valor) -> bool:
    # comparada com as datas locais no merge, entao precisa de fuso
    return _data_iso_valida(valor) and datetime.fromisoformat(valor).tzinfo is not None


def _delegacao_mais_recente(recebida: dict, local: dict) -> bool:
    recebida_em = datetime.fromisoformat(recebida["atualizado_em"])
    local_em = datetime.fromisoformat(local["atualizado_em"])
    if recebida_em != local_em:
        return recebida_em > local_em
    # empate: a revogacao prevalece
    return local["ativo"] and not recebida["ativo"]


def merge_votacao(dados_votacao: dict, caminho: str = None) -> bool:
    """
    Merge uma votacao recebida de um peer.
    - Se nao existe localmente, cria (sem eleitores — os logins sao locais).
    - Une as chaves autorizadas: uma autorizacao feita em qualquer no vale em todos.
    - Se ja existe e o peer encerrou (ativa=False), encerra localmente tambem.
    - Delegacoes: para cada admin vale a concessao ou revogacao mais recente.
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
                "fim": dados_votacao.get("fim"),
                "criador": dados_votacao.get("criador"),
                "delegados": dict(dados_votacao.get("delegados", {}))
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

        if dados.get("criador") is None and dados_votacao.get("criador"):
            dados["criador"] = dados_votacao["criador"]
            alterou = True

        delegados = dados.setdefault("delegados", {})
        for login, recebida in dados_votacao.get("delegados", {}).items():
            local = delegados.get(login)
            if local is None or _delegacao_mais_recente(recebida, local):
                delegados[login] = dict(recebida)
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