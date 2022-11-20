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

from .model.controller import ControllerModel

PacketMutator = Callable[['Packet'], Optional['Packet']]


class StatsRelay(PacketMutator):
    def __init__(self, key: str, controller: ControllerModel, *, inner: PacketMutator = None):
        self.controller = controller
        self.inner = inner
        self.key = key

    def __call__(self, packet: 'Packet'):
        if self.inner:
            packet = self.inner(packet)

        if packet:
            self.controller.post_delta(self.key)

        return packet


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
        packet = self.transmit_filter(data)
        if packet is None:
            return

        packet_raw = packet.save()
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

            if packet.write_offset == self.local_read_offset:
                self.local_read_offset += 1
                self.data_out.put(packet.data)

            # If the packet was not just an ack (IE transmitted data)
            # then we want to either acknowledge that data or let remote know what is missing
            if packet.write_offset >= 0:
                # Whether we accept the transmission or not, we should let remote know
                # what is expected next (in the event of a wrong transmission) or that
                # the prior transmission was acknowledged
                self.write_raw(Packet.ack(self.local_read_offset))

    def transmit_pending(self):
        if self.pending is None:
            return

        next_packet = Packet(self.local_read_offset, self.pending.write_offset, self.pending.data)
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
        try:
            while not self.stop_event.is_set():
                try:
                    self.try_receive()
                    self.try_transmit()
                except ConnectionResetError:
                    break
        except BrokenPipeError:
            self.data_out.put(None)


class StreamForwarder:
    def __init__(self, src: socket.socket, dest: socket.socket, *, mutator: PacketMutator = None):
        self.src = src
        self.dest = dest
        self.recv_buffer = b''
        self.forward_filter = NoOpPacketMutator if mutator is None else mutator

    def write_raw(self, data: Packet):
        packet = self.forward_filter(data)
        if packet is None:
            return

        packet_raw = packet.save()
        packet_len = len(packet_raw)
        transmit = struct.pack("I", packet_len) + packet_raw

        self.dest.sendall(transmit)

    def poll(self):
        try:
            expected = math.inf
            if len(self.recv_buffer) >= 4:
                expected = 4 + struct.unpack("I", self.recv_buffer[:4])[0]

            ready = select.select([self.src], [], [], 0.01)

            if ready[0]:
                self.recv_buffer += self.src.recv(4096)

            if len(self.recv_buffer) >= expected:
                data = self.recv_buffer[4:expected]
                self.recv_buffer = self.recv_buffer[expected:]
                self.write_raw(Packet.load(data))
        except ConnectionError:
            return False

        return True


class StreamBridge(threading.Thread):
    def __init__(self, sock_a: socket.socket, sock_b: socket.socket,
                 ab_filter: PacketMutator = None, ba_filter: PacketMutator = None):

        super().__init__()

        self.ab = StreamForwarder(sock_a, sock_b, mutator=ab_filter)
        self.ba = StreamForwarder(sock_b, sock_a, mutator=ba_filter)
        self.stop_event = threading.Event()

    def stop(self):
        self.stop_event.set()

    def run(self) -> None:
        while self.ab.poll() and self.ba.poll():
            time.sleep(0.001)


class Stream(object):
    PACKET_DATASEG_SIZE = 1024

    def __init__(self, *, recv_filter: Optional[PacketMutator] = None, transmit_filter: Optional[PacketMutator] = None):
        self.data_in = queue.Queue(maxsize=10)
        self.data_out = queue.Queue(maxsize=10)
        self.stream_worker: Optional[StreamWorker] = None
        self.recv_filter = recv_filter
        self.transmit_filter = transmit_filter
        self.closed = False

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
                    r = self.data_out.get(block=False)

                    if r is None:
                        self.closed = True
                        break

                    buffer += r
                except Empty:
                    break
        else:
            while len(buffer) < min_read:
                try:
                    r = self.data_out.get(timeout=timeout)

                    if r is None:
                        self.closed = True
                        break

                    buffer += r
                except Empty:
                    break

        return buffer

    def is_open(self):
        return not self.closed

    def close(self):
        self.data_out.put(None)
        if self.stream_worker:
            self.stream_worker.stop()
            self.stream_worker.join()
