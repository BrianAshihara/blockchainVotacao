import time
from typing import List

from core.bloco import Bloco
from core.transacao import Transacao


def criar_bloco_genesis(dificuldade: int = 4) -> Bloco:
    """
    Cria bloco genesis (indice 0, sem transacoes).
    Timestamp fixo em 0 para que todos os nos gerem o mesmo genesis.
    """
    return Bloco(
        indice=0,
        timestamp=0.0,
        transacoes=[],
        hash_anterior="0" * 64,
        nonce=0,
        dificuldade=dificuldade
    )


def verificar_integridade(blocos: List[Bloco]) -> bool:
    """
    Valida a cadeia de hashes e PoW.
    Adaptado de blockchain.py Blockchain.verificar_integridade().
    """
    for i in range(1, len(blocos)):
        bloco_atual = blocos[i]
        bloco_anterior = blocos[i - 1]

        if bloco_atual.hash_anterior != bloco_anterior.hash_atual:
            return False

        if bloco_atual.hash_atual != bloco_atual.gerar_hash():
            return False

        prefixo = "0" * bloco_atual.dificuldade
        if not bloco_atual.hash_atual.startswith(prefixo):
            return False

    return True


def eleitor_ja_votou(blocos: List[Bloco], chave_publica: str, id_votacao: str) -> bool:
    """
    Verifica se o eleitor (por chave publica) ja votou em uma votacao especifica.
    Adaptado de blockchain.py Blockchain.eleitor_ja_votou().
    """
    for bloco in blocos:
        for tx in bloco.transacoes:
            if tx.chave_publica == chave_publica and tx.id_votacao == id_votacao:
                return True
    return False


def gerar_relatorio(blocos: List[Bloco], id_votacao: str) -> dict:
    """
    Contabiliza votos para uma votacao especifica.
    Adaptado de blockchain.py Blockchain.gerar_relatorio().
    """
    resultados = {}
    for bloco in blocos:
        for tx in bloco.transacoes:
            if tx.id_votacao == id_votacao:
                escolha = tx.escolha
                resultados[escolha] = resultados.get(escolha, 0) + 1

    if not resultados:
        return {"vencedor": None, "total": 0, "detalhes": {}}

    vencedor = max(resultados, key=resultados.get)
    return {
        "vencedor": vencedor,
        "total": sum(resultados.values()),
        "detalhes": resultados
    }


def ultimo_bloco(blocos: List[Bloco]) -> Bloco:
    """Retorna o ultimo bloco da cadeia."""
    return blocos[-1]


def comprimento(blocos: List[Bloco]) -> int:
    """Retorna o comprimento da cadeia."""
    return len(blocos)
