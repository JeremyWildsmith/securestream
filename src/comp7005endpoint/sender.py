import sys
from argparse import ArgumentParser

from .subsystem import Subsystem
from .udp import UdpClient
from .tcp import TcpClient
from .model.controller import ControllerModel
from .stream import Stream, StatsRelay


def transmit_file(stream: Stream, file: str):
    with open(file, "rb") as f:
        while True:
            rbuffer = f.read(stream.get_preferred_segment_size())

            if len(rbuffer) == 0:
                break

            stream.write(rbuffer)


def transmit_stdin(stream: Stream):
    for l in sys.stdin:
        print("Writing: " + l)
        stream.write(l.encode("utf-8"))


def create_stream(subsystem: Subsystem, controller: ControllerModel):
    send_stat = StatsRelay("client_sent", controller)
    recv_stat = StatsRelay("client_recv", controller)

    return Stream(subsystem, transmit_filter=send_stat, recv_filter=recv_stat)


def sender_main():
    parser = ArgumentParser(
        prog='sender',
        description='Transmits data to a server')

    parser.add_argument(
        "--target-port",
        help="The port to host the proxy service on.",
        type=int,
        default=6000
    )

    parser.add_argument(
        "--target",
        help="The target port (where data is proxied to)",
        type=str,
        default="127.0.0.1"
    )

    parser.add_argument(
        "--file",
        help="Transmits the specified file. Otherwise, if argument not specified, enters text input mode from stdin "
             "where each newline triggers transmission of one or more packets containing the contents defined.",
        type=str
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

    if args.udp:
        client = UdpClient(
            args.target,
            args.target_port
        )
    else:
        client = TcpClient(
            args.target,
            args.target_port
        )

    with client as client_subsystem:
        with create_stream(client_subsystem, controller) as client_stream:
            if args.file:
                transmit_file(client_stream, args.file)
            else:
                transmit_stdin(client_stream)



if __name__ == "__main__":
    sender_main()