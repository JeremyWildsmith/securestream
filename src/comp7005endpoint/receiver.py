import os
import sys
from argparse import ArgumentParser
from .communicator import ServerSingleRemote
from .model.controller import ControllerModel
from .stream import StatsRelay


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

    args = parser.parse_args()

    controller = ControllerModel(args.controller)
    server = ServerSingleRemote(
        args.port,
        transmit_filter=StatsRelay("server_sent", controller),
        recv_filter=StatsRelay("server_recv", controller),
    )

    with server as server_stream:
        while server_stream.is_open():
            with os.fdopen(sys.stdout.fileno(), "wb", closefd=False) as stdout:
                stdout.write(server_stream.read(1))
                stdout.flush()


if __name__ == "__main__":
    receiver_main()
