import threading
from datetime import datetime, timezone

import requests
from flask import Flask, request, jsonify

from node.estado import EstadoNo
from core.transacao import Transacao
from core.bloco import Bloco
from core.validacao import validar_transacao, validar_bloco
from core.cadeia import verificar_integridade, gerar_relatorio
from core.mineracao import minerar_bloco
from core.cripto import verificar_assinatura


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

        valida, motivo = validar_transacao(tx, estado.blocos, estado.mempool.listar())
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
        Valida e adiciona a chain se valido.
        """
        dados = request.get_json()
        bloco = Bloco.from_dict(dados)

        bloco_anterior = estado.ultimo_bloco()
        valido, motivo = validar_bloco(bloco, bloco_anterior)

        if not valido:
            if bloco.indice > bloco_anterior.indice + 1:
                from network.sincronizacao import sincronizar_chain
                threading.Thread(
                    target=sincronizar_chain,
                    args=(estado,),
                    daemon=True
                ).start()
                return jsonify({"mensagem": "Sincronizando chain"}), 202
            return jsonify({"erro": motivo}), 400

        estado.adicionar_bloco(bloco)
        return jsonify({"mensagem": "Bloco aceito"}), 201

    # --- Mining endpoint ---

    @app.route("/minerar", methods=["POST"])
    def minerar():
        """
        Minera um bloco com as transacoes pendentes na mempool.
        """
        transacoes = estado.mempool.obter_para_mineracao()
        if not transacoes:
            return jsonify({"erro": "Nenhuma transacao pendente"}), 400

        bloco_anterior = estado.ultimo_bloco()
        novo_bloco = minerar_bloco(bloco_anterior, transacoes)
        estado.adicionar_bloco(novo_bloco)

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
        return jsonify({
            "votacoes": obter_todas_votacoes_dict(caminho=estado.caminho_votacoes)
        })

    @app.route("/votacao", methods=["POST"])
    def receber_votacao():
        """
        Recebe uma sessao de votacao de um peer.
        Merge: cria se nao existe, encerra se o peer encerrou.
        """
        from sistema.votacao import merge_votacao
        dados = request.get_json()
        alterou = merge_votacao(dados, caminho=estado.caminho_votacoes)
        if alterou:
            return jsonify({"mensagem": "Votacao atualizada"}), 201
        return jsonify({"mensagem": "Votacao ja conhecida"}), 200

    @app.route("/votacao/propagar", methods=["POST"])
    def propagar_votacao_endpoint():
        """
        CLI chama apos criar/encerrar votacao para broadcast aos peers.
        Body: {"id_votacao": str, "nome": str, "opcoes": [...], "ativa": bool}
        """
        dados = request.get_json()
        from network.propagacao import propagar_votacao
        threading.Thread(
            target=propagar_votacao,
            args=(dados, estado.peers.listar(), estado.porta, estado.usar_tls),
            daemon=True
        ).start()
        return jsonify({"mensagem": "Propagacao iniciada"})

    # --- Voting report endpoint ---

    @app.route("/votacao/relatorio/<id_votacao>", methods=["GET"])
    def relatorio_votacao(id_votacao):
        """Gera relatorio de votacao."""
        relatorio = gerar_relatorio(estado.blocos, id_votacao)
        return jsonify(relatorio)

    # --- Node info endpoint ---

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

    # --- Health check endpoint ---

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
