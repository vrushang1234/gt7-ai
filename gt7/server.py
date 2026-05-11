import json
import os
import queue
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote


class TelemetryHub:
    def __init__(self) -> None:
        self.subscribers: list[queue.Queue] = []
        self.lock = threading.Lock()
        self.last_telemetry: dict | None = None
        self.last_compare: dict | None = None
        self.summaries: list[dict] = []
        self.last_coach: dict | None = None

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=500)
        with self.lock:
            self.subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self.lock:
            if q in self.subscribers:
                self.subscribers.remove(q)

    def push(self, event_type: str, data) -> None:
        msg = {"type": event_type, "data": data, "t": time.time()}
        if event_type == "telemetry":
            self.last_telemetry = msg
        elif event_type == "compare":
            self.last_compare = msg
        elif event_type == "summary":
            self.summaries.append(msg)
            if len(self.summaries) > 100:
                self.summaries.pop(0)
        elif event_type == "coach":
            self.last_coach = msg
        with self.lock:
            dead = []
            for q in self.subscribers:
                try:
                    q.put_nowait(msg)
                except queue.Full:
                    dead.append(q)
            for q in dead:
                self.subscribers.remove(q)


HUB = TelemetryHub()
COACH = None


def attach_coach(coach) -> None:
    global COACH
    COACH = coach


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args, **kwargs) -> None:
        pass

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.send_header("Access-Control-Allow-Methods", "GET")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/api/stream":
            self._stream()
        elif path == "/api/reference":
            self._serve_file("tactics/reference_track.json", "application/json")
        elif path == "/api/tactics":
            self._serve_file("tactics/best_tactics.json", "application/json")
        elif path == "/api/summaries":
            self._json({"summaries": HUB.summaries})
        elif path == "/api/coach":
            self._handle_coach()
        elif path.startswith("/audio/"):
            self._serve_file(unquote("audio/" + path[len("/audio/") :]), "audio/wav")
        elif path.startswith("/maps/"):
            self._serve_file(unquote("maps/" + path[len("/maps/") :]), "image/png")
        else:
            self.send_response(404)
            self._cors()
            self.end_headers()

    def _handle_coach(self) -> None:
        from urllib.parse import parse_qs, urlparse

        qs = parse_qs(urlparse(self.path).query)
        try:
            turn = int(qs.get("turn", ["0"])[0])
        except ValueError:
            self.send_response(400)
            self._cors()
            self.end_headers()
            return

        target = None
        for msg in reversed(HUB.summaries):
            data = msg.get("data", {})
            s = data.get("summary", {})
            if s.get("turn") == turn:
                target = data
                break

        print(
            f"[server] /api/coach turn={turn} "
            f"summaries={len(HUB.summaries)} "
            f"match={'yes' if target else 'no'} "
            f"coach_enabled={COACH is not None and getattr(COACH, 'enabled', False)}"
        )

        if target is None:
            self._json(
                {
                    "error": f"no summary stored for T{turn} yet (have {len(HUB.summaries)})",
                    "turn": turn,
                }
            )
            return
        if COACH is None or not getattr(COACH, "enabled", False):
            self._json({"error": "coach disabled (set GEMINI_API_KEY)"})
            return

        COACH.coach_async(target["summary"], target["text"])
        self._json(
            {
                "queued": True,
                "turn": turn,
                "summary_text": target["text"],
            }
        )

    def _json(self, obj) -> None:
        data = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def _serve_file(self, path: str, mime: str) -> None:
        if not os.path.exists(path):
            self.send_response(404)
            self._cors()
            self.end_headers()
            return
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self._cors()
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _send_event(self, msg: dict) -> None:
        payload = json.dumps(msg)
        self.wfile.write(f"data: {payload}\n\n".encode())
        self.wfile.flush()

    def _stream(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self._cors()
        self.end_headers()

        try:
            for name, path in (
                ("reference", "tactics/reference_track.json"),
                ("tactics", "tactics/best_tactics.json"),
            ):
                if os.path.exists(path):
                    with open(path) as f:
                        data = json.load(f)
                    self._send_event(
                        {"type": "snapshot_" + name, "data": data, "t": time.time()}
                    )
            for s in HUB.summaries[-10:]:
                self._send_event(s)
            if HUB.last_telemetry:
                self._send_event(HUB.last_telemetry)
            if HUB.last_compare:
                self._send_event(HUB.last_compare)
            if HUB.last_coach:
                self._send_event(HUB.last_coach)
        except (BrokenPipeError, ConnectionResetError):
            return

        q = HUB.subscribe()
        try:
            while True:
                try:
                    msg = q.get(timeout=15)
                    self._send_event(msg)
                except queue.Empty:
                    try:
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        break
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            HUB.unsubscribe(q)


def start_server(port: int = 8765) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"[server] listening on http://localhost:{port}")
    return srv
