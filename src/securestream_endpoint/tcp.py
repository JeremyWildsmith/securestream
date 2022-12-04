import math
import select
import socket
import struct
import sys
import threading
import time

from typing import Optional
from .subsystem import Subsystem, SubsystemClosedException, Packet


class TcpSocketSubsystem(Subsystem):
    def __init__(self, sock: socket.socket = None):
        self.sock: Optional[socket.socket] = None
        self.recv_buffer = b''
        self.closed = False

        if sock is not None:
            self.attach(sock)

    def attach(self, sock: socket.socket):
        if self.sock is not None:
            raise Exception("Already attached")

        self.sock = sock
        self.sock.setblocking(False)

    def send(self, packet: Packet):
        try:
            while self.sock is None:
                time.sleep(0.1)

            if self.is_closed():
                raise SubsystemClosedException()

            packet_raw = packet.save()
            packet_len = len(packet_raw)
            transmit = struct.pack("I", packet_len) + packet_raw

            self.sock.sendall(transmit)
        except ConnectionError:
            self.close()
            raise SubsystemClosedException()

    def recv(self) -> Optional[Packet]:
        if self.sock is None:
            return None

        if self.is_closed():
            raise SubsystemClosedException()

        expected = math.inf
        if len(self.recv_buffer) >= 4:
            expected = 4 + struct.unpack("I", self.recv_buffer[:4])[0]

        ready = select.select([self.sock], [], [], 0.01)

        if ready[0]:
            self.recv_buffer += self.sock.recv(4096)

        if len(self.recv_buffer) >= expected:
            data = self.recv_buffer[4:expected]
            self.recv_buffer = self.recv_buffer[expected:]
            packet = Packet.load(data)
            return packet
        else:
            return None

    def get_dataseg_limit(self) -> int:
        return 1024 * 2

    def close(self):
        self.closed = True

        if self.sock:
            self.sock.close()

    def is_closed(self) -> bool:
        return self.closed


class TcpClient:
    def __init__(self, host: str, port: int):
        super().__init__()
        self.connection_config = (host, port)
        self.subsystem: TcpSocketSubsystem = None

    def __enter__(self) -> Subsystem:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(self.connection_config)

        self.subsystem = TcpSocketSubsystem(sock)

        return self.subsystem

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.subsystem:
            self.subsystem.close()


class TcpServerSocketAttacher(threading.Thread):
    def __init__(self, sock: socket.socket, subsystem: TcpSocketSubsystem):
        super().__init__()
        self.sock = sock
        self.subsystem = subsystem

    def run(self) -> None:
        try:
            self.subsystem.attach(self.sock.accept()[0])
            self.sock.close()
        except Exception as e:
            print(sys.stderr, f"Error attaching stream to remote socket {e}")
            pass


class TcpServerSingleRemote:
    def __init__(self, port: int):
        super().__init__()
        self.connection_config = ("0.0.0.0", port)

    def __enter__(self) -> TcpSocketSubsystem:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(self.connection_config)
        self.sock.listen(0)
        self.subsystem = TcpSocketSubsystem()
        self.attacher = TcpServerSocketAttacher(self.sock, self.subsystem)
        self.attacher.start()

        return self.subsystem

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.subsystem.close()
        self.sock.close()
        self.attacher.join()
