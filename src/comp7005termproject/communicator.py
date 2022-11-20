import time
from math import inf
from typing import Callable

from .stream import Stream, RandomDropMutator, PacketMutator
import threading
import socket
import sys


class StreamBridge(threading.Thread):
    BUFFER_BLOCK_SIZE = Stream.PACKET_DATASEG_SIZE

    def __init__(self, a: Stream, b: Stream, buffer_wait=0.01):
        super().__init__()
        self.a = a
        self.b = b
        self.a_transmit = b''
        self.b_transmit = b''

        self.a_transmit_time = time.time()
        self.b_transmit_time = time.time()

        self.buffer_wait = buffer_wait
        self.stop_signal = threading.Event()

    def stop(self):
        self.stop_signal.set()

    def run(self):
        while not self.stop_signal.is_set():
            a_in = self.a.read(min_read=StreamBridge.BUFFER_BLOCK_SIZE, timeout=self.buffer_wait / 4)
            b_in = self.b.read(min_read=StreamBridge.BUFFER_BLOCK_SIZE, timeout=self.buffer_wait / 4)

            if len(a_in) > 0:
                if len(self.a_transmit) == 0:
                    self.a_transmit_time + time.time() + self.buffer_wait
                self.a_transmit += a_in

            if len(b_in) > 0:
                if len(self.b_transmit) == 0:
                    self.b_transmit_time + time.time() + self.buffer_wait
                self.b_transmit += b_in

            if len(self.a_transmit) > 0 and self.a_transmit_time > time.time():
                self.a.write(self.a_transmit)
                self.a_transmit = b''

            if len(self.b_transmit) > 0 and self.b_transmit_time > time.time():
                self.b.write(self.b_transmit)
                self.b_transmit = b''


class Client:
    def __init__(self, host: str, port: int,
                 recv_filter: PacketMutator = None, transmit_filter: PacketMutator = None):
        super().__init__()
        self.recv_filter = recv_filter
        self.transmit_filter = transmit_filter
        self.connection_config = (host, port)

    def __enter__(self) -> Stream:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect(self.connection_config)
        self.stream = Stream(recv_filter=self.recv_filter, transmit_filter=self.transmit_filter)
        self.stream.attach(self.sock)

        return self.stream

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stream.close()
        self.sock.close()


class ServerSocketAttacher(threading.Thread):
    def __init__(self, sock: socket.socket, stream: Stream):
        super().__init__()
        self.sock = sock
        self.stream = stream

    def run(self) -> None:
        try:
            self.stream.attach(self.sock.accept()[0])
        except Exception as e:
            print(sys.stderr, f"Error attaching stream to remote socket {e}")
            pass


class ServerSingleRemote:
    def __init__(self, port: int,
                 recv_filter: PacketMutator = None, transmit_filter: PacketMutator = None):
        super().__init__()
        self.recv_filter = recv_filter
        self.transmit_filter = transmit_filter
        self.connection_config = ("0.0.0.0", port)

    def __enter__(self) -> Stream:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(self.connection_config)
        self.sock.listen(0)
        self.stream = Stream(recv_filter=self.recv_filter, transmit_filter=self.transmit_filter)
        self.attacher = ServerSocketAttacher(self.sock, self.stream)
        self.attacher.start()

        return self.stream

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stream.close()
        self.sock.close()
        self.attacher.join()
