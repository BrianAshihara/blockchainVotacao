import argparse
import threading
import logging

from node.estado import EstadoNo
from node.api import criar_app
from network.sincronizacao import iniciar_sincronizacao

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)


def main():
    parser = argparse.ArgumentParser(description="No da blockchain de votacao P2P")
    parser.add_argument("--porta", type=int, default=5000, help="Porta HTTP (default: 5000)")
    parser.add_argument("--dados", type=str, default="data", help="Diretorio de dados (default: data)")
    parser.add_argument("--peers", nargs="*", default=[], help="Peers iniciais (host:port)")
    args = parser.parse_args()

    estado = EstadoNo(diretorio_dados=args.dados, porta=args.porta)

    for peer in args.peers:
        estado.peers.adicionar(peer)

    app = criar_app(estado)

    endereco_local = f"localhost:{args.porta}"
    threading.Thread(
        target=iniciar_sincronizacao,
        args=(estado, endereco_local),
        daemon=True
    ).start()

    logging.info(f"No iniciado na porta {args.porta} | ID: {estado.identidade.id_no}")
    logging.info(f"Peers iniciais: {estado.peers.listar()}")

    app.run(host="0.0.0.0", port=args.porta, threaded=True)


if __name__ == "__main__":
    main()
