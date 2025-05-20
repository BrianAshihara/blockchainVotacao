import typer
from sistema import Sistema
from blockchain import Blockchain

app = typer.Typer()
sistema = Sistema()

@app.command()
def login():
    """
    Realiza login e redireciona para o menu do tipo de usuário.
    """
    login = typer.prompt("Login")
    senha = typer.prompt("Senha", hide_input=True)

    if not sistema.autenticar(login, senha):
        typer.echo("❌ Login ou senha inválidos.")
        raise typer.Exit()

    tipo = sistema.tipo_usuario(login)
    typer.echo(f"✅ Bem-vindo, {login} ({tipo})")

    if tipo == "admin":
        menu_admin(login)
    elif tipo == "eleitor":
        menu_eleitor(login)
    elif tipo == "auditor":
        menu_auditor()
    else:
        typer.echo("❌ Tipo de usuário desconhecido.")
        raise typer.Exit()


def menu_admin(login):
    while True:
        opcao = typer.prompt(
            "\n[Admin] Escolha uma opção:\n"
            "1 - Cadastrar usuário\n"
            "2 - Criar votação\n"
            "3 - Encerrar votação\n"
            "4 - Autorizar eleitor\n"
            "0 - Sair\n"
            "Opção"
        )

        if opcao == "1":
            novo_login = typer.prompt("Login do novo usuário")
            senha = typer.prompt("Senha")
            tipo = typer.prompt("Tipo (admin, eleitor, auditor)")
            if sistema.cadastrar_usuario(novo_login, senha, tipo):
                typer.echo("✅ Usuário cadastrado.")
            else:
                typer.echo("⚠️ Usuário já existe.")
        elif opcao == "2":
            id_votacao = typer.prompt("ID da nova votação")
            opcoes = typer.prompt("Opções separadas por vírgula").split(",")
            if sistema.criar_votacao(id_votacao.strip(), [o.strip() for o in opcoes]):
                typer.echo("✅ Votação criada.")
            else:
                typer.echo("⚠️ Votação já existe.")
        elif opcao == "3":
            id_votacao = typer.prompt("ID da votação a encerrar")
            if sistema.encerrar_votacao(id_votacao):
                typer.echo("✅ Votação encerrada.")
            else:
                typer.echo("⚠️ Votação não encontrada.")
        elif opcao == "4":
            id_votacao = typer.prompt("ID da votação")
            eleitor_login = typer.prompt("Login do eleitor")
            if sistema.autorizar_eleitor(id_votacao, eleitor_login):
                typer.echo("✅ Eleitor autorizado.")
            else:
                typer.echo("⚠️ Erro ao autorizar eleitor.")
        elif opcao == "0":
            break


def menu_eleitor(login):
    while True:
        opcao = typer.prompt(
            "\n[Eleitor] Escolha uma opção:\n"
            "1 - Votar\n"
            "0 - Sair\n"
            "Opção"
        )

        if opcao == "1":
            id_votacao = typer.prompt("ID da votação")
            if not sistema.votacao_ativa(id_votacao):
                typer.echo("⚠️ Votação não está ativa.")
                continue

            if not sistema.eleitor_autorizado(id_votacao, login):
                typer.echo("❌ Você não está autorizado a votar.")
                continue

            opcoes = sistema.opcoes_disponiveis(id_votacao)
            for i, opc in enumerate(opcoes):
                typer.echo(f"{i + 1} - {opc}")
            escolha = typer.prompt("Digite o número da sua escolha")

            try:
                escolha = int(escolha)
                opcao = opcoes[escolha - 1]
            except (ValueError, IndexError):
                typer.echo("❌ Opção inválida.")
                continue

            caminho = f"data/blockchain_votacao_{id_votacao}.json"
            bc = Blockchain(caminho)
            sucesso = bc.adicionar_voto(login, opcao)
            if sucesso:
                typer.echo("✅ Voto registrado com sucesso.")
            else:
                typer.echo("⚠️ Você já votou nesta votação.")
        elif opcao == "0":
            break


def menu_auditor():
    while True:
        opcao = typer.prompt(
            "\n[Auditor] Escolha uma opção:\n"
            "1 - Ver resultado de votação\n"
            "2 - Exportar relatório CSV\n"
            "0 - Sair\n"
            "Opção"
        )

        if opcao == "1":
            id_votacao = typer.prompt("ID da votação")
            caminho = f"data/blockchain_votacao_{id_votacao}.json"
            if not sistema.votacao_ativa(id_votacao):
                bc = Blockchain(caminho)
                relatorio = bc.gerar_relatorio()
                typer.echo("\n📊 Resultado Final:")
                for opcao, total in relatorio["detalhes"].items():
                    typer.echo(f"{opcao}: {total} voto(s)")
                typer.echo(f"\n🏆 Vencedor: {relatorio['vencedor']}")
            else:
                typer.echo("⚠️ Votação ainda está ativa.")
        elif opcao == "2":
            id_votacao = typer.prompt("ID da votação")
            caminho = sistema.exportar_csv(id_votacao)
            if caminho:
                typer.echo(f"✅ Relatório exportado para {caminho}")
            else:
                typer.echo("❌ Erro ao exportar relatório.")
        elif opcao == "0":
            break


if __name__ == "__main__":
    app()
