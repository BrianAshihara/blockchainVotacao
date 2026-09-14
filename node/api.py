import re
import threading
from datetime import datetime, timezone

import requests
from flask import Flask, request, jsonify

from node.estado import EstadoNo
from node.identidade import verificar_mensagem
from sistema.votacao import ID_VOTACAO_VALIDO
from core.transacao import Transacao
from core.bloco import Bloco
from core.validacao import validar_transacao, validar_conteudo_bloco, validar_votos_do_bloco
from core.cadeia import verificar_integridade, gerar_relatorio, contar_votos
from core.cripto import verificar_assinatura, chave_publica_valida

PAPEIS_ADMIN = ("master", "admin")
LOGIN_VALIDO = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
TAMANHO_MINIMO_SENHA = 6
ENDERECOS_LOCAIS = ("127.0.0.1", "::1")


def _ler_data_iso(valor):
    if valor in (None, ""):
        return None
    try:
        data = datetime.fromisoformat(str(valor))
    except ValueError:
        raise ValueError(f"Data invalida: {valor}")
    if data.tzinfo is None:
        raise ValueError("Data sem fuso horario (ex: 2025-01-01T10:00:00+00:00)")
    return data.astimezone(timezone.utc)


def criar_app(estado: EstadoNo) -> Flask:
    """
    Factory function para criar a app Flask.
    Recebe o estado do no como dependencia.
    """
    app = Flask(__name__)

    @app.errorhandler(KeyError)
    def handle_key_error(e):
        return jsonify({"erro": f"Campo obrigatorio ausente: {e}"}), 400

    @app.errorhandler(TypeError)
    def handle_type_error(e):
        return jsonify({"erro": "Requisicao invalida ou JSON ausente"}), 400

    @app.errorhandler(AttributeError)
    def handle_attribute_error(e):
        return jsonify({"erro": "Requisicao invalida ou JSON ausente"}), 400

    @app.after_request
    def liberar_cors(resposta):
        # frontend roda em outra origem; o token vai no header, sem cookie
        resposta.headers["Access-Control-Allow-Origin"] = "*"
        resposta.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        resposta.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return resposta

    def _token_requisicao() -> str:
        cabecalho = request.headers.get("Authorization", "")
        return cabecalho[7:] if cabecalho.startswith("Bearer ") else ""

    def _usuario_autenticado(papeis):
        from sistema.autenticacao import tipo_usuario
        token = _token_requisicao()
        login = estado.sessoes.obter(token) if token else None
        if login is None:
            return None, (jsonify({"erro": "Sessao invalida ou expirada"}), 401)
        if tipo_usuario(login, caminho=estado.caminho_usuarios) not in papeis:
            return None, (jsonify({"erro": "Acesso nao permitido para este usuario"}), 403)
        return login, None

    def _propagar_votacao_async(dados_votacao):
        from network.propagacao import propagar_votacao
        threading.Thread(
            target=propagar_votacao,
            args=(dados_votacao, estado.peers.listar(), estado.porta, estado.identidade, estado.usar_tls),
            daemon=True
        ).start()

    # --- Chain endpoints ---

    @app.route("/chain", methods=["GET"])
    def obter_chain():
        """Retorna a chain completa deste no."""
        return jsonify({
            "comprimento": estado.comprimento_chain(),
            "blocos": estado.obter_chain_dict()
        })

    @app.route("/chain/comprimento", methods=["GET"])
    def obter_comprimento():
        """Retorna so o comprimento (para consensus sem baixar tudo)."""
        return jsonify({"comprimento": estado.comprimento_chain()})

    @app.route("/chain/integridade", methods=["GET"])
    def verificar():
        """Verifica integridade da chain local."""
        valida = verificar_integridade(estado.blocos)
        return jsonify({"valida": valida})

    # --- Transaction endpoints ---

    @app.route("/transacao", methods=["POST"])
    def receber_transacao():
        """
        Recebe uma transacao (voto assinado) de um peer.
        Valida, adiciona a mempool, e propaga aos peers.
        """
        dados = request.get_json()
        tx = Transacao.from_dict(dados)

        valida, motivo = validar_transacao(tx, estado.blocos, estado.mempool.listar(),
                                              caminho_votacoes=estado.caminho_votacoes)
        if not valida:
            return jsonify({"erro": motivo}), 400

        adicionada = estado.mempool.adicionar(tx)
        if not adicionada:
            return jsonify({"mensagem": "Transacao ja conhecida"}), 200

        from network.propagacao import propagar_transacao
        threading.Thread(
            target=propagar_transacao,
            args=(tx, estado.peers.listar(), estado.porta, estado.usar_tls),
            daemon=True
        ).start()

        return jsonify({"mensagem": "Transacao aceita", "tx_hash": tx.calcular_hash()}), 201

    @app.route("/mempool", methods=["GET"])
    def obter_mempool():
        """Retorna transacoes pendentes."""
        return jsonify({
            "pendentes": [t.to_dict() for t in estado.mempool.listar()],
            "total": estado.mempool.tamanho()
        })

    # --- Block endpoints ---

    @app.route("/bloco", methods=["POST"])
    def receber_bloco():
        """
        Recebe um bloco minerado de outro no.
        - Encaixa na ponta local: adiciona.
        - Mesma altura da ponta ou mais baixo: mantem o bloco que chegou primeiro.
        - Mais alto e nao encaixa (gap ou outro ramo): o peer tem cadeia mais longa,
          entao ressincroniza pela cadeia mais longa valida.
        """
        dados = request.get_json()
        bloco = Bloco.from_dict(dados)

        valido, motivo = validar_conteudo_bloco(bloco)
        if not valido:
            return jsonify({"erro": motivo}), 400

        ponta = estado.ultimo_bloco()
        if bloco.indice <= ponta.indice:
            return jsonify({"erro": f"Bloco {bloco.indice} nao e mais alto que a ponta local ({ponta.indice})"}), 400

        from network.sincronizacao import sincronizar_votacoes_e_chain

        if bloco.indice == ponta.indice + 1 and bloco.hash_anterior == ponta.hash_atual:
            votos_validos, motivo = validar_votos_do_bloco(bloco, estado.blocos, estado.caminho_votacoes)
            if not votos_validos:
                threading.Thread(target=sincronizar_votacoes_e_chain, args=(estado,), daemon=True).start()
                return jsonify({"erro": motivo}), 400
            if estado.adicionar_bloco_se_ponta(bloco):
                return jsonify({"mensagem": "Bloco aceito"}), 201
            return jsonify({"erro": "A ponta da cadeia mudou durante o recebimento"}), 409

        threading.Thread(
            target=sincronizar_votacoes_e_chain,
            args=(estado,),
            daemon=True
        ).start()
        return jsonify({"mensagem": "Sincronizando chain"}), 202

    # --- Mining endpoint ---

    @app.route("/minerar", methods=["POST"])
    def minerar():
        """
        Minera um bloco com as transacoes pendentes na mempool.
        """
        novo_bloco = estado.minerar_pendentes()
        if novo_bloco is None:
            if not estado._mining_lock.acquire(blocking=False):
                return jsonify({"erro": "Mineracao em andamento"}), 409
            estado._mining_lock.release()
            return jsonify({"erro": "Nenhuma transacao pendente"}), 400

        from network.propagacao import propagar_bloco
        threading.Thread(
            target=propagar_bloco,
            args=(novo_bloco, estado.peers.listar(), estado.porta, estado.usar_tls),
            daemon=True
        ).start()

        return jsonify({
            "mensagem": "Bloco minerado",
            "bloco": novo_bloco.to_dict()
        }), 201

    # --- Peer endpoints ---

    @app.route("/peers", methods=["GET"])
    def listar_peers():
        return jsonify({"peers": estado.peers.listar()})

    @app.route("/peers/registrar", methods=["POST"])
    def registrar_peer():
        """
        Registra um novo peer.
        Body: {"endereco": "host:port"}
        Com autenticacao: inclui id_no, chave_publica, timestamp, assinatura.
        """
        dados = request.get_json()
        endereco = dados.get("endereco")
        if not endereco:
            return jsonify({"erro": "Endereco obrigatorio"}), 400

        assinatura = dados.get("assinatura")
        if assinatura:
            chave_publica = dados.get("chave_publica", "")
            timestamp_str = dados.get("timestamp", "")

            dados_assinados = f"{endereco}:{timestamp_str}"
            if not verificar_assinatura(chave_publica, dados_assinados, assinatura):
                return jsonify({"erro": "Assinatura invalida"}), 401

            try:
                ts = datetime.fromisoformat(timestamp_str)
                agora = datetime.now(timezone.utc)
                if abs((agora - ts).total_seconds()) > 300:
                    return jsonify({"erro": "Timestamp expirado (max 5 min)"}), 401
            except (ValueError, TypeError):
                return jsonify({"erro": "Timestamp invalido"}), 400

        elif estado.require_auth:
            return jsonify({"erro": "Autenticacao obrigatoria"}), 401

        novo = estado.peers.adicionar(endereco)
        return jsonify({
            "mensagem": "Peer registrado" if novo else "Peer ja conhecido",
            "peers": estado.peers.listar()
        })

    # --- Voting session endpoints ---

    @app.route("/votacoes", methods=["GET"])
    def listar_votacoes():
        """Retorna todas as sessoes de votacao (para sync entre nos)."""
        from sistema.votacao import obter_todas_votacoes_dict
        votacoes = obter_todas_votacoes_dict(caminho=estado.caminho_votacoes)
        # assinada para o peer que sincroniza conferir que veio deste no
        return jsonify({"votacoes": votacoes, **estado.identidade.assinar_mensagem(votacoes)})

    @app.route("/votacao", methods=["POST"])
    def receber_votacao():
        """
        Recebe uma sessao de votacao de um peer.
        Merge: cria se nao existe, encerra se o peer encerrou.
        """
        from sistema.votacao import merge_votacao, votacao_recebida_valida
        dados = request.get_json(silent=True) or {}
        votacao = dados.get("votacao")

        autenticada, motivo = verificar_mensagem(votacao, dados, estado.nos_confiaveis.listar())
        if not autenticada:
            return jsonify({"erro": motivo}), 401
        if not votacao_recebida_valida(votacao):
            return jsonify({"erro": "Dados da votacao invalidos"}), 400

        alterou = merge_votacao(votacao, caminho=estado.caminho_votacoes)
        if alterou:
            return jsonify({"mensagem": "Votacao atualizada"}), 201
        return jsonify({"mensagem": "Votacao ja conhecida"}), 200

    @app.route("/votacao/propagar", methods=["POST"])
    def propagar_votacao_endpoint():
        # usado pela CLI da mesma maquina; a sessao e relida do disco, o corpo so indica qual
        from sistema.votacao import obter_votacao_dict
        if request.remote_addr not in ENDERECOS_LOCAIS:
            return jsonify({"erro": "Propagacao permitida apenas a partir da maquina do no"}), 403

        dados = request.get_json(silent=True) or {}
        votacao = obter_votacao_dict(str(dados.get("id_votacao", "")), caminho=estado.caminho_votacoes)
        if votacao is None:
            return jsonify({"erro": "Votacao nao encontrada"}), 404

        _propagar_votacao_async(votacao)
        return jsonify({"mensagem": "Propagacao iniciada"})

    # --- Voting report endpoint ---

    @app.route("/votacao/relatorio/<id_votacao>", methods=["GET"])
    def relatorio_votacao(id_votacao):
        """
        Relatorio de votacao.
        - Sessao ativa: payload slim (apenas contagem total, sem breakdown).
        - Sessao encerrada: relatorio completo com percentuais e vencedor.
        """
        from sistema.votacao import votacao_ativa, _carregar_votacoes
        votacoes = _carregar_votacoes(estado.caminho_votacoes)
        dados_votacao = votacoes.get(id_votacao)

        if votacao_ativa(id_votacao, caminho=estado.caminho_votacoes):
            # Sessao ativa: expor apenas contagem total, sem breakdown por candidato
            total = contar_votos(estado.blocos, id_votacao)
            return jsonify({
                "id_votacao": id_votacao,
                "nome": dados_votacao.get("nome") if dados_votacao else None,
                "ativa": True,
                "inicio": dados_votacao.get("inicio") if dados_votacao else None,
                "fim": dados_votacao.get("fim") if dados_votacao else None,
                "total_votos_confirmados": total
            })

        relatorio = gerar_relatorio(estado.blocos, id_votacao, dados_votacao=dados_votacao)
        return jsonify(relatorio)

    @app.route("/votacao/contagem/<id_votacao>", methods=["GET"])
    def contagem_votacao(id_votacao):
        """Contagem leve de votos confirmados on-chain. Publico, qualquer estado."""
        total = contar_votos(estado.blocos, id_votacao)
        return jsonify({
            "id_votacao": id_votacao,
            "total_votos_confirmados": total
        })

    # Usuario endpoints (frontend)

    @app.route("/usuario/login", methods=["POST"])
    def login_usuario():
        from sistema.autenticacao import autenticar, obter_usuario_publico
        dados = request.get_json(silent=True) or {}
        login = str(dados.get("login", "")).strip()
        senha = str(dados.get("senha", ""))

        if not login or not autenticar(login, senha, caminho=estado.caminho_usuarios):
            return jsonify({"erro": "Login ou senha invalidos"}), 401

        usuario = obter_usuario_publico(login, caminho=estado.caminho_usuarios)
        if usuario["tipo"] not in ("master", "admin", "eleitor"):
            return jsonify({"erro": "Tipo de usuario sem acesso ao sistema"}), 403

        usuario["token"] = estado.sessoes.criar(login)
        return jsonify(usuario)

    @app.route("/usuario/logout", methods=["POST"])
    def logout_usuario():
        estado.sessoes.remover(_token_requisicao())
        return jsonify({"mensagem": "Sessao encerrada"})

    @app.route("/usuario/autorregistrar", methods=["POST"])
    def autorregistrar_usuario():
        from sistema.autenticacao import autorregistrar_eleitor
        dados = request.get_json(silent=True) or {}
        login = str(dados.get("login", "")).strip()
        senha = str(dados.get("senha", ""))
        chave_publica = str(dados.get("chave_publica", "")).lower()
        chave_privada_cifrada = dados.get("chave_privada_cifrada")

        if not LOGIN_VALIDO.match(login) or login.upper() == "REGISTRAR":
            return jsonify({"erro": "Login invalido (3 a 32 caracteres: letras, numeros, _ . -)"}), 400
        if len(senha) < TAMANHO_MINIMO_SENHA:
            return jsonify({"erro": f"A senha deve ter pelo menos {TAMANHO_MINIMO_SENHA} caracteres"}), 400
        if not chave_publica_valida(chave_publica):
            return jsonify({"erro": "Chave publica invalida"}), 400
        if not isinstance(chave_privada_cifrada, str) or not chave_privada_cifrada:
            return jsonify({"erro": "Chave privada cifrada ausente"}), 400

        if login == "admin" or not autorregistrar_eleitor(
                login, senha, chave_publica=chave_publica,
                chave_privada_cifrada=chave_privada_cifrada, caminho=estado.caminho_usuarios):
            return jsonify({"erro": "Login ja existe"}), 409

        return jsonify({"mensagem": "Eleitor cadastrado", "login": login}), 201

    @app.route("/usuarios", methods=["GET"])
    def listar_usuarios():
        from sistema.autenticacao import listar_eleitores, listar_admins
        _, erro = _usuario_autenticado(PAPEIS_ADMIN)
        if erro:
            return erro
        return jsonify({
            "eleitores": sorted(listar_eleitores(caminho=estado.caminho_usuarios)),
            "admins": sorted(listar_admins(caminho=estado.caminho_usuarios))
        })

    @app.route("/usuario/promover", methods=["POST"])
    def promover_usuario():
        from sistema.autenticacao import promover_para_admin
        _, erro = _usuario_autenticado(PAPEIS_ADMIN)
        if erro:
            return erro
        dados = request.get_json(silent=True) or {}
        alvo = str(dados.get("login", "")).strip()
        if not promover_para_admin(alvo, caminho=estado.caminho_usuarios):
            return jsonify({"erro": "Nao foi possivel promover (usuario inexistente, ja e admin ou e master)"}), 400
        return jsonify({"mensagem": f"Eleitor '{alvo}' promovido a admin"})

    @app.route("/usuario/rebaixar", methods=["POST"])
    def rebaixar_usuario():
        from sistema.autenticacao import rebaixar_para_eleitor
        # so o master mexe no papel de um admin
        _, erro = _usuario_autenticado(("master",))
        if erro:
            return erro
        dados = request.get_json(silent=True) or {}
        alvo = str(dados.get("login", "")).strip()
        if not rebaixar_para_eleitor(alvo, caminho=estado.caminho_usuarios):
            return jsonify({"erro": "Nao foi possivel rebaixar (usuario inexistente, nao e admin ou e master)"}), 400
        return jsonify({"mensagem": f"Admin '{alvo}' rebaixado a eleitor"})

    # Gestao de votacoes

    @app.route("/votacao/criar", methods=["POST"])
    def criar_votacao_endpoint():
        from sistema.votacao import criar_votacao, obter_votacao_dict
        _, erro = _usuario_autenticado(PAPEIS_ADMIN)
        if erro:
            return erro

        dados = request.get_json(silent=True) or {}
        id_votacao = str(dados.get("id_votacao", "")).strip()
        nome = str(dados.get("nome", "")).strip()
        opcoes = dados.get("opcoes")

        if not ID_VOTACAO_VALIDO.match(id_votacao):
            return jsonify({"erro": "ID invalido (ate 64 caracteres: letras, numeros, _ ou -)"}), 400
        if not nome:
            return jsonify({"erro": "Nome da votacao obrigatorio"}), 400
        if not isinstance(opcoes, list) or not all(isinstance(o, str) for o in opcoes):
            return jsonify({"erro": "Opcoes devem ser uma lista de textos"}), 400
        opcoes = [o.strip() for o in opcoes]
        if len(opcoes) < 2 or "" in opcoes or len(set(opcoes)) != len(opcoes):
            return jsonify({"erro": "Informe pelo menos 2 opcoes, sem repeticao"}), 400

        try:
            inicio = _ler_data_iso(dados.get("inicio")) or datetime.now(timezone.utc)
            fim = _ler_data_iso(dados.get("fim"))
        except ValueError as e:
            return jsonify({"erro": str(e)}), 400
        if fim is not None and fim <= inicio:
            return jsonify({"erro": "O fim deve ser depois do inicio"}), 400
        if fim is not None and fim <= datetime.now(timezone.utc):
            return jsonify({"erro": "O fim da votacao ja passou"}), 400

        criada = criar_votacao(id_votacao, nome, opcoes, inicio=inicio.isoformat(),
                               fim=fim.isoformat() if fim else None,
                               caminho=estado.caminho_votacoes)
        if not criada:
            return jsonify({"erro": "Ja existe uma votacao com este ID"}), 409

        votacao = obter_votacao_dict(id_votacao, caminho=estado.caminho_votacoes)
        _propagar_votacao_async(votacao)
        return jsonify({"mensagem": "Votacao criada", "votacao": votacao}), 201

    @app.route("/votacao/encerrar", methods=["POST"])
    def encerrar_votacao_endpoint():
        from sistema.votacao import encerrar_votacao, obter_votacao_dict
        from network.propagacao import propagar_bloco
        _, erro = _usuario_autenticado(PAPEIS_ADMIN)
        if erro:
            return erro

        dados = request.get_json(silent=True) or {}
        id_votacao = str(dados.get("id_votacao", "")).strip()
        votacao = obter_votacao_dict(id_votacao, caminho=estado.caminho_votacoes)
        if votacao is None:
            return jsonify({"erro": "Votacao nao encontrada"}), 404
        if not votacao["ativa"]:
            return jsonify({"erro": "Votacao ja encerrada"}), 409

        # mine-on-close: minera os votos pendentes da sessao antes de encerrar
        blocos_minerados = []
        while any(tx.id_votacao == id_votacao for tx in estado.mempool.listar()):
            novo_bloco = estado.minerar_pendentes()
            if novo_bloco is None:
                break
            blocos_minerados.append(novo_bloco.indice)
            threading.Thread(
                target=propagar_bloco,
                args=(novo_bloco, estado.peers.listar(), estado.porta, estado.usar_tls),
                daemon=True
            ).start()

        encerrar_votacao(id_votacao, caminho=estado.caminho_votacoes)
        _propagar_votacao_async(obter_votacao_dict(id_votacao, caminho=estado.caminho_votacoes))
        return jsonify({"mensagem": "Votacao encerrada", "blocos_minerados": blocos_minerados})

    @app.route("/votacao/autorizar", methods=["POST"])
    def autorizar_eleitor_endpoint():
        from sistema.votacao import autorizar_eleitor, eleitor_autorizado, obter_votacao_dict
        from sistema.autenticacao import obter_usuario_publico, tipo_usuario
        _, erro = _usuario_autenticado(PAPEIS_ADMIN)
        if erro:
            return erro

        dados = request.get_json(silent=True) or {}
        id_votacao = str(dados.get("id_votacao", "")).strip()
        login = str(dados.get("login", "")).strip()

        votacao = obter_votacao_dict(id_votacao, caminho=estado.caminho_votacoes)
        if votacao is None:
            return jsonify({"erro": "Votacao nao encontrada"}), 404
        if not votacao["ativa"]:
            return jsonify({"erro": "Votacao ja encerrada"}), 409
        if tipo_usuario(login, caminho=estado.caminho_usuarios) != "eleitor":
            return jsonify({"erro": "Eleitor nao encontrado"}), 404
        if eleitor_autorizado(id_votacao, login, caminho=estado.caminho_votacoes):
            return jsonify({"erro": "Eleitor ja autorizado nesta votacao"}), 409

        usuario = obter_usuario_publico(login, caminho=estado.caminho_usuarios)
        chave_publica = usuario.get("chave_publica") if usuario else None
        if not chave_publica:
            return jsonify({"erro": "Eleitor sem chave publica cadastrada"}), 400

        autorizar_eleitor(id_votacao, login, chave_publica=chave_publica,
                          caminho=estado.caminho_votacoes)
        # a chave autorizada precisa chegar aos peers: sem ela, eles rejeitam o voto
        _propagar_votacao_async(obter_votacao_dict(id_votacao, caminho=estado.caminho_votacoes))
        return jsonify({"mensagem": "Eleitor autorizado"})

    @app.route("/votacao/<id_votacao>/eleitores", methods=["GET"])
    def eleitores_votacao(id_votacao):
        from sistema.votacao import _carregar_votacoes
        _, erro = _usuario_autenticado(PAPEIS_ADMIN)
        if erro:
            return erro
        votacoes = _carregar_votacoes(estado.caminho_votacoes)
        if id_votacao not in votacoes:
            return jsonify({"erro": "Votacao nao encontrada"}), 404
        return jsonify({
            "id_votacao": id_votacao,
            "eleitores": votacoes[id_votacao].get("eleitores", [])
        })

    @app.route("/eleitor/votacoes", methods=["GET"])
    def votacoes_eleitor():
        from sistema.votacao import listar_votacoes_eleitor, obter_votacao_dict
        login, erro = _usuario_autenticado(("eleitor",))
        if erro:
            return erro
        votacoes = []
        for id_votacao, _ in listar_votacoes_eleitor(login, caminho=estado.caminho_votacoes):
            dados = obter_votacao_dict(id_votacao, caminho=estado.caminho_votacoes)
            dados.pop("chaves_autorizadas", None)
            votacoes.append(dados)
        return jsonify({"votacoes": votacoes})

    # Node info endpoint

    @app.route("/no/info", methods=["GET"])
    def info_no():
        """Informacoes deste no."""
        return jsonify({
            "id_no": estado.identidade.id_no,
            "chave_publica": estado.identidade.chave_publica,
            "comprimento_chain": estado.comprimento_chain(),
            "transacoes_pendentes": estado.mempool.tamanho(),
            "peers": estado.peers.quantidade(),
            "porta": estado.porta
        })

    # Health check endpoint

    @app.route("/no/saude", methods=["GET"])
    def saude_no():
        """Verificacao de saude do no com status de peers."""
        peers = estado.peers.listar()
        protocolo = "https" if estado.usar_tls else "http"
        peers_alcancaveis = 0

        for peer in peers:
            try:
                resp = requests.get(
                    f"{protocolo}://{peer}/no/info",
                    timeout=2
                )
                if resp.status_code == 200:
                    peers_alcancaveis += 1
            except requests.exceptions.RequestException:
                pass

        return jsonify({
            "status": "ok",
            "id_no": estado.identidade.id_no,
            "comprimento_chain": estado.comprimento_chain(),
            "chain_valida": verificar_integridade(estado.blocos),
            "transacoes_pendentes": estado.mempool.tamanho(),
            "peers_conhecidos": len(peers),
            "peers_alcancaveis": peers_alcancaveis,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    return app
