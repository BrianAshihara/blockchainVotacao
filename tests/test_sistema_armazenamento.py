# Testes para sistema/armazenamento.py

import json
import os
import threading

import pytest

from sistema.armazenamento import carregar_json, salvar_json, travar


def test_salvar_e_carregar(tmp_path):
    caminho = str(tmp_path / "dados.json")
    salvar_json(caminho, {"a": 1})
    assert carregar_json(caminho, {}) == {"a": 1}


def test_carregar_arquivo_inexistente_retorna_padrao(tmp_path):
    assert carregar_json(str(tmp_path / "nao_existe.json"), {}) == {}


def test_salvar_cria_diretorio(tmp_path):
    caminho = str(tmp_path / "sub" / "dir" / "dados.json")
    salvar_json(caminho, {"x": True})
    assert os.path.exists(caminho)


def test_salvar_nao_deixa_arquivo_temporario(tmp_path):
    caminho = str(tmp_path / "dados.json")
    salvar_json(caminho, {"a": 1})
    salvar_json(caminho, {"a": 2})
    assert os.listdir(tmp_path) == ["dados.json"]


def test_falha_na_gravacao_preserva_o_arquivo_anterior(tmp_path):
    caminho = str(tmp_path / "dados.json")
    salvar_json(caminho, {"a": 1})
    with pytest.raises(TypeError):
        salvar_json(caminho, {"a": object()})  # nao serializavel: falha no meio do json.dump
    assert carregar_json(caminho, {}) == {"a": 1}
    assert os.listdir(tmp_path) == ["dados.json"]


def test_ler_modificar_gravar_concorrente_nao_perde_nem_corrompe(tmp_path):
    caminho = str(tmp_path / "lista.json")
    salvar_json(caminho, {"itens": []})

    def adicionar(i):
        with travar(caminho):
            dados = carregar_json(caminho, {})
            dados["itens"].append(i)
            salvar_json(caminho, dados)

    threads = [threading.Thread(target=adicionar, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    with open(caminho) as f:
        dados = json.load(f)
    assert sorted(dados["itens"]) == list(range(50))