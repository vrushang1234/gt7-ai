import socket

RECV_PORT = 33740
SEND_PORT = 33739


def send_heartbeat(sock: socket.socket, ps_ip: str):
    sock.sendto(b"A", (ps_ip, SEND_PORT))


def open_socket(timeout: float = 2.0) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", RECV_PORT))
    sock.settimeout(timeout)
    return sock
