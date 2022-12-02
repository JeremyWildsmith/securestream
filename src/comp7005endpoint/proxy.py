import time
from argparse import ArgumentParser

from comp7005endpoint.udp import UdpClient, UdpServerSingleRemote
from .tcp import TcpSocketSubsystem, TcpClient, TcpServerSingleRemote
from .model.controller import ControllerModel
from .stream import RandomDropMutator, SubsystemBridge
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

    parser.add_argument(
        "--udp",
        help="Use UDP Subsystem instead of default TCP subsstem",
        action='store_true'
    )

    args = parser.parse_args()

    controller = ControllerModel(args.controller)

    client_serv_filter = RandomDropMutator(0.0)
    serv_client_filter = RandomDropMutator(0.0)

    if args.udp:
        client = UdpServerSingleRemote(args.proxy_port)
        target = UdpClient(args.target, args.target_port)
    else:
        client = TcpServerSingleRemote(args.proxy_port)
        target = TcpClient(args.target, args.target_port)

    with client as client_subsystem:
        with target as target_subsystem:
            try:
                bridge = SubsystemBridge(
                    client_subsystem,
                    target_subsystem,
                    client_serv_filter, serv_client_filter)
                bridge.start()

                while bridge.is_alive():
                    time.sleep(0.2)

                    client_serv_filter.set_drop(controller.get_config("client_server_drop", 0.0) / 100.0)
                    serv_client_filter.set_drop(controller.get_config("server_client_drop", 0.0) / 100.0)
            finally:
                client_subsystem.close()
                target_subsystem.close()


if __name__ == "__main__":
    proxy_main()
