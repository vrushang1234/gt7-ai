import json
import os
import sys
import time
from datetime import datetime

from crypto import decrypt_gt7_packet
from display import print_telemetry
from map_render import save_lap_map
from network import RECV_PORT, SEND_PORT, open_socket, send_heartbeat
from parser import parse_packet, u8


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <playstation_ip> [--record]")
        sys.exit(1)

    ps_ip = sys.argv[1]
    record = "--record" in sys.argv

    log_file = None
    if record:
        os.makedirs("logs", exist_ok=True)
        log_path = os.path.join(
            "logs", f"gt7_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
        )
        log_file = open(log_path, "a", buffering=1)
        print(f"Recording telemetry to {log_path}")

    sock = open_socket()

    print(f"Listening on UDP {RECV_PORT}")
    print(f"Sending heartbeat to {ps_ip}:{SEND_PORT}")
    print("Start driving in GT7. Press Ctrl+C to stop.\n")

    last_heartbeat = 0.0
    prev_lap = -1
    lap_start_track_ms = 0
    lap_xs: list[float] = []
    lap_zs: list[float] = []
    lap_thr: list[float] = []
    lap_brk: list[float] = []
    session_tag = datetime.now().strftime("%Y%m%d_%H%M%S")

    try:
        while True:
            now = time.time()

            if now - last_heartbeat > 1:
                send_heartbeat(sock, ps_ip)
                last_heartbeat = now

            try:
                data, addr = sock.recvfrom(4096)
            except TimeoutError:
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
                if prev_lap > 0 and lap_xs:
                    save_lap_map(prev_lap, lap_xs, lap_zs, lap_thr, lap_brk, session_tag)
                lap_xs = []
                lap_zs = []
                lap_thr = []
                lap_brk = []
                lap_start_track_ms = track_ms
                prev_lap = lap
            telemetry["current_lap_ms"] = max(0, track_ms - lap_start_track_ms)
            lap_xs.append(telemetry["x"])
            lap_zs.append(telemetry["z"])
            lap_thr.append(telemetry["throttle_pct"])
            lap_brk.append(telemetry["brake_pct"])

            print_telemetry(telemetry)

            if log_file is not None:
                log_file.write(json.dumps(telemetry) + "\n")

    except KeyboardInterrupt:
        print("\nStopped.")

    finally:
        if prev_lap > 0 and lap_xs:
            save_lap_map(prev_lap, lap_xs, lap_zs, lap_thr, lap_brk, session_tag)
        sock.close()

        if log_file is not None:
            log_file.close()


if __name__ == "__main__":
    main()
