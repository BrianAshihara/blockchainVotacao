### arquivo: main.py
### CLI adaptado para comunicar com o no local via HTTP

import os
import typer
import requests

from sistema.autenticacao import autenticar, tipo_usuario, cadastrar_usuario, obter_chaves_usuario, listar_eleitores
from sistema.votacao import criar_votacao, listar_votacoes, encerrar_votacao, autorizar_eleitor, eleitor_autorizado, votacao_ativa, opcoes_disponiveis, obter_votacao_dict
from sistema.relatorio import exportar_csv
from core.transacao import Transacao
from core.cripto import assinar

app = typer.Typer()

# Endereco do no (configuravel via variavel de ambiente NODE_URL)
NODE_URL = os.environ.get("NODE_URL", "http://localhost:5000")


def _node_url():
    return NODE_URL


@app.command()
def login():
    """
    Realiza login e redireciona para o menu do tipo de usuario.
    """
    login_input = typer.prompt("Login")
    senha = typer.prompt("Senha", hide_input=True)

    if not autenticar(login_input, senha):
        typer.echo("Login ou senha invalidos.")
        raise typer.Exit()

    tipo = tipo_usuario(login_input)
    typer.echo(f"Bem-vindo, {login_input} ({tipo})")

    if tipo == "admin":
        menu_admin(login_input)
    elif tipo == "eleitor":
        menu_eleitor(login_input)
    elif tipo == "auditor":
        menu_auditor()
    else:
        typer.echo("Tipo de usuario desconhecido.")
        raise typer.Exit()


def exibir_votacoes(apenas_ativas=False):
    votacoes = listar_votacoes(apenas_ativas=apenas_ativas)
    if not votacoes:
        typer.echo("Nenhuma votacao disponivel.")
    for vid, nome in votacoes:
        typer.echo(f"ID: {vid} | Nome: {nome}")


def menu_admin(login_input):
    while True:
        opcao = typer.prompt(
            "\n[Admin] Escolha uma opcao:\n"
            "1 - Cadastrar usuario\n"
            "2 - Criar votacao\n"
            "3 - Encerrar votacao\n"
            "4 - Autorizar eleitor\n"
            "5 - Minerar bloco\n"
            "6 - Info do no\n"
            "0 - Sair\n"
            "Opcao"
        )

        if opcao == "1":
            novo_login = typer.prompt("Login do novo usuario")
            senha = typer.prompt("Senha")
            tipo = typer.prompt("Tipo (admin, eleitor, auditor)")
            if cadastrar_usuario(novo_login, senha, tipo):
                typer.echo("Usuario cadastrado com sucesso.")
            else:
                typer.echo("Usuario ja existe.")
        elif opcao == "2":
            id_votacao = typer.prompt("ID da nova votacao")
            nome_votacao = typer.prompt("Nome da votacao")
            opcoes = typer.prompt("Opcoes separadas por virgula").split(",")
            id_votacao = id_votacao.strip()
            opcoes_lista = [o.strip() for o in opcoes]
            if criar_votacao(id_votacao, nome_votacao.strip(), opcoes_lista):
                typer.echo("Votacao criada.")
                # Propagar para peers
                dados_votacao = obter_votacao_dict(id_votacao)
                if dados_votacao:
                    try:
                        requests.post(f"{_node_url()}/votacao/propagar", json=dados_votacao, timeout=5)
                    except requests.exceptions.ConnectionError:
                        typer.echo("Aviso: no local nao esta rodando, votacao nao propagada.")
            else:
                typer.echo("Votacao ja existe.")
        elif opcao == "3":
            exibir_votacoes(apenas_ativas=True)
            id_votacao = typer.prompt("ID da votacao a encerrar")
            if encerrar_votacao(id_votacao):
                typer.echo("Votacao encerrada.")
                # Propagar encerramento para peers
                dados_votacao = obter_votacao_dict(id_votacao)
                if dados_votacao:
                    try:
                        requests.post(f"{_node_url()}/votacao/propagar", json=dados_votacao, timeout=5)
                    except requests.exceptions.ConnectionError:
                        typer.echo("Aviso: no local nao esta rodando, encerramento nao propagado.")
            else:
                typer.echo("Votacao nao encontrada.")
        elif opcao == "4":
            exibir_votacoes(apenas_ativas=True)
            id_votacao = typer.prompt("ID da votacao")

            eleitores = listar_eleitores()
            if not eleitores:
                typer.echo("Nenhum eleitor cadastrado.")
                continue
            typer.echo("Eleitores cadastrados:")
            for eleitor in eleitores:
                typer.echo(f"- {eleitor}")

            eleitor_login = typer.prompt("Login do eleitor")
            if autorizar_eleitor(id_votacao, eleitor_login):
                typer.echo("Eleitor autorizado.")
            else:
                typer.echo("Erro ao autorizar eleitor.")
        elif opcao == "5":
            try:
                resp = requests.post(f"{_node_url()}/minerar", timeout=120)
                dados = resp.json()
                if resp.status_code == 201:
                    typer.echo(f"Bloco minerado! Indice: {dados['bloco']['indice']}")
                else:
                    typer.echo(f"Erro: {dados.get('erro', 'desconhecido')}")
            except requests.exceptions.ConnectionError:
                typer.echo("Erro: no local nao esta rodando.")
        elif opcao == "6":
            try:
                resp = requests.get(f"{_node_url()}/no/info", timeout=5)
                info = resp.json()
                typer.echo(f"\nID do no: {info['id_no']}")
                typer.echo(f"Porta: {info['porta']}")
                typer.echo(f"Comprimento da chain: {info['comprimento_chain']}")
                typer.echo(f"Transacoes pendentes: {info['transacoes_pendentes']}")
                typer.echo(f"Peers conectados: {info['peers']}")
            except requests.exceptions.ConnectionError:
                typer.echo("Erro: no local nao esta rodando.")
        elif opcao == "0":
            break


def menu_eleitor(login_input):
    while True:
        opcao = typer.prompt(
            "\n[Eleitor] Escolha uma opcao:\n"
            "1 - Votar\n"
            "0 - Sair\n"
            "Opcao"
        )

        if opcao == "1":
            exibir_votacoes(apenas_ativas=True)
            id_votacao = typer.prompt("ID da votacao")
            if not votacao_ativa(id_votacao):
                typer.echo("Votacao nao esta ativa.")
                continue

            if not eleitor_autorizado(id_votacao, login_input):
                typer.echo("Voce nao esta autorizado a votar.")
                continue

            opcoes = opcoes_disponiveis(id_votacao)
            for i, opc in enumerate(opcoes):
                typer.echo(f"{i + 1} - {opc}")
            escolha = typer.prompt("Digite o numero da sua escolha")

            try:
                escolha = int(escolha)
                opcao_escolhida = opcoes[escolha - 1]
            except (ValueError, IndexError):
                typer.echo("Opcao invalida.")
                continue

            # Obter chaves do eleitor
            chaves = obter_chaves_usuario(login_input)
            if chaves is None:
                typer.echo("Erro: chaves do eleitor nao encontradas. Recadastre o usuario.")
                continue

            chave_privada, chave_publica = chaves

            # Assinar transacao localmente (chave privada nunca sai do CLI)
            tx = Transacao(
                id_votacao=id_votacao,
                chave_publica=chave_publica,
                escolha=opcao_escolhida
            )
            tx.assinatura = assinar(chave_privada, tx.dados_para_assinar())

            # Enviar transacao ja assinada para o no
            try:
                resp = requests.post(f"{_node_url()}/transacao", json=tx.to_dict(), timeout=10)
                dados = resp.json()
                if resp.status_code == 201:
                    typer.echo("Voto registrado com sucesso.")
                else:
                    typer.echo(f"Erro: {dados.get('erro', 'desconhecido')}")
            except requests.exceptions.ConnectionError:
                typer.echo("Erro: no local nao esta rodando. Inicie com run_node.py.")
        elif opcao == "0":
            break


def menu_auditor():
    while True:
        opcao = typer.prompt(
            "\n[Auditor] Escolha uma opcao:\n"
            "1 - Ver resultado de votacao\n"
            "2 - Exportar relatorio CSV\n"
            "3 - Verificar integridade da chain\n"
            "0 - Sair\n"
            "Opcao"
        )

        if opcao == "1":
            exibir_votacoes()
            id_votacao = typer.prompt("ID da votacao")
            if not votacao_ativa(id_votacao):
                try:
                    resp = requests.get(f"{_node_url()}/votacao/relatorio/{id_votacao}", timeout=10)
                    relatorio = resp.json()
                    typer.echo("\nResultado Final:")
                    for opc, total in relatorio["detalhes"].items():
                        typer.echo(f"{opc}: {total} voto(s)")
                    typer.echo(f"\nVencedor: {relatorio['vencedor']}")
                except requests.exceptions.ConnectionError:
                    typer.echo("Erro: no local nao esta rodando.")
            else:
                typer.echo("Votacao ainda esta ativa.")
        elif opcao == "2":
            exibir_votacoes()
            id_votacao = typer.prompt("ID da votacao")
            try:
                resp = requests.get(f"{_node_url()}/votacao/relatorio/{id_votacao}", timeout=10)
                if resp.status_code == 200:
                    # Usa o relatorio module pra exportar CSV localmente
                    # mas precisa dos blocos -- busca da API
                    resp_chain = requests.get(f"{_node_url()}/chain", timeout=10)
                    from core.bloco import Bloco
                    blocos = [Bloco.from_dict(b) for b in resp_chain.json()["blocos"]]
                    caminho = exportar_csv(blocos, id_votacao)
                    if caminho:
                        typer.echo(f"Relatorio exportado para {caminho}")
                    else:
                        typer.echo("Erro ao exportar relatorio.")
            except requests.exceptions.ConnectionError:
                typer.echo("Erro: no local nao esta rodando.")
        elif opcao == "3":
            try:
                resp = requests.get(f"{_node_url()}/chain/integridade", timeout=10)
                dados = resp.json()
                if dados["valida"]:
                    typer.echo("Chain integra e valida.")
                else:
                    typer.echo("ALERTA: Chain com problemas de integridade!")
            except requests.exceptions.ConnectionError:
                typer.echo("Erro: no local nao esta rodando.")
        elif opcao == "0":
            break


if __name__ == "__main__":
    while True:
        try:
            login()
        except typer.Exit:
            break
