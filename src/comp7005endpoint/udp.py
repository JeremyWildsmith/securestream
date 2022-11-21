import math
import select
import socket
import struct
import sys
import threading
import time

from typing import Optional
from .subsystem import Subsystem, SubsystemClosedException, Packet


class UdpSocketSubsystem(Subsystem):
    def __init__(self, host: Optional[str], port: int, sock: socket.socket):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = sock
        self.closed = False
        self.recv_buffer = b''

    def send(self, packet: Packet):
        try:
            while self.host is None:
                time.sleep(0.1)

            packet_raw = packet.save()
            packet_len = len(packet_raw)
            transmit = struct.pack("I", packet_len) + packet_raw

            self.sock.sendto(transmit, (self.host, self.port))
        except ConnectionError:
            self.close()
            raise SubsystemClosedException()

    def recv(self) -> Optional[Packet]:
        expected = math.inf
        if len(self.recv_buffer) >= 4:
            expected = 4 + struct.unpack("I", self.recv_buffer[:4])[0]

        ready = select.select([self.sock], [], [], 0.01)

        if ready[0]:
            data, address = self.sock.recvfrom(4096)
            self.host, self.port = address

            self.recv_buffer += data

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
        self.sock.close()

    def is_closed(self) -> bool:
        return self.closed


class UdpClient:
    def __init__(self, host: str, port: int):
        super().__init__()
        self.host = host
        self.port = port

    def __enter__(self) -> Subsystem:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.sendto(b'', (self.host, self.port))
        return UdpSocketSubsystem(self.host, self.port, self.sock)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.sock.close()


class UdpServerSingleRemote:
    def __init__(self, port: int):
        super().__init__()
        self.port = port

    def __enter__(self) -> UdpSocketSubsystem:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", self.port))
        self.subsystem = UdpSocketSubsystem(None, self.port, self.sock)

        return self.subsystem

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.subsystem.close()
        self.sock.close()
