import secrets
import threading
import time

DURACAO_PADRAO = 8 * 60 * 60  # 8 horas


class RegistroSessoes:

    def __init__(self, duracao: int = DURACAO_PADRAO):
        self.duracao = duracao
        self._lock = threading.Lock()
        self._sessoes: dict[str, tuple[str, float]] = {}

    def criar(self, login: str) -> str:
        token = secrets.token_hex(32)
        with self._lock:
            self._sessoes[token] = (login, time.time() + self.duracao)
        return token

    def obter(self, token: str) -> str | None:
        with self._lock:
            sessao = self._sessoes.get(token)
            if sessao is None:
                return None
            login, expira_em = sessao
            if expira_em < time.time():
                del self._sessoes[token]
                return None
            return login

    def remover(self, token: str):
        with self._lock:
            self._sessoes.pop(token, None)

    def quantidade(self) -> int:
        with self._lock:
            return len(self._sessoes)