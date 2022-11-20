import sys
from argparse import ArgumentParser
from .communicator import Client
from .model.controller import ControllerModel
from .stream import Stream, StatsRelay


def transmit_file(stream: Stream, file: str):
    with open(file, "rb") as f:
        while True:
            rbuffer = f.read(Stream.PACKET_DATASEG_SIZE)

            if len(rbuffer) == 0:
                break

            stream.write(rbuffer)


def transmit_stdin(stream: Stream):
    for l in sys.stdin:
        print("Writing: " + l)
        stream.write(l.encode("utf-8"))


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

    args = parser.parse_args()

    controller = ControllerModel(args.controller)
    client = Client(
        args.target,
        args.target_port,
        transmit_filter=StatsRelay("client_sent", controller),
        recv_filter=StatsRelay("client_recv", controller)
    )

    with client as client_stream:
        if args.file:
            transmit_file(client_stream, args.file)
        else:
            transmit_stdin(client_stream)


if __name__ == "__man__":
    sender_main()