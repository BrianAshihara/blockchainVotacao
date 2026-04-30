### arquivo: main.py
### CLI adaptado para comunicar com o no local via HTTP

import os
import typer
import requests
from datetime import datetime, timezone

from sistema.autenticacao import (autenticar, tipo_usuario, obter_chaves_usuario, listar_eleitores,
                                  autorregistrar_eleitor, promover_para_admin, listar_admins)
from sistema.votacao import (criar_votacao, listar_votacoes, encerrar_votacao, autorizar_eleitor,
                             eleitor_autorizado, votacao_ativa, opcoes_disponiveis, obter_votacao_dict,
                             listar_votacoes_eleitor)
from core.transacao import Transacao
from core.cripto import assinar

app = typer.Typer()

# Endereco do no (configuravel via variavel de ambiente NODE_URL)
NODE_URL = os.environ.get("NODE_URL", "http://localhost:5000")


def _node_url():
    return NODE_URL


def autorregistrar_flow():
    """Self-registration flow para novos eleitores."""
    typer.echo("\n=== Auto-cadastro de Eleitor ===")
    novo_login = typer.prompt("Escolha um login").strip()
    if not novo_login or novo_login.upper() == "REGISTRAR":
        typer.echo("Login invalido.")
        return
    senha = typer.prompt("Escolha uma senha", hide_input=True)
    senha_conf = typer.prompt("Confirme a senha", hide_input=True)
    if senha != senha_conf:
        typer.echo("Senhas nao conferem.")
        return
    if autorregistrar_eleitor(novo_login, senha):
        typer.echo(f"Eleitor '{novo_login}' cadastrado com sucesso. Faca login para continuar.")
    else:
        typer.echo("Login ja existe. Tente outro.")


@app.command()
def login():
    """
    Realiza login e redireciona para o menu do tipo de usuario.
    Digite REGISTRAR no campo login para se cadastrar como eleitor.
    """
    login_input = typer.prompt("Login (ou 'REGISTRAR' para se cadastrar)").strip()

    if login_input.upper() == "REGISTRAR":
        autorregistrar_flow()
        return

    senha = typer.prompt("Senha", hide_input=True)

    if not autenticar(login_input, senha):
        typer.echo("Login ou senha invalidos.")
        raise typer.Exit()

    tipo = tipo_usuario(login_input)
    typer.echo(f"Bem-vindo, {login_input} ({tipo})")

    if tipo in ("master", "admin"):
        menu_admin(login_input)
    elif tipo == "eleitor":
        menu_eleitor(login_input)
    else:
        typer.echo("Tipo de usuario nao suportado. Contate um admin.")
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
            "1 - Promover eleitor para admin\n"
            "2 - Criar votacao\n"
            "3 - Encerrar votacao\n"
            "4 - Autorizar eleitor\n"
            "5 - Minerar bloco\n"
            "6 - Info do no\n"
            "7 - Ver relatorio de votacao encerrada\n"
            "0 - Sair\n"
            "Opcao"
        )

        if opcao == "1":
            eleitores = listar_eleitores()
            if not eleitores:
                typer.echo("Nenhum eleitor disponivel para promocao.")
                continue
            typer.echo("Eleitores cadastrados:")
            for e in eleitores:
                typer.echo(f"- {e}")
            admins_atuais = listar_admins()
            if admins_atuais:
                typer.echo(f"\nAdmins atuais: {', '.join(admins_atuais)}")
            alvo = typer.prompt("Login do eleitor a promover").strip()
            if promover_para_admin(alvo):
                typer.echo(f"Eleitor '{alvo}' promovido a admin.")
            else:
                typer.echo("Nao foi possivel promover (usuario inexistente, ja e admin, ou e master).")
        elif opcao == "2":
            id_votacao = typer.prompt("ID da nova votacao")
            nome_votacao = typer.prompt("Nome da votacao")
            opcoes = typer.prompt("Opcoes separadas por virgula").split(",")
            inicio_str = typer.prompt("Data/hora de inicio (YYYY-MM-DD HH:MM, Enter para agora)", default="")
            fim_str = typer.prompt("Data/hora de fim (YYYY-MM-DD HH:MM, Enter para sem limite)", default="")

            inicio_iso = None
            if inicio_str.strip():
                try:
                    dt = datetime.strptime(inicio_str.strip(), "%Y-%m-%d %H:%M")
                    inicio_iso = dt.replace(tzinfo=timezone.utc).isoformat()
                except ValueError:
                    typer.echo("Formato de data invalido. Use YYYY-MM-DD HH:MM")
                    continue

            fim_iso = None
            if fim_str.strip():
                try:
                    dt = datetime.strptime(fim_str.strip(), "%Y-%m-%d %H:%M")
                    fim_iso = dt.replace(tzinfo=timezone.utc).isoformat()
                except ValueError:
                    typer.echo("Formato de data invalido. Use YYYY-MM-DD HH:MM")
                    continue

            id_votacao = id_votacao.strip()
            opcoes_lista = [o.strip() for o in opcoes]
            if criar_votacao(id_votacao, nome_votacao.strip(), opcoes_lista,
                             inicio=inicio_iso, fim=fim_iso):
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
            # Minerar votos pendentes antes de encerrar
            try:
                resp = requests.post(f"{_node_url()}/minerar", timeout=120)
                if resp.status_code == 201:
                    typer.echo("Bloco minerado com votos pendentes antes do encerramento.")
            except requests.exceptions.ConnectionError:
                pass
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
        elif opcao == "7":
            exibir_votacoes()
            id_votacao = typer.prompt("ID da votacao")
            try:
                resp = requests.get(f"{_node_url()}/votacao/relatorio/{id_votacao}", timeout=10)
                if resp.status_code == 200:
                    relatorio = resp.json()
                    typer.echo(f"\nRelatorio: {relatorio.get('nome_votacao', id_votacao)}")
                    typer.echo(f"Inicio: {relatorio.get('inicio', 'N/A')}")
                    typer.echo(f"Fim: {relatorio.get('fim', 'N/A')}")
                    typer.echo(f"Eleitores autorizados: {relatorio.get('total_eleitores_autorizados', 'N/A')}")
                    typer.echo(f"Votos confirmados: {relatorio.get('total_votos_confirmados', 0)}")
                    typer.echo(f"Blocos com votos: {relatorio.get('blocos_com_votos', 0)}")
                    typer.echo(f"Hash ultimo bloco: {relatorio.get('hash_ultimo_bloco_com_votos', 'N/A')}")
                    typer.echo("\nResultados:")
                    for opc, info in relatorio.get("detalhes", {}).items():
                        if isinstance(info, dict):
                            typer.echo(f"  {opc}: {info['votos']} voto(s) ({info['percentual']}%)")
                        else:
                            typer.echo(f"  {opc}: {info} voto(s)")
                    typer.echo(f"\nVencedor: {relatorio.get('vencedor', 'N/A')}")
                elif resp.status_code == 403:
                    typer.echo("Votacao ainda esta ativa.")
                else:
                    typer.echo(f"Erro: {resp.json().get('erro', 'desconhecido')}")
            except requests.exceptions.ConnectionError:
                typer.echo("Erro: no local nao esta rodando.")
        elif opcao == "0":
            break


def menu_eleitor(login_input):
    while True:
        opcao = typer.prompt(
            "\n[Eleitor] Escolha uma opcao:\n"
            "1 - Votar\n"
            "2 - Minhas votacoes ativas\n"
            "3 - Ver resultado (votacao encerrada)\n"
            "0 - Sair\n"
            "Opcao"
        )

        if opcao == "1":
            # Mostrar apenas votacoes ativas onde o eleitor esta autorizado
            votacoes_eleitor = listar_votacoes_eleitor(login_input, apenas_ativas=True)
            if not votacoes_eleitor:
                typer.echo("Nenhuma votacao ativa disponivel para voce.")
                continue
            for vid, nome in votacoes_eleitor:
                typer.echo(f"ID: {vid} | Nome: {nome}")

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

            chaves = obter_chaves_usuario(login_input)
            if chaves is None:
                typer.echo("Erro: chaves do eleitor nao encontradas. Recadastre o usuario.")
                continue

            chave_privada, chave_publica = chaves

            tx = Transacao(
                id_votacao=id_votacao,
                chave_publica=chave_publica,
                escolha=opcao_escolhida
            )
            tx.assinatura = assinar(chave_privada, tx.dados_para_assinar())

            try:
                resp = requests.post(f"{_node_url()}/transacao", json=tx.to_dict(), timeout=10)
                dados = resp.json()
                if resp.status_code == 201:
                    typer.echo("\nSeu voto foi computado.")
                    typer.echo(f"Comprovante (hash da transacao): {dados.get('tx_hash')}")
                    try:
                        cont_resp = requests.get(f"{_node_url()}/votacao/contagem/{id_votacao}", timeout=5)
                        if cont_resp.status_code == 200:
                            total = cont_resp.json().get("total_votos_confirmados", 0)
                            typer.echo(f"Total de votos confirmados nesta sessao: {total}")
                    except requests.exceptions.ConnectionError:
                        pass
                else:
                    typer.echo(f"Erro: {dados.get('erro', 'desconhecido')}")
            except requests.exceptions.ConnectionError:
                typer.echo("Erro: no local nao esta rodando. Inicie com run_node.py.")
        elif opcao == "2":
            votacoes_eleitor = listar_votacoes_eleitor(login_input, apenas_ativas=True)
            if not votacoes_eleitor:
                typer.echo("Nenhuma votacao ativa disponivel para voce.")
            else:
                for vid, nome in votacoes_eleitor:
                    typer.echo(f"ID: {vid} | Nome: {nome}")
        elif opcao == "3":
            votacoes_eleitor = listar_votacoes_eleitor(login_input, apenas_ativas=False)
            encerradas = []
            for vid, nome in votacoes_eleitor:
                if not votacao_ativa(vid):
                    encerradas.append((vid, nome))
            if not encerradas:
                typer.echo("Nenhuma votacao encerrada disponivel.")
                continue
            for vid, nome in encerradas:
                typer.echo(f"ID: {vid} | Nome: {nome}")
            id_votacao = typer.prompt("ID da votacao")
            try:
                resp = requests.get(f"{_node_url()}/votacao/relatorio/{id_votacao}", timeout=10)
                if resp.status_code == 200:
                    relatorio = resp.json()
                    typer.echo(f"\nRelatorio: {relatorio.get('nome_votacao', id_votacao)}")
                    typer.echo(f"Votos confirmados: {relatorio.get('total_votos_confirmados', 0)}")
                    typer.echo("\nResultados:")
                    for opc, info in relatorio.get("detalhes", {}).items():
                        if isinstance(info, dict):
                            typer.echo(f"  {opc}: {info['votos']} voto(s) ({info['percentual']}%)")
                        else:
                            typer.echo(f"  {opc}: {info} voto(s)")
                    typer.echo(f"\nVencedor: {relatorio.get('vencedor', 'N/A')}")
                elif resp.status_code == 403:
                    typer.echo("Votacao ainda esta ativa.")
                else:
                    typer.echo(f"Erro: {resp.json().get('erro', 'desconhecido')}")
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
