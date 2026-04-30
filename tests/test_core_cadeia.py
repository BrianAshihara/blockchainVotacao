"""
Testes para core/cadeia.py

Cobre criacao do bloco genesis, verificacao de integridade da cadeia,
deteccao de voto duplo, contagem de votos e funcoes utilitarias.
"""

from core.cadeia import (
    criar_bloco_genesis, verificar_integridade, eleitor_ja_votou,
    gerar_relatorio, ultimo_bloco, comprimento, contar_votos
)
from core.mineracao import minerar_bloco

DIFICULDADE_TESTE = 1


# ---- criar_bloco_genesis ----

def test_criar_bloco_genesis_indice_zero():
    g = criar_bloco_genesis(dificuldade=DIFICULDADE_TESTE)
    assert g.indice == 0


def test_criar_bloco_genesis_timestamp_zero():
    g = criar_bloco_genesis(dificuldade=DIFICULDADE_TESTE)
    assert g.timestamp == 0.0


def test_criar_bloco_genesis_hash_anterior_zeros():
    g = criar_bloco_genesis(dificuldade=DIFICULDADE_TESTE)
    assert g.hash_anterior == "0" * 64


def test_criar_bloco_genesis_sem_transacoes():
    g = criar_bloco_genesis(dificuldade=DIFICULDADE_TESTE)
    assert g.transacoes == []


def test_criar_bloco_genesis_dificuldade_customizada():
    g = criar_bloco_genesis(dificuldade=2)
    assert g.dificuldade == 2


def test_criar_bloco_genesis_deterministico():
    g1 = criar_bloco_genesis(dificuldade=DIFICULDADE_TESTE)
    g2 = criar_bloco_genesis(dificuldade=DIFICULDADE_TESTE)
    assert g1.hash_atual == g2.hash_atual


# ---- verificar_integridade ----

def test_verificar_integridade_chain_so_genesis(chain_com_genesis):
    assert verificar_integridade(chain_com_genesis) is True


def test_verificar_integridade_chain_valida(chain_com_dois_blocos):
    assert verificar_integridade(chain_com_dois_blocos) is True


def test_verificar_integridade_hash_anterior_adulterado(chain_com_um_bloco):
    chain_com_um_bloco[1].hash_anterior = "f" * 64
    assert verificar_integridade(chain_com_um_bloco) is False


def test_verificar_integridade_hash_atual_adulterado(chain_com_um_bloco):
    chain_com_um_bloco[1].hash_atual = "f" * 64
    assert verificar_integridade(chain_com_um_bloco) is False


def test_verificar_integridade_chain_vazia():
    assert verificar_integridade([]) is True


# ---- eleitor_ja_votou ----

def test_eleitor_ja_votou_sim(chain_com_um_bloco, par_chaves):
    _, pk = par_chaves
    assert eleitor_ja_votou(chain_com_um_bloco, pk, "vot1") is True


def test_eleitor_ja_votou_nao(chain_com_um_bloco):
    assert eleitor_ja_votou(chain_com_um_bloco, "pk_inexistente", "vot1") is False


def test_eleitor_ja_votou_outra_votacao(chain_com_um_bloco, par_chaves):
    _, pk = par_chaves
    assert eleitor_ja_votou(chain_com_um_bloco, pk, "vot_outra") is False


# ---- gerar_relatorio ----

def test_gerar_relatorio_contagem_correta(chain_com_dois_blocos):
    relatorio = gerar_relatorio(chain_com_dois_blocos, "vot1")
    assert relatorio["total"] == 2
    # Novo formato: detalhes[opcao] e dict com votos e percentual
    assert relatorio["detalhes"]["Alice"]["votos"] == 1
    assert relatorio["detalhes"]["Bob"]["votos"] == 1
    assert relatorio["detalhes"]["Alice"]["percentual"] == 50.0
    assert relatorio["detalhes"]["Bob"]["percentual"] == 50.0


def test_gerar_relatorio_total_votos_confirmados(chain_com_dois_blocos):
    """Novo campo total_votos_confirmados deve coincidir com total."""
    relatorio = gerar_relatorio(chain_com_dois_blocos, "vot1")
    assert relatorio["total_votos_confirmados"] == 2


def test_gerar_relatorio_blocos_com_votos(chain_com_dois_blocos):
    """Cada bloco com votos da sessao deve ser contado."""
    relatorio = gerar_relatorio(chain_com_dois_blocos, "vot1")
    # chain_com_dois_blocos tem 2 blocos minerados, cada um com uma tx vot1
    assert relatorio["blocos_com_votos"] == 2


def test_gerar_relatorio_hash_ultimo_bloco_com_votos(chain_com_dois_blocos):
    relatorio = gerar_relatorio(chain_com_dois_blocos, "vot1")
    # ultimo bloco com voto e o ultimo da chain
    assert relatorio["hash_ultimo_bloco_com_votos"] == chain_com_dois_blocos[-1].hash_atual


def test_gerar_relatorio_sem_votos(chain_com_genesis):
    relatorio = gerar_relatorio(chain_com_genesis, "vot_inexistente")
    assert relatorio["vencedor"] is None
    assert relatorio["total"] == 0
    assert relatorio["total_votos_confirmados"] == 0
    assert relatorio["detalhes"] == {}
    assert relatorio["blocos_com_votos"] == 0
    assert relatorio["hash_ultimo_bloco_com_votos"] is None


def test_gerar_relatorio_com_dados_votacao_inclui_metadados(chain_com_dois_blocos):
    """Quando dados_votacao e fornecido, relatorio deve incluir metadados da sessao."""
    dados = {
        "nome": "Eleicao Teste",
        "inicio": "2026-03-20T10:00:00+00:00",
        "fim": "2026-03-20T18:00:00+00:00",
        "eleitores": ["a", "b", "c"]
    }
    relatorio = gerar_relatorio(chain_com_dois_blocos, "vot1", dados_votacao=dados)
    assert relatorio["nome_votacao"] == "Eleicao Teste"
    assert relatorio["inicio"] == "2026-03-20T10:00:00+00:00"
    assert relatorio["fim"] == "2026-03-20T18:00:00+00:00"
    assert relatorio["total_eleitores_autorizados"] == 3


def test_gerar_relatorio_sem_dados_votacao_nao_inclui_metadados(chain_com_dois_blocos):
    relatorio = gerar_relatorio(chain_com_dois_blocos, "vot1")
    assert "nome_votacao" not in relatorio
    assert "total_eleitores_autorizados" not in relatorio


def test_gerar_relatorio_vencedor_correto(
    bloco_genesis, par_chaves, par_chaves_secundario, par_chaves_terceiro,
    fazer_transacao_assinada
):
    sk1, pk1 = par_chaves
    sk2, pk2 = par_chaves_secundario
    sk3, pk3 = par_chaves_terceiro
    tx1 = fazer_transacao_assinada(sk1, pk1, escolha="Alice", timestamp=1.0)
    tx2 = fazer_transacao_assinada(sk2, pk2, escolha="Alice", timestamp=2.0)
    tx3 = fazer_transacao_assinada(sk3, pk3, escolha="Bob", timestamp=3.0)
    b1 = minerar_bloco(bloco_genesis, [tx1, tx2, tx3], dificuldade=DIFICULDADE_TESTE)
    chain = [bloco_genesis, b1]
    relatorio = gerar_relatorio(chain, "vot1")
    assert relatorio["vencedor"] == "Alice"
    assert relatorio["total"] == 3
    # Percentual deve ser 66.67% para Alice (2/3) e 33.33% para Bob (1/3)
    assert relatorio["detalhes"]["Alice"]["percentual"] == 66.67
    assert relatorio["detalhes"]["Bob"]["percentual"] == 33.33


# ---- contar_votos ----

def test_contar_votos_chain_vazia(chain_com_genesis):
    assert contar_votos(chain_com_genesis, "vot1") == 0


def test_contar_votos_com_votos(chain_com_dois_blocos):
    assert contar_votos(chain_com_dois_blocos, "vot1") == 2


def test_contar_votos_votacao_inexistente(chain_com_dois_blocos):
    assert contar_votos(chain_com_dois_blocos, "vot_outra") == 0


def test_contar_votos_mais_leve_que_relatorio(chain_com_dois_blocos):
    """contar_votos deve retornar apenas int, nao calcular detalhes/percentuais."""
    total = contar_votos(chain_com_dois_blocos, "vot1")
    assert isinstance(total, int)
    assert total == 2


# ---- ultimo_bloco / comprimento ----

def test_ultimo_bloco(chain_com_dois_blocos):
    ub = ultimo_bloco(chain_com_dois_blocos)
    assert ub.indice == 2


def test_comprimento(chain_com_dois_blocos):
    assert comprimento(chain_com_dois_blocos) == 3
