import json
import os
import tempfile
import threading
import time
from contextlib import contextmanager

_travas: dict[str, threading.RLock] = {}
_travas_guarda = threading.Lock()


def _trava(caminho: str) -> threading.RLock:
    chave = os.path.abspath(caminho)
    with _travas_guarda:
        if chave not in _travas:
            _travas[chave] = threading.RLock()
        return _travas[chave]


@contextmanager
def travar(caminho: str):
    with _trava(caminho):
        yield


def carregar_json(caminho: str, padrao):
    with travar(caminho):
        if not os.path.exists(caminho):
            return padrao
        with open(caminho, "r") as f:
            return json.load(f)


def salvar_json(caminho: str, dados, tentativas: int = 5):
    diretorio = os.path.dirname(caminho) or "."
    with travar(caminho):
        os.makedirs(diretorio, exist_ok=True)
        fd, temporario = tempfile.mkstemp(dir=diretorio, prefix=".tmp_", suffix=".json")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(dados, f, indent=4)
            for i in range(tentativas):
                try:
                    os.replace(temporario, caminho)
                    return
                except PermissionError:
                    # no Windows o replace falha se outro processo (ex: a CLI) estiver com o arquivo aberto
                    if i == tentativas - 1:
                        raise
                    time.sleep(0.05)
        finally:
            if os.path.exists(temporario):
                os.remove(temporario)