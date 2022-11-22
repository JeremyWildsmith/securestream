import math
import queue
import random
import threading
from queue import Queue, Empty
import time
from typing import Optional, Callable, List, Tuple, Dict

from .model.controller import ControllerModel
from .subsystem import Subsystem, SubsystemClosedException, Packet

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


class StreamWorker(threading.Thread):
    MAX_RECV = 100
    MAX_WINDOW_SIZE = 10
    RECV_WINDOW_HINT_SIZE = 3

    # We will cease transmitting for a maximum of half a second
    MAX_BACKOFF_PERIOD = 3

    def __init__(self, subsystem: Subsystem, data_in: Queue[bytes], data_out: Queue[bytes],
                 recv_filter: PacketMutator = None, transmit_filter: PacketMutator = None,
                 ack_timeout=2):
        super().__init__()

        self.recv_window: Dict[int, bytes] = {}
        self.window_size = 2
        self.ack_timeout = ack_timeout
        self.recv_filter = recv_filter
        self.transmit_filter = transmit_filter
        self.subsystem = subsystem
        self.data_in = data_in
        self.data_out = data_out

        self.stop_event = threading.Event()

        self.max_remote_read_offset = 0

        self.local_read_offset = 0
        self.local_write_offset = 0

        self.last_write_ack = time.time() #The last time our write was acked
        self.pending: List[Tuple[int, Packet]] = []
        self.recv_window_size_hint = []
        self.recv_buffer = b''

        self.backoff_since = 0

    def stop(self):
        self.stop_event.set()

    def write_raw(self, data: Packet):
        packet = self.transmit_filter(data)
        if packet is None:
            return

        self.subsystem.send(packet)

    def clean_pending(self):
        while self.pending and self.pending[0][0] <= self.max_remote_read_offset:
            self.pending = self.pending[1:]
            self.last_write_ack = time.time()

    def approximate_remote_window_size(self):
        if len(self.recv_window_size_hint) == 0:
            return 1

        r = math.floor(sum(self.recv_window_size_hint) / len(self.recv_window_size_hint))

        if r == 0:
            if self.backoff_since == 0:
                self.backoff_since = time.time()
        else:
            self.backoff_since = 0

        return r

    def try_receive(self):
        # Limit packet processing so we don't starve the logic loop
        for _ in range(StreamWorker.MAX_RECV):
            packet = self.subsystem.recv()

            if packet is None:
                break

            packet = self.recv_filter(packet)

            if packet is None:
                continue

            self.max_remote_read_offset = max(packet.read_offset, self.max_remote_read_offset)
            self.clean_pending()

            self.recv_window_size_hint = [self.recv_window_size_hint + [packet.recv_window_size]][:-StreamWorker.RECV_WINDOW_HINT_SIZE]

            if packet.write_offset >= self.local_read_offset and packet.write_offset not in self.recv_window:
                self.recv_window[packet.write_offset] = packet.data

                try:
                    while self.local_read_offset in self.recv_window:
                        src = self.recv_window[self.local_read_offset]
                        self.data_out.put(src)
                        del(self.recv_window[self.local_read_offset])
                        self.local_read_offset += 1
                except queue.Full:
                    pass


            # If the packet was not just an ack (IE transmitted data)
            # then we want to either acknowledge that data or let remote know what is missing
            if packet.write_offset >= 0:
                # Whether we accept the transmission or not, we should let remote know
                # what is expected next (in the event of a wrong transmission) or that
                # the prior transmission was acknowledged
                self.write_raw(Packet.ack(self.local_read_offset, self.data_out.maxsize - self.data_out.qsize()))

    def transmit_pending(self):
        self.clean_pending()

        if not self.pending:
            return

        for i in range(min(len(self.pending), self.window_size, self.approximate_remote_window_size())):
            p = self.pending[i]
            next_packet = Packet(self.local_read_offset, p[1].write_offset, self.data_out.maxsize - self.data_out.qsize(), p[1].data)
            self.write_raw(next_packet)

    def try_transmit(self):
        if self.pending and self.last_write_ack + self.ack_timeout < time.time():
            self.last_write_ack = time.time()
            self.transmit_pending()
            self.window_size = 1

        if len(self.pending) < min(self.approximate_remote_window_size(), self.window_size):
            try:
                data_in = self.data_in.get(block=False)

                new_packet = Packet(self.local_read_offset, self.local_write_offset, self.data_out.maxsize - self.data_out.qsize(), data_in)
                self.local_write_offset += 1
                self.pending.append((self.local_write_offset, new_packet))
                self.last_write_ack = time.time()
                self.write_raw(new_packet)

                self.window_size = min(self.window_size + 1, StreamWorker.MAX_WINDOW_SIZE)
            except Empty:
                pass

    def try_restore_backoff(self):
        if self.backoff_since > 0 and self.backoff_since + StreamWorker.MAX_BACKOFF_PERIOD < time.time():
            if self.approximate_remote_window_size() == 0:
                self.recv_window_size_hint = [1]

    def run(self) -> None:
        try:
            while not self.stop_event.is_set():
                try:
                    self.try_restore_backoff()
                    self.try_receive()
                    self.try_transmit()
                except ConnectionResetError:
                    break
        except BrokenPipeError:
            self.data_out.put(None)


class StreamForwarder:
    def __init__(self, src: Subsystem, dest: Subsystem, *, mutator: PacketMutator = None):
        self.src = src
        self.dest = dest
        self.recv_buffer = b''
        self.forward_filter = NoOpPacketMutator if mutator is None else mutator

    def write_raw(self, data: Packet):
        packet = self.forward_filter(data)
        if packet is None:
            return

        self.dest.send(packet)

    def poll(self):
        try:
            packet = self.src.recv()

            if packet is not None:
                self.write_raw(packet)
        except SubsystemClosedException:
            return False

        return True


class StreamBridge(threading.Thread):
    def __init__(self, sock_a: Subsystem, sock_b: Subsystem,
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

    def __init__(self, subsystem: Subsystem, *, recv_filter: Optional[PacketMutator] = None, transmit_filter: Optional[PacketMutator] = None):
        self.data_in = queue.Queue(maxsize=10)
        self.data_out = queue.Queue(maxsize=10)
        self.stream_worker: Optional[StreamWorker] = None
        self.recv_filter = recv_filter
        self.transmit_filter = transmit_filter
        self.closed = False
        self.max_packet_size = subsystem.get_dataseg_limit()

        self.stream_worker = StreamWorker(
            subsystem,
            self.data_in,
            self.data_out,
            NoOpPacketMutator() if self.recv_filter is None else self.recv_filter,
            NoOpPacketMutator() if self.transmit_filter is None else self.transmit_filter
        )

        self.stream_worker.start()

    def get_preferred_segment_size(self):
        return self.max_packet_size

    def write(self, data: bytes):
        segments = math.ceil(len(data) / self.max_packet_size)

        for i in range(segments):
            subset = data[i * self.max_packet_size : (i + 1) * self.max_packet_size]
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

        self.closed = True
