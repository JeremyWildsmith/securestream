import time
from argparse import ArgumentParser
from .communicator import ServerSingleRemote, Client
from .model.controller import ControllerModel
from .stream import RandomDropMutator, StreamBridge
import socket

def proxy_main():
    parser = ArgumentParser(
        prog='proxy',
        description='Proxy server for controlling data drop-rates.')

    parser.add_argument(
        "--proxy-port",
        help="The port to host the proxy service on.",
        type=int,
        default=6000
    )

    parser.add_argument(
        "--target-port",
        help="The target port (where data is proxied to)",
        type=int,
        default=7000
    )

    parser.add_argument(
        "--target",
        help="The target endpoint (where data is proxied to)",
        type=str,
        default="127.0.0.1"
    )

    parser.add_argument(
        "--controller",
        help="URL to the controller in the form of http://<host>:port",
        type=str,
        default="http://127.0.0.1:5000"
    )

    args = parser.parse_args()

    print("Waiting for connection to proxy...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("0.0.0.0", args.proxy_port))
    sock.listen(0)
    client = sock.accept()[0]
    sock.close()

    print("Establishing connection to target...")

    target = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    target.connect((args.target, args.target_port))

    print("Target connection established. Bridging")

    client_serv_filter = RandomDropMutator(0.0)
    serv_client_filter = RandomDropMutator(0.0)

    controller = ControllerModel(args.controller)
    try:
        bridge = StreamBridge(client, target, client_serv_filter, serv_client_filter)
        bridge.start()

        while bridge.is_alive():
            time.sleep(0.2)

            client_serv_filter.set_drop(controller.get_config("client_server_drop", 0.0) / 100.0)
            serv_client_filter.set_drop(controller.get_config("server_client_drop", 0.0) / 100.0)
    finally:
        client.close()
        target.close()

if __name__ == "__main__":
    proxy_main()