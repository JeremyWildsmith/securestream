import math
import socket
import struct

class Stream(object):
    PACKET_DATASEG_SIZE = 1024

    # Size is equal to data segment size plus the two ack registers.
    PACKET_SIZE = PACKET_DATASEG_SIZE + 4 * 2

    def __init__(self, sock: socket.socket):
        self.sock = sock
        self.stream_buffer = b''
        self.remote_sync = 0
        self.local_sync = 0

    @staticmethod
    def _encode_packet(data: bytes, remote_ackno: int, local_ackno: int) -> bytes:
        if len(data) > Stream.PACKET_DATASEG_SIZE:
            raise Exception("Data is invalid.")

        databuffer = b''
        databuffer += struct.pack("I", remote_ackno)
        databuffer += struct.pack("I", local_ackno)
        databuffer += data
        databuffer += [b'\x00'] * (Stream.PACKET_DATASEG_SIZE - len(data))

        return databuffer

    @staticmethod
    def _decode_packet(data: bytes):
        return {
            "local_ack": struct.unpack("I", data[:4])[0],
            "remote_ack": struct.unpack("I", data[4:8])[0],
            "data": data[8:]
        }

    def _read_packet(self):
        while True:
            data = self._read_raw(Stream.PACKET_SIZE)
            packet = Stream._decode_packet(data)

            # Just wait for the proper packet, ignore everything else

            if packet["remote_ack"] != self.remote_sync + 1:
                continue

            self.remote_sync += 1

            self.local_sync = max(self.local_sync, packet["local_sync"])

    def _write_packet(self, data: bytes):
        self.local_sync += 1
        packet = Stream._encode_packet(data, self.remote_sync, self.local_sync)
        self._write_raw(packet)

    def _write_raw(self, data: bytes):
        pass

    def _read_raw(self, num_data: int) -> bytes:
        pass

    def grow_stream(self):
        pass

    def read(self, num_bytes):
        while len(self.stream_buffer) < num_bytes:
            self.grow_stream()

        parsed = self.stream_buffer[:num_bytes]
        self.stream_buffer = self.stream_buffer[num_bytes:]

        return parsed

    def write(self, data: bytes):
        for i in range(math.ceil(len(data) / Stream.PACKET_DATASEG_SIZE)):
            origin = i * Stream.PACKET_DATASEG_SIZE
            self._write_packet(data[origin:origin + Stream.PACKET_DATASEG_SIZE])
