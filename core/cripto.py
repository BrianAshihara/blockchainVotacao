import hashlib
from ecdsa import SigningKey, VerifyingKey, SECP256k1, BadSignatureError


def gerar_par_chaves() -> tuple[str, str]:
    """
    Gera um par de chaves (privada, publica) como strings hexadecimais.
    """
    sk = SigningKey.generate(curve=SECP256k1)
    vk = sk.get_verifying_key()
    return sk.to_string().hex(), vk.to_string().hex()


def assinar(chave_privada_hex: str, dados: str) -> str:
    """
    Assina os dados com a chave privada. Retorna a assinatura em hex.
    """
    sk = SigningKey.from_string(bytes.fromhex(chave_privada_hex), curve=SECP256k1)
    assinatura = sk.sign(dados.encode("utf-8"))
    return assinatura.hex()


def verificar_assinatura(chave_publica_hex: str, dados: str, assinatura_hex: str) -> bool:
    """
    Verifica se a assinatura e valida para os dados e chave publica.
    """
    try:
        vk = VerifyingKey.from_string(bytes.fromhex(chave_publica_hex), curve=SECP256k1)
        vk.verify(bytes.fromhex(assinatura_hex), dados.encode("utf-8"))
        return True
    except BadSignatureError:
        return False


def gerar_endereco(chave_publica_hex: str) -> str:
    """
    Gera um endereco (identidade do eleitor) a partir da chave publica.
    SHA-256 da chave publica, truncado a 40 chars.
    """
    return hashlib.sha256(chave_publica_hex.encode()).hexdigest()[:40]
