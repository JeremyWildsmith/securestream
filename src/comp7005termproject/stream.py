import math
import queue
import random
import socket
import struct
import threading
import select
from dataclasses import dataclass
from queue import Queue, Empty
import time
from typing import Optional, Callable


PacketMutator = Callable[['Packet'], Optional['Packet']]


class NoOpPacketMutator(PacketMutator):
    def __call__(self, packet: 'Packet'):
        return packet


class RandomDropMutator(PacketMutator):
    def __init__(self, chance: float = 0.0):
        self.chance = chance

    def set_drop(self, chance: float):
        self.chance = chance

    def __call__(self, packet):
        return None if random.random() <= self.chance else packet


@dataclass(frozen=True)
class Packet:
    read_offset: int
    write_offset: int
    data: bytes

    @staticmethod
    def load(data: bytes) -> 'Packet':
        return Packet(
            read_offset = struct.unpack("i", data[:4])[0],
            write_offset = struct.unpack("i", data[4:8])[0],
            data = data[8:]
        )

    @staticmethod
    def ack(off: int) -> 'Packet':
        return Packet(
            read_offset = off,
            write_offset = -1,
            data = bytes()
        )

    def save(self) -> bytes:
        return \
            struct.pack("i", self.read_offset) + \
            struct.pack("i", self.write_offset) + \
            self.data


class StreamWorker(threading.Thread):
    def __init__(self, sock: socket.socket, data_in: Queue[bytes], data_out: Queue[bytes],
                 recv_filter: PacketMutator = None, transmit_filter: PacketMutator = None,
                 ack_timeout=2):
        super().__init__()

        self.ack_timeout = ack_timeout
        self.recv_filter = recv_filter
        self.transmit_filter = transmit_filter
        self.sock = sock
        self.data_in = data_in
        self.data_out = data_out
        self.sock.setblocking(False)

        self.stop_event = threading.Event()

        self.local_read_offset = 0
        self.local_write_offset = 0

        self.last_write_ack = time.time() #The last time our write was acked
        self.pending: Optional[Packet] = None

        self.recv_buffer = b''

    def stop(self):
        self.stop_event.set()

    def write_raw(self, data: Packet):
        packet_raw = data.save()
        packet_len = len(packet_raw)
        transmit = struct.pack("I", packet_len) + packet_raw

        self.sock.sendall(transmit)

    def try_receive(self):
        expected = math.inf
        if len(self.recv_buffer) >= 4:
            expected = 4 + struct.unpack("I", self.recv_buffer[:4])[0]

        ready = select.select([self.sock], [], [], 0.01)

        if ready[0]:
            self.recv_buffer += self.sock.recv(4096)

        if len(self.recv_buffer) >= expected:
            data = self.recv_buffer[4:expected]
            self.recv_buffer = self.recv_buffer[expected:]
            packet = self.recv_filter(Packet.load(data))

            if packet is None:
                return

            if packet.read_offset == self.local_write_offset and self.pending is not None:
                self.pending = None

            if packet.write_offset != self.local_read_offset:
                return

            self.local_read_offset += 1
            self.data_out.put(packet.data)
            self.write_raw(Packet.ack(self.local_read_offset))

    def transmit_pending(self):
        if self.pending is None:
            return

        next_packet = Packet(self.local_read_offset, self.pending.write_offset, self.pending.data)
        next_packet = self.transmit_filter(next_packet)

        if next_packet is not None:
            self.write_raw(next_packet)

    def try_transmit(self):
        if self.pending:
            if self.last_write_ack + self.ack_timeout > time.time():
                return

            self.last_write_ack = time.time()
            self.transmit_pending()
        else:
            try:
                data_in = self.data_in.get(block=False)

                self.pending = Packet(self.local_read_offset, self.local_write_offset, data_in)
                self.last_write_ack = time.time()
                self.transmit_pending()
                self.local_write_offset += 1
            except Empty:
                pass

    def run(self) -> None:
        while not self.stop_event.is_set():
            self.try_receive()
            self.try_transmit()


class Stream(object):
    PACKET_DATASEG_SIZE = 1024

    def __init__(self, *, recv_filter: Optional[PacketMutator] = None, transmit_filter: Optional[PacketMutator] = None):
        self.data_in = queue.Queue(maxsize=10)
        self.data_out = queue.Queue(maxsize=10)
        self.stream_worker: Optional[StreamWorker] = None
        self.recv_filter = recv_filter
        self.transmit_filter = transmit_filter

    def attach(self, sock: socket.socket):
        if self.stream_worker is not None:
            raise Exception("Already attached")

        self.stream_worker = StreamWorker(
            sock,
            self.data_in,
            self.data_out,
            NoOpPacketMutator() if self.recv_filter is None else self.recv_filter,
            NoOpPacketMutator() if self.transmit_filter is None else self.transmit_filter
        )
        self.stream_worker.start()

    def write(self, data: bytes):
        segments = math.ceil(len(data) / Stream.PACKET_DATASEG_SIZE)

        for i in range(segments):
            subset = data[i * Stream.PACKET_DATASEG_SIZE : (i + 1) * Stream.PACKET_DATASEG_SIZE]
            self.data_in.put(subset)

    def read(self, min_read: int = 0, timeout=None) -> bytes:
        buffer = b''

        if min_read <= 0:
            while True:
                try:
                    buffer += self.data_out.get(block=False)
                except Empty:
                    break
        else:
            while len(buffer) < min_read:
                try:
                    buffer += self.data_out.get(timeout=timeout)
                except Empty:
                    break
        return buffer

    def close(self):
        if self.stream_worker:
            self.stream_worker.stop()
            self.stream_worker.join()