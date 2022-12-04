import os
import sys
import time
from argparse import ArgumentParser

from .subsystem import Subsystem
from .udp import UdpServerSingleRemote
from .tcp import TcpServerSingleRemote
from .model.controller import ControllerModel
from .stream import StatsRelay, Stream, CompositeMutator
from .crypto import build_cryptor


def create_stream(subsystem: Subsystem, controller: ControllerModel, pub_key: str = None, priv_key: str = None):
    transmit_filter = StatsRelay("server_sent", controller)
    recv_filter = StatsRelay("server_recv", controller)

    if pub_key:
        recv_filter = CompositeMutator(build_cryptor(pub_key), recv_filter)

    if priv_key:
        transmit_filter = CompositeMutator(transmit_filter, build_cryptor(priv_key))

    return Stream(subsystem, transmit_filter=transmit_filter, recv_filter=recv_filter)


def receiver_main():
    parser = ArgumentParser(
        prog='receiver',
        description='Receiver server for collecting data from a sender.')

    parser.add_argument(
        "--port",
        help="The listen port for the file reciever",
        type=int,
        default=7000
    )

    parser.add_argument(
        "--controller",
        help="URL to the controller in the form of http://<host>:port",
        type=str,
        default="http://127.0.0.1:5000"
    )

    parser.add_argument(
        "--udp",
        help="Use UDP Subsystem instead of default TCP subsystem",
        action='store_true'
    )

    parser.add_argument(
        "--pub-key",
        help="Public key file to use for decrypting received data.",
        type=str
    )

    parser.add_argument(
        "--priv-key",
        help="Private key file, used for encrypting received data.",
        type=str
    )

    args = parser.parse_args()

    controller = ControllerModel(args.controller)

    if args.udp:
        server = UdpServerSingleRemote(
            args.port
        )
    else:
        server = TcpServerSingleRemote(
            args.port
        )

    with server as server_subsystem:
        with create_stream(server_subsystem, controller, args.pub_key, args.priv_key) as server_stream:
            while server_stream.is_open():
                with os.fdopen(sys.stdout.fileno(), "wb", closefd=False) as stdout:
                    stdout.write(server_stream.read(1))
                    stdout.flush()

                    delay = controller.get_config("recv_delay", 0)

                    if delay > 0:
                        time.sleep(delay)


if __name__ == "__main__":
    receiver_main()
