import json
import socket
import struct
import sys
import time
from datetime import datetime

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


def i16(packet: bytes, offset: int) -> int:
    return struct.unpack_from("<h", packet, offset)[0]


def i32(packet: bytes, offset: int) -> int:
    return struct.unpack_from("<i", packet, offset)[0]


def safe_ratio(num: float, den: float) -> float:
    if abs(den) < 1e-6:
        return 0.0
    return num / den


def parse_packet(packet: bytes) -> dict:
    gear_byte = u8(packet, 0x90)

    speed_mps = f32(packet, 0x4C)
    speed_kph = speed_mps * 3.6
    speed_mph = speed_mps * 2.23694

    tyre_diameter_fl = f32(packet, 0xB4)
    tyre_diameter_fr = f32(packet, 0xB8)
    tyre_diameter_rl = f32(packet, 0xBC)
    tyre_diameter_rr = f32(packet, 0xC0)

    tyre_speed_fl = abs(3.6 * tyre_diameter_fl * f32(packet, 0xA4))
    tyre_speed_fr = abs(3.6 * tyre_diameter_fr * f32(packet, 0xA8))
    tyre_speed_rl = abs(3.6 * tyre_diameter_rl * f32(packet, 0xAC))
    tyre_speed_rr = abs(3.6 * tyre_diameter_rr * f32(packet, 0xB0))

    slip_divisor = speed_kph if speed_kph > 1.0 else 1.0

    flags = u8(packet, 0x8E)

    return {
        # local timestamp
        "recv_time": time.time(),
        # timing / race
        "tick": i32(packet, 0x70),
        "lap": u16(packet, 0x74),
        "total_laps": u16(packet, 0x76),
        "best_lap_ms": i32(packet, 0x78),
        "last_lap_ms": i32(packet, 0x7C),
        "time_on_track_ms": i32(packet, 0x80),
        "race_position": u16(packet, 0x84),
        "total_positions": u16(packet, 0x86),
        # car state
        "car_id": i32(packet, 0x124),
        "speed_mps": speed_mps,
        "speed_kph": speed_kph,
        "speed_mph": speed_mph,
        "rpm": f32(packet, 0x3C),
        "rpm_rev_warning": u16(packet, 0x88),
        "rpm_rev_limiter": u16(packet, 0x8A),
        "estimated_top_speed": i16(packet, 0x8C),
        "gear": gear_byte & 0x0F,
        "suggested_gear": gear_byte >> 4,
        "throttle_raw": u8(packet, 0x91),
        "brake_raw": u8(packet, 0x92),
        "throttle_pct": u8(packet, 0x91) / 2.55,
        "brake_pct": u8(packet, 0x92) / 2.55,
        "boost": f32(packet, 0x50) - 1.0,
        # fuel
        "fuel": f32(packet, 0x44),
        "fuel_capacity": f32(packet, 0x48),
        "fuel_pct": safe_ratio(f32(packet, 0x44), f32(packet, 0x48)) * 100.0,
        # temperatures / pressure
        "oil_temp": f32(packet, 0x5C),
        "water_temp": f32(packet, 0x58),
        "oil_pressure": f32(packet, 0x54),
        # tyre temps
        "tyre_temp_fl": f32(packet, 0x60),
        "tyre_temp_fr": f32(packet, 0x64),
        "tyre_temp_rl": f32(packet, 0x68),
        "tyre_temp_rr": f32(packet, 0x6C),
        # position
        "x": f32(packet, 0x04),
        "y": f32(packet, 0x08),
        "z": f32(packet, 0x0C),
        # velocity
        "velocity_x": f32(packet, 0x10),
        "velocity_y": f32(packet, 0x14),
        "velocity_z": f32(packet, 0x18),
        # rotation
        "rotation_pitch": f32(packet, 0x1C),
        "rotation_yaw": f32(packet, 0x20),
        "rotation_roll": f32(packet, 0x24),
        # angular velocity
        "angular_velocity_x": f32(packet, 0x2C),
        "angular_velocity_y": f32(packet, 0x30),
        "angular_velocity_z": f32(packet, 0x34),
        # ride height / suspension
        "ride_height_mm": f32(packet, 0x38) * 1000.0,
        "suspension_fl": f32(packet, 0xC4),
        "suspension_fr": f32(packet, 0xC8),
        "suspension_rl": f32(packet, 0xCC),
        "suspension_rr": f32(packet, 0xD0),
        # tyres
        "tyre_diameter_fl": tyre_diameter_fl,
        "tyre_diameter_fr": tyre_diameter_fr,
        "tyre_diameter_rl": tyre_diameter_rl,
        "tyre_diameter_rr": tyre_diameter_rr,
        "tyre_speed_fl": tyre_speed_fl,
        "tyre_speed_fr": tyre_speed_fr,
        "tyre_speed_rl": tyre_speed_rl,
        "tyre_speed_rr": tyre_speed_rr,
        "tyre_slip_fl": tyre_speed_fl / slip_divisor,
        "tyre_slip_fr": tyre_speed_fr / slip_divisor,
        "tyre_slip_rl": tyre_speed_rl / slip_divisor,
        "tyre_slip_rr": tyre_speed_rr / slip_divisor,
        # clutch
        "clutch": f32(packet, 0xF4),
        "clutch_engaged": f32(packet, 0xF8),
        "rpm_after_clutch": f32(packet, 0xFC),
        # gear ratios
        "gear_ratio_1": f32(packet, 0x104),
        "gear_ratio_2": f32(packet, 0x108),
        "gear_ratio_3": f32(packet, 0x10C),
        "gear_ratio_4": f32(packet, 0x110),
        "gear_ratio_5": f32(packet, 0x114),
        "gear_ratio_6": f32(packet, 0x118),
        "gear_ratio_7": f32(packet, 0x11C),
        "gear_ratio_8": f32(packet, 0x120),
        # flags
        "is_paused": bool(flags & 0b10),
        "in_race": bool(flags & 0b01),
    }


def send_heartbeat(sock: socket.socket, ps_ip: str):
    sock.sendto(b"A", (ps_ip, SEND_PORT))


def format_lap_time(ms: int) -> str:
    if ms <= 0:
        return "--:--.---"

    seconds = ms / 1000.0
    minutes = int(seconds // 60)
    seconds = seconds % 60

    return f"{minutes}:{seconds:06.3f}"


def print_telemetry(t: dict):
    print(
        f"Lap {t['lap']:>2} | "
        f"Cur {format_lap_time(t.get('current_lap_ms', 0))} | "
        f"Last {format_lap_time(t['last_lap_ms'])} | "
        f"Best {format_lap_time(t['best_lap_ms'])}"
    )


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <playstation_ip> [--record]")
        sys.exit(1)

    ps_ip = sys.argv[1]
    record = "--record" in sys.argv

    log_file = None
    if record:
        log_path = f"gt7_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
        log_file = open(log_path, "a", buffering=1)
        print(f"Recording telemetry to {log_path}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", RECV_PORT))
    sock.settimeout(2.0)

    print(f"Listening on UDP {RECV_PORT}")
    print(f"Sending heartbeat to {ps_ip}:{SEND_PORT}")
    print("Start driving in GT7. Press Ctrl+C to stop.\n")

    last_heartbeat = 0
    prev_lap = -1
    lap_start_track_ms = 0

    try:
        while True:
            now = time.time()

            if now - last_heartbeat > 10:
                send_heartbeat(sock, ps_ip)
                last_heartbeat = now

            try:
                data, addr = sock.recvfrom(4096)
            except socket.timeout:
                print("[debug] recv timeout, no packet")
                continue

            print(f"[debug] got {len(data)} bytes from {addr}")

            packet = decrypt_gt7_packet(data)
            if packet is None:
                print("[debug] decrypt failed (magic mismatch)")
                continue

            print(f"[debug] decrypted ok, paused={bool(u8(data, 0x8E) & 0b10)}")

            telemetry = parse_packet(packet)

            if telemetry["is_paused"]:
                continue

            lap = telemetry["lap"]
            track_ms = telemetry["time_on_track_ms"]
            if lap != prev_lap:
                lap_start_track_ms = track_ms
                prev_lap = lap
            telemetry["current_lap_ms"] = max(0, track_ms - lap_start_track_ms)

            print_telemetry(telemetry)

            if log_file is not None:
                log_file.write(json.dumps(telemetry) + "\n")

    except KeyboardInterrupt:
        print("\nStopped.")

    finally:
        sock.close()

        if log_file is not None:
            log_file.close()


if __name__ == "__main__":
    main()
