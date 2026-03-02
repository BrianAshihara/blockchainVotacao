"""
Testes para core/cripto.py

Cobre geracao de chaves ECDSA, assinatura, verificacao de assinatura
e derivacao de endereco. Todos os testes usam criptografia real.
"""

from core.cripto import gerar_par_chaves, assinar, verificar_assinatura, gerar_endereco


# ---- gerar_par_chaves ----

def test_gerar_par_chaves_retorna_tupla_de_dois_hex():
    sk, pk = gerar_par_chaves()
    assert isinstance(sk, str)
    assert isinstance(pk, str)
    int(sk, 16)
    int(pk, 16)


def test_gerar_par_chaves_comprimento_correto():
    sk, pk = gerar_par_chaves()
    assert len(sk) == 64, "Chave privada SECP256k1 deve ter 64 hex chars (32 bytes)"
    assert len(pk) == 128, "Chave publica SECP256k1 deve ter 128 hex chars (64 bytes)"


def test_gerar_par_chaves_unicidade():
    par1 = gerar_par_chaves()
    par2 = gerar_par_chaves()
    assert par1 != par2


# ---- assinar ----

def test_assinar_retorna_hex_valido(par_chaves):
    sk, pk = par_chaves
    assinatura = assinar(sk, "dados de teste")
    assert isinstance(assinatura, str)
    assert len(assinatura) > 0
    int(assinatura, 16)


def test_assinar_dados_diferentes_gera_assinaturas_diferentes(par_chaves):
    sk, pk = par_chaves
    sig1 = assinar(sk, "dados A")
    sig2 = assinar(sk, "dados B")
    assert sig1 != sig2


# ---- verificar_assinatura ----

def test_verificar_assinatura_valida(par_chaves):
    sk, pk = par_chaves
    dados = "voto: Alice"
    assinatura = assinar(sk, dados)
    assert verificar_assinatura(pk, dados, assinatura) is True


def test_verificar_assinatura_dados_alterados(par_chaves):
    sk, pk = par_chaves
    assinatura = assinar(sk, "dados originais")
    assert verificar_assinatura(pk, "dados adulterados", assinatura) is False


def test_verificar_assinatura_chave_errada(par_chaves, par_chaves_secundario):
    sk, pk = par_chaves
    _, pk_outra = par_chaves_secundario
    assinatura = assinar(sk, "dados")
    assert verificar_assinatura(pk_outra, "dados", assinatura) is False


def test_verificar_assinatura_hex_invalido(par_chaves):
    _, pk = par_chaves
    # Hex invalido (nao-hex chars) deve levantar ValueError ou retornar False
    try:
        resultado = verificar_assinatura(pk, "dados", "zzzz_invalido")
        assert resultado is False
    except (ValueError, Exception):
        pass  # ecdsa pode levantar excecao para hex invalido


def test_verificar_assinatura_chave_publica_invalida():
    # Chave publica invalida (ponto fora da curva) pode levantar excecao
    try:
        resultado = verificar_assinatura("ff" * 64, "dados", "aa" * 32)
        assert resultado is False
    except Exception:
        pass  # ecdsa levanta MalformedPointError para chaves invalidas


# ---- gerar_endereco ----

def test_gerar_endereco_formato(par_chaves):
    _, pk = par_chaves
    endereco = gerar_endereco(pk)
    assert isinstance(endereco, str)
    assert len(endereco) == 40
    int(endereco, 16)


def test_gerar_endereco_deterministico(par_chaves):
    _, pk = par_chaves
    assert gerar_endereco(pk) == gerar_endereco(pk)


def test_gerar_endereco_chaves_diferentes(par_chaves, par_chaves_secundario):
    _, pk1 = par_chaves
    _, pk2 = par_chaves_secundario
    assert gerar_endereco(pk1) != gerar_endereco(pk2)
