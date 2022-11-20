from comp7005termproject.communicator import ServerSingleRemote, Client
from .stream import RandomDropMutator

dropper = RandomDropMutator(.8)


def test_main():
    with ServerSingleRemote(4867, transmit_filter=RandomDropMutator(0.8)) as server_stream:
        with Client("0.0.0.0", 4867) as client_stream:
            server_stream.write("Hello WORLD!".encode("utf-8"))

            print("Waiting for server reply ...")
            print(client_stream.read(4).decode("utf-8"))


if __name__ == "__main__":
    test_main()
