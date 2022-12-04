from .stream import PacketMutator, Packet
import json


class RsaCryptor(PacketMutator):
    def __init__(self, key, n):
        self.key = key
        self.n = n

    def __call__(self, packet: 'Packet'):
        b = packet.save()

        num = int.from_bytes(b, "big")

        num = pow(num, self.key, self.n)

        encrypted = num.to_bytes((num.bit_length() + 7) // 8, "big")

        return packet.load(encrypted)


def save_key(file: str, key: int, n: int):
    with open(file, "w") as f:
        json.dump({"k": key, "n": n}, f)


def build_cryptor(file: str):
    with open(file, "r") as f:
        d = json.load(f)
        return RsaCryptor(d["k"], d["n"])
