from Crypto.Cipher import Salsa20

GT7_KEY = b"Simulator Interface Packet GT7 ver 0.0"


def decrypt_gt7_packet(data: bytes) -> bytes | None:
    seed = data[0x40:0x44]

    iv1 = int.from_bytes(seed, "little")
    iv2 = iv1 ^ 0xDEADBEAF

    nonce = iv2.to_bytes(4, "little") + iv1.to_bytes(4, "little")

    cipher = Salsa20.new(key=GT7_KEY[:32], nonce=nonce)
    decrypted = cipher.decrypt(data)

    magic = int.from_bytes(decrypted[0:4], "little")
    if magic != 0x47375330:
        return None

    return decrypted
