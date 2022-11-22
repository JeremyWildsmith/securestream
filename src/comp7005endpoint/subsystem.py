from dataclasses import dataclass
from typing import Optional
import struct


@dataclass(frozen=True)
class Packet:
    read_offset: int
    write_offset: int
    recv_window_size: int
    data: bytes

    @staticmethod
    def load(data: bytes) -> 'Packet':
        return Packet(
            recv_window_size=struct.unpack("i", data[:4])[0],
            read_offset=struct.unpack("i", data[4:8])[0],
            write_offset=struct.unpack("i", data[8:12])[0],
            data=data[12:]
        )

    @staticmethod
    def ack(off: int, recv_window_size: int) -> 'Packet':
        return Packet(
            recv_window_size=recv_window_size,
            read_offset=off,
            write_offset=-1,
            data=bytes()
        )

    def save(self) -> bytes:
        return \
            struct.pack("i", self.recv_window_size) + \
            struct.pack("i", self.read_offset) + \
            struct.pack("i", self.write_offset) + \
            self.data


class SubsystemClosedException(Exception):
    pass


class Subsystem:
    def send(self, data: Packet):
        pass

    def recv(self) -> Optional[Packet]:
        pass

    def get_dataseg_limit(self) -> int:
        pass

    def close(self):
        pass

    def is_closed(self) -> bool:
        pass
