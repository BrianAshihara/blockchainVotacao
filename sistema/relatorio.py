import csv
import os
from typing import List

from core.bloco import Bloco
from core.cadeia import gerar_relatorio


def exportar_csv(blocos: List[Bloco], id_votacao: str, caminho_saida: str = None) -> str | bool:
    """
    Adaptado de sistema.py exportar_csv().
    Agora recebe a lista de blocos diretamente (nao cria instancia de Blockchain).
    """
    if caminho_saida is None:
        caminho_saida = f"data/relatorio_{id_votacao}.csv"

    relatorio = gerar_relatorio(blocos, id_votacao)

    os.makedirs(os.path.dirname(caminho_saida), exist_ok=True)
    with open(caminho_saida, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Opcao", "Total de Votos", "Percentual"])
        for opcao, info in relatorio["detalhes"].items():
            if isinstance(info, dict):
                writer.writerow([opcao, info["votos"], f'{info["percentual"]}%'])
            else:
                writer.writerow([opcao, info, ""])
        writer.writerow([])
        writer.writerow(["Vencedor", relatorio["vencedor"]])
        writer.writerow(["Total de votos", relatorio["total"]])

    return caminho_saida
