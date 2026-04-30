import argparse
import threading
import logging
import json
import os
import time

from node.estado import EstadoNo
from node.api import criar_app
from network.sincronizacao import iniciar_sincronizacao, loop_verificacao_peers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)


def loop_mineracao_automatica(estado, intervalo: int = 30):
    """Daemon que minera automaticamente a cada intervalo se houver txs pendentes."""
    logger = logging.getLogger("auto_miner")
    while True:
        time.sleep(intervalo)
        if estado.mempool.tamanho() == 0:
            continue
        novo_bloco = estado.minerar_pendentes()
        if novo_bloco is not None:
            logger.info(f"Auto-minerado bloco {novo_bloco.indice} com {len(novo_bloco.transacoes)} tx(s)")
            from network.propagacao import propagar_bloco
            propagar_bloco(novo_bloco, estado.peers.listar(), estado.porta, estado.usar_tls)


def loop_encerramento_automatico(estado, intervalo: int = 30):
    """Daemon que encerra automaticamente sessoes cujo fim passou."""
    logger = logging.getLogger("auto_close")
    while True:
        time.sleep(intervalo)
        from sistema.votacao import listar_votacoes_expiradas, encerrar_votacao, obter_votacao_dict
        expiradas = listar_votacoes_expiradas(caminho=estado.caminho_votacoes)

        for id_votacao in expiradas:
            txs_pendentes = [tx for tx in estado.mempool.listar()
                             if tx.id_votacao == id_votacao]
            if txs_pendentes:
                logger.info(f"Sessao {id_votacao} expirada com {len(txs_pendentes)} voto(s) pendente(s). Minerando.")
                novo_bloco = estado.minerar_pendentes()
                if novo_bloco:
                    from network.propagacao import propagar_bloco
                    propagar_bloco(novo_bloco, estado.peers.listar(), estado.porta, estado.usar_tls)

            encerrar_votacao(id_votacao, caminho=estado.caminho_votacoes)
            logger.info(f"Sessao {id_votacao} encerrada automaticamente.")

            dados = obter_votacao_dict(id_votacao, caminho=estado.caminho_votacoes)
            if dados:
                from network.propagacao import propagar_votacao
                propagar_votacao(dados, estado.peers.listar(), estado.porta, estado.usar_tls)


def main():
    parser = argparse.ArgumentParser(description="No da blockchain de votacao P2P")
    parser.add_argument("--porta", type=int, default=5000, help="Porta HTTP (default: 5000)")
    parser.add_argument("--host", type=str, default="localhost", help="Endereco visivel para outros nos (ex: 192.168.1.10)")
    parser.add_argument("--dados", type=str, default="data", help="Diretorio de dados (default: data)")
    parser.add_argument("--peers", nargs="*", default=[], help="Peers iniciais (host:port)")
    parser.add_argument("--tls-cert", type=str, default=None, help="Caminho do certificado TLS (PEM)")
    parser.add_argument("--tls-key", type=str, default=None, help="Caminho da chave privada TLS (PEM)")
    parser.add_argument("--require-auth", action="store_true", help="Exigir autenticacao assinada no registro de peers")
    args = parser.parse_args()

    usar_tls = bool(args.tls_cert and args.tls_key)

    estado = EstadoNo(
        diretorio_dados=args.dados,
        porta=args.porta,
        usar_tls=usar_tls,
        require_auth=args.require_auth
    )

    endereco_proprio = f"{args.host}:{args.porta}"

    if args.peers:
        for peer in args.peers:
            estado.peers.adicionar(peer)
    else:
        caminho_bootstrap = os.path.join(os.path.dirname(os.path.abspath(__file__)), "peers_bootstrap.json")
        if os.path.exists(caminho_bootstrap):
            try:
                with open(caminho_bootstrap, "r") as f:
                    lista_peers = json.load(f)
                if not isinstance(lista_peers, list):
                    raise ValueError("peers_bootstrap.json deve conter uma lista")
                for peer in lista_peers:
                    if not isinstance(peer, str):
                        logging.warning(f"peers_bootstrap.json: entrada ignorada (nao e string): {peer}")
                        continue
                    if peer == endereco_proprio:
                        continue
                    estado.peers.adicionar(peer)
                logging.info(f"Peers carregados de peers_bootstrap.json")
            except (json.JSONDecodeError, ValueError) as e:
                logging.warning(f"peers_bootstrap.json malformado, ignorando: {e}")

    app = criar_app(estado)

    threading.Thread(
        target=iniciar_sincronizacao,
        args=(estado, endereco_proprio),
        daemon=True
    ).start()

    threading.Thread(
        target=loop_verificacao_peers,
        args=(estado, endereco_proprio),
        daemon=True
    ).start()

    threading.Thread(
        target=loop_mineracao_automatica,
        args=(estado,),
        daemon=True
    ).start()

    threading.Thread(
        target=loop_encerramento_automatico,
        args=(estado,),
        daemon=True
    ).start()

    logging.info(f"No iniciado na porta {args.porta} | ID: {estado.identidade.id_no}")
    logging.info(f"Peers iniciais: {estado.peers.listar()}")
    if usar_tls:
        logging.info(f"TLS ativado: {args.tls_cert}")
    if args.require_auth:
        logging.info("Autenticacao de peers obrigatoria")

    ssl_ctx = (args.tls_cert, args.tls_key) if usar_tls else None
    app.run(host="0.0.0.0", port=args.porta, threaded=True, ssl_context=ssl_ctx)


if __name__ == "__main__":
    main()
