"""
Testes para sistema/relatorio.py

Cobre geracao de relatorio CSV a partir dos dados da blockchain.
Usa tmp_path para isolamento do arquivo de saida.
"""

import csv
import os

from sistema.relatorio import exportar_csv
from core.mineracao import minerar_bloco

DIFICULDADE_TESTE = 1


# ---- exportar_csv ----

def test_exportar_csv_cria_arquivo(tmp_path, chain_com_um_bloco):
    caminho = str(tmp_path / "relatorio.csv")
    exportar_csv(chain_com_um_bloco, "vot1", caminho_saida=caminho)
    assert os.path.exists(caminho)


def test_exportar_csv_retorna_caminho(tmp_path, chain_com_um_bloco):
    caminho = str(tmp_path / "relatorio.csv")
    resultado = exportar_csv(chain_com_um_bloco, "vot1", caminho_saida=caminho)
    assert resultado == caminho


def test_exportar_csv_cabecalho_correto(tmp_path, chain_com_um_bloco):
    caminho = str(tmp_path / "relatorio.csv")
    exportar_csv(chain_com_um_bloco, "vot1", caminho_saida=caminho)
    with open(caminho, "r") as f:
        reader = csv.reader(f)
        header = next(reader)
    assert header == ["Opcao", "Total de Votos"]


def test_exportar_csv_dados_corretos(tmp_path, chain_com_dois_blocos):
    caminho = str(tmp_path / "relatorio.csv")
    exportar_csv(chain_com_dois_blocos, "vot1", caminho_saida=caminho)
    with open(caminho, "r") as f:
        reader = csv.reader(f)
        linhas = list(reader)
    # header + Alice row + Bob row + empty row + vencedor row + total row
    opcoes_linhas = linhas[1:3]
    opcoes_dict = {row[0]: int(row[1]) for row in opcoes_linhas}
    assert opcoes_dict["Alice"] == 1
    assert opcoes_dict["Bob"] == 1


def test_exportar_csv_vencedor_correto(
    tmp_path, bloco_genesis, par_chaves, par_chaves_secundario,
    par_chaves_terceiro, fazer_transacao_assinada
):
    sk1, pk1 = par_chaves
    sk2, pk2 = par_chaves_secundario
    sk3, pk3 = par_chaves_terceiro
    tx1 = fazer_transacao_assinada(sk1, pk1, escolha="Alice", timestamp=1.0)
    tx2 = fazer_transacao_assinada(sk2, pk2, escolha="Alice", timestamp=2.0)
    tx3 = fazer_transacao_assinada(sk3, pk3, escolha="Bob", timestamp=3.0)
    b1 = minerar_bloco(bloco_genesis, [tx1, tx2, tx3], dificuldade=DIFICULDADE_TESTE)
    chain = [bloco_genesis, b1]

    caminho = str(tmp_path / "relatorio.csv")
    exportar_csv(chain, "vot1", caminho_saida=caminho)
    with open(caminho, "r") as f:
        conteudo = f.read()
    assert "Alice" in conteudo


def test_exportar_csv_total_correto(tmp_path, chain_com_dois_blocos):
    caminho = str(tmp_path / "relatorio.csv")
    exportar_csv(chain_com_dois_blocos, "vot1", caminho_saida=caminho)
    with open(caminho, "r") as f:
        reader = csv.reader(f)
        linhas = list(reader)
    # Ultima linha deve ter total
    ultima = linhas[-1]
    assert ultima[0] == "Total de votos"
    assert int(ultima[1]) == 2


def test_exportar_csv_sem_votos(tmp_path, chain_com_genesis):
    caminho = str(tmp_path / "relatorio.csv")
    exportar_csv(chain_com_genesis, "vot_inexistente", caminho_saida=caminho)
    assert os.path.exists(caminho)
    with open(caminho, "r") as f:
        conteudo = f.read()
    # Deve conter cabecalho e linhas de resumo
    assert "Opcao" in conteudo
    assert "Total de votos" in conteudo
    assert "0" in conteudo


def test_exportar_csv_caminho_customizado(tmp_path, chain_com_genesis):
    caminho = str(tmp_path / "pasta" / "meu_relatorio.csv")
    resultado = exportar_csv(chain_com_genesis, "v1", caminho_saida=caminho)
    assert resultado == caminho
    assert os.path.exists(caminho)
