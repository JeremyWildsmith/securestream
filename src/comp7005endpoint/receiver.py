import os
import sys
import time
from argparse import ArgumentParser

from .udp import UdpServerSingleRemote
from .tcp import TcpServerSingleRemote
from .model.controller import ControllerModel
from .stream import StatsRelay, Stream


def receiver_main():
    parser = ArgumentParser(
        prog='proxy',
        description='Proxy server for controlling data drop-rates.')

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
        server_stream = Stream(
            server_subsystem,
            transmit_filter=StatsRelay("server_sent", controller),
            recv_filter=StatsRelay("server_recv", controller)
        )

        while server_stream.is_open():
            with os.fdopen(sys.stdout.fileno(), "wb", closefd=False) as stdout:
                stdout.write(server_stream.read(1))
                stdout.flush()

                delay = controller.get_config("recv_delay", 0)

                if delay > 0:
                    time.sleep(delay)


if __name__ == "__main__":
    receiver_main()
