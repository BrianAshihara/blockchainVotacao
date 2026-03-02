from typing import List

from core.transacao import Transacao
from core.bloco import Bloco
from core.cripto import verificar_assinatura
from core import cadeia


def validar_transacao(tx: Transacao, blocos: List[Bloco], mempool_txs: List[Transacao]) -> tuple[bool, str]:
    """
    Valida uma transacao antes de aceitar na mempool.

    Checks:
    1. Campos obrigatorios presentes
    2. Assinatura valida
    3. Eleitor nao votou na chain (double-vote)
    4. Eleitor nao tem tx pendente na mempool para mesma votacao
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

    return True, ""


def validar_bloco(bloco: Bloco, bloco_anterior: Bloco) -> tuple[bool, str]:
    """
    Valida um bloco recebido de outro no.

    Checks:
    1. Indice = anterior + 1
    2. hash_anterior = hash_atual do anterior
    3. Hash recalculado correto
    4. PoW valido (leading zeros)
    5. Todas transacoes no bloco tem assinatura valida
    """
    if bloco.indice != bloco_anterior.indice + 1:
        return False, f"Indice incorreto: esperado {bloco_anterior.indice + 1}, recebido {bloco.indice}"

    if bloco.hash_anterior != bloco_anterior.hash_atual:
        return False, "Hash anterior nao confere"

    if bloco.hash_atual != bloco.gerar_hash():
        return False, "Hash do bloco nao confere"

    prefixo = "0" * bloco.dificuldade
    if not bloco.hash_atual.startswith(prefixo):
        return False, "Proof-of-Work invalido"

    for tx in bloco.transacoes:
        if not verificar_assinatura(tx.chave_publica, tx.dados_para_assinar(), tx.assinatura):
            return False, f"Transacao com assinatura invalida: {tx.calcular_hash()}"

    return True, ""
