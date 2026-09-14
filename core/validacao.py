from typing import List

from core.transacao import Transacao
from core.bloco import Bloco
from core.cripto import verificar_assinatura
from core import cadeia, mineracao


def validar_transacao(tx: Transacao, blocos: List[Bloco], mempool_txs: List[Transacao],
                      caminho_votacoes: str = None) -> tuple[bool, str]:
    """
    Valida uma transacao antes de aceitar na mempool.

    Checks:
    1. Campos obrigatorios presentes
    2. Assinatura valida
    3. Eleitor nao votou na chain (double-vote)
    4. Eleitor nao tem tx pendente na mempool para mesma votacao
    5. Sessao de votacao ativa e dentro do periodo
    6. Chave publica esta na lista de autorizados da sessao
    7. Escolha esta entre as opcoes da sessao
    """
    if not all([tx.id_votacao, tx.chave_publica, tx.escolha, tx.assinatura]):
        return False, "Campos obrigatorios ausentes"

    if not verificar_assinatura(tx.chave_publica, tx.dados_para_assinar(), tx.assinatura):
        return False, "Assinatura invalida"

    if cadeia.eleitor_ja_votou(blocos, tx.chave_publica, tx.id_votacao):
        return False, "Eleitor ja votou nesta votacao (na cadeia)"

    for pendente in mempool_txs:
        if pendente.chave_publica == tx.chave_publica and pendente.id_votacao == tx.id_votacao:
            return False, "Eleitor ja tem voto pendente nesta votacao (na mempool)"

    if caminho_votacoes is not None:
        from sistema.votacao import chave_autorizada, opcoes_disponiveis, votacao_ativa
        if not votacao_ativa(tx.id_votacao, caminho=caminho_votacoes):
            return False, "Votacao nao esta ativa ou fora do periodo"
        if not chave_autorizada(tx.id_votacao, tx.chave_publica, caminho=caminho_votacoes):
            return False, "Eleitor nao autorizado nesta votacao"
        if tx.escolha not in opcoes_disponiveis(tx.id_votacao, caminho=caminho_votacoes):
            return False, "Opcao invalida para esta votacao"

    return True, ""


def _sessoes_por_id(caminho_votacoes: str) -> dict:
    from sistema.votacao import obter_todas_votacoes_dict
    return {v["id_votacao"]: v for v in obter_todas_votacoes_dict(caminho=caminho_votacoes)}


def _validar_votos(transacoes: List[Transacao], sessoes: dict, ja_votaram: set) -> tuple[bool, str]:
    # ja_votaram e atualizado conforme os votos sao aceitos, para pegar voto duplo no mesmo bloco
    for tx in transacoes:
        sessao = sessoes.get(tx.id_votacao)
        if sessao is None:
            return False, f"Votacao desconhecida neste no: {tx.id_votacao}"
        if tx.escolha not in sessao["opcoes"]:
            return False, f"Opcao invalida na votacao {tx.id_votacao}: {tx.escolha}"
        if tx.chave_publica not in sessao["chaves_autorizadas"]:
            return False, f"Eleitor nao autorizado na votacao {tx.id_votacao}"
        eleitor = (tx.chave_publica, tx.id_votacao)
        if eleitor in ja_votaram:
            return False, f"Voto duplo na votacao {tx.id_votacao}: {tx.calcular_hash()}"
        ja_votaram.add(eleitor)
    return True, ""


def validar_votos_do_bloco(bloco: Bloco, blocos: List[Bloco], caminho_votacoes: str) -> tuple[bool, str]:
    ja_votaram = {(tx.chave_publica, tx.id_votacao) for b in blocos for tx in b.transacoes}
    return _validar_votos(bloco.transacoes, _sessoes_por_id(caminho_votacoes), ja_votaram)


def validar_votos_da_cadeia(blocos: List[Bloco], caminho_votacoes: str) -> tuple[bool, str]:
    # Mesmas regras de validar_votos_do_bloco aplicadas a cadeia inteira (usado no consenso)
    sessoes = _sessoes_por_id(caminho_votacoes)
    ja_votaram = set()
    for bloco in blocos:
        valido, motivo = _validar_votos(bloco.transacoes, sessoes, ja_votaram)
        if not valido:
            return False, f"Bloco {bloco.indice}: {motivo}"
    return True, ""


def validar_bloco(bloco: Bloco, bloco_anterior: Bloco) -> tuple[bool, str]:
    """
    Valida um bloco recebido de outro no.

    Checks:
    1. Indice = anterior + 1
    2. hash_anterior = hash_atual do anterior
    3-5. Conteudo do bloco (ver validar_conteudo_bloco)
    """
    if bloco.indice != bloco_anterior.indice + 1:
        return False, f"Indice incorreto: esperado {bloco_anterior.indice + 1}, recebido {bloco.indice}"

    if bloco.hash_anterior != bloco_anterior.hash_atual:
        return False, "Hash anterior nao confere"

    return validar_conteudo_bloco(bloco)


def validar_conteudo_bloco(bloco: Bloco) -> tuple[bool, str]:
    """
    Checagens que nao dependem da cadeia local. Usada antes de ressincronizar por
    causa de um bloco que nao encaixa, para um peer nao forcar o download da cadeia
    mandando bloco invalido.

    3. Hash recalculado correto
    4. PoW valido (leading zeros)
    5. Todas transacoes no bloco tem assinatura valida
    """
    if bloco.hash_atual != bloco.gerar_hash():
        return False, "Hash do bloco nao confere"

    if bloco.dificuldade < mineracao.DIFICULDADE_MINIMA:
        return False, f"Dificuldade abaixo do minimo ({mineracao.DIFICULDADE_MINIMA})"

    prefixo = "0" * bloco.dificuldade
    if not bloco.hash_atual.startswith(prefixo):
        return False, "Proof-of-Work invalido"

    for tx in bloco.transacoes:
        if not verificar_assinatura(tx.chave_publica, tx.dados_para_assinar(), tx.assinatura):
            return False, f"Transacao com assinatura invalida: {tx.calcular_hash()}"

    return True, ""
