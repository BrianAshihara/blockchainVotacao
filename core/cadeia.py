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


def gerar_relatorio(blocos: List[Bloco], id_votacao: str, dados_votacao: dict = None) -> dict:
    """
    Contabiliza votos para uma votacao especifica.
    Se dados_votacao fornecido, inclui metadados da sessao no relatorio.
    """
    resultados = {}
    blocos_com_votos = []
    for bloco in blocos:
        bloco_tem_voto = False
        for tx in bloco.transacoes:
            if tx.id_votacao == id_votacao:
                escolha = tx.escolha
                resultados[escolha] = resultados.get(escolha, 0) + 1
                bloco_tem_voto = True
        if bloco_tem_voto:
            blocos_com_votos.append(bloco)

    total = sum(resultados.values())

    if not resultados:
        vencedor = None
        detalhes = {}
    else:
        vencedor = max(resultados, key=resultados.get)
        detalhes = {}
        for opcao, votos in resultados.items():
            detalhes[opcao] = {
                "votos": votos,
                "percentual": round((votos / total) * 100, 2)
            }

    relatorio = {
        "vencedor": vencedor,
        "total": total,
        "total_votos_confirmados": total,
        "detalhes": detalhes,
        "blocos_com_votos": len(blocos_com_votos),
        "hash_ultimo_bloco_com_votos": blocos_com_votos[-1].hash_atual if blocos_com_votos else None
    }

    if dados_votacao:
        relatorio["nome_votacao"] = dados_votacao.get("nome")
        relatorio["inicio"] = dados_votacao.get("inicio")
        relatorio["fim"] = dados_votacao.get("fim")
        relatorio["total_eleitores_autorizados"] = len(dados_votacao.get("eleitores", []))

    return relatorio


def contar_votos(blocos: List[Bloco], id_votacao: str) -> int:
    """Retorna o numero de votos confirmados on-chain para uma votacao."""
    total = 0
    for bloco in blocos:
        for tx in bloco.transacoes:
            if tx.id_votacao == id_votacao:
                total += 1
    return total


def ultimo_bloco(blocos: List[Bloco]) -> Bloco:
    """Retorna o ultimo bloco da cadeia."""
    return blocos[-1]


def comprimento(blocos: List[Bloco]) -> int:
    """Retorna o comprimento da cadeia."""
    return len(blocos)
