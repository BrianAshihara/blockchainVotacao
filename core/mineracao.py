import time
from typing import List

from core.bloco import Bloco
from core.transacao import Transacao

DIFICULDADE_PADRAO = 4
MAX_TRANSACOES_POR_BLOCO = 10


def minerar_bloco(bloco_anterior: Bloco, transacoes: List[Transacao],
                  dificuldade: int = DIFICULDADE_PADRAO) -> Bloco:
    """
    Cria e minera um novo bloco com proof-of-work.

    Incrementa nonce ate o hash ter os zeros iniciais exigidos.
    Operacao bloqueante e CPU-intensiva.
    """
    prefixo_alvo = "0" * dificuldade
    novo_bloco = Bloco(
        indice=bloco_anterior.indice + 1,
        timestamp=time.time(),
        transacoes=transacoes,
        hash_anterior=bloco_anterior.hash_atual,
        nonce=0,
        dificuldade=dificuldade
    )

    while not novo_bloco.hash_atual.startswith(prefixo_alvo):
        novo_bloco.nonce += 1
        novo_bloco.hash_atual = novo_bloco.gerar_hash()

    return novo_bloco


def verificar_pow(bloco: Bloco) -> bool:
    """Verifica se o PoW do bloco e valido."""
    prefixo = "0" * bloco.dificuldade
    hash_recalculado = bloco.gerar_hash()
    return (bloco.hash_atual == hash_recalculado and
            hash_recalculado.startswith(prefixo))
