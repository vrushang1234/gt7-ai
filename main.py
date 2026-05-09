import socket
import struct
import sys
import time

from Crypto.Cipher import Salsa20

GT7_KEY = b"Simulator Interface Packet GT7 ver 0.0"
RECV_PORT = 33740
SEND_PORT = 33739


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


def f32(packet: bytes, offset: int) -> float:
    return struct.unpack_from("<f", packet, offset)[0]


def u8(packet: bytes, offset: int) -> int:
    return struct.unpack_from("<B", packet, offset)[0]


def u16(packet: bytes, offset: int) -> int:
    return struct.unpack_from("<H", packet, offset)[0]


def i32(packet: bytes, offset: int) -> int:
    return struct.unpack_from("<i", packet, offset)[0]


def parse_packet(packet: bytes) -> dict:
    gear_byte = u8(packet, 0x90)

    return {
        "x": f32(packet, 0x04),
        "y": f32(packet, 0x08),
        "z": f32(packet, 0x0C),
        "speed_mps": f32(packet, 0x4C),
        "speed_mph": f32(packet, 0x4C) * 2.23694,
        "rpm": f32(packet, 0x3C),
        "throttle": u8(packet, 0x91),
        "brake": u8(packet, 0x92),
        "gear": gear_byte & 0x0F,
        "lap": u16(packet, 0x74),
        "race_position": u16(packet, 0x84),
        "tick": i32(packet, 0x70),
    }


def send_heartbeat(sock: socket.socket, ps_ip: str):
    sock.sendto(b"A", (ps_ip, SEND_PORT))


def main():
    if len(sys.argv) != 2:
        print("Usage: python gt7_udp_live.py <playstation_ip>")
        sys.exit(1)

    ps_ip = sys.argv[1]

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", RECV_PORT))
    sock.settimeout(2.0)

    print(f"Listening on UDP {RECV_PORT}")
    print(f"Sending heartbeat to {ps_ip}:{SEND_PORT}")
    print("Start driving in GT7. Press Ctrl+C to stop.\n")

    last_heartbeat = 0

    try:
        while True:
            now = time.time()

            if now - last_heartbeat > 10:
                send_heartbeat(sock, ps_ip)
                last_heartbeat = now

            try:
                data, _ = sock.recvfrom(4096)
            except socket.timeout:
                continue

            packet = decrypt_gt7_packet(data)
            if packet is None:
                continue

            t = parse_packet(packet)

            print(
                f"Lap {t['lap']:>2} | "
                f"Pos {t['race_position']:>2} | "
                f"{t['speed_mph']:>6.1f} mph | "
                f"RPM {t['rpm']:>7.0f} | "
                f"G {t['gear']} | "
                f"Throttle {t['throttle']:>3} | "
                f"Brake {t['brake']:>3} | "
                f"XYZ ({t['x']:.1f}, {t['y']:.1f}, {t['z']:.1f})",
            )

    except KeyboardInterrupt:
        print("\nStopped.")

    finally:
        sock.close()


if __name__ == "__main__":
    main()
