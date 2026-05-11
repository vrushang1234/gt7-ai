import json
import math
import os

TACTICS_PATH = os.path.join("tactics", "best_tactics.json")
REF_TRACK_PATH = os.path.join("tactics", "reference_track.json")

LINE_OFFSET_LIMIT_M = 50.0
TURN_PROXIMITY_M = 200.0
LOCAL_SEARCH_WINDOW = 60
FALLBACK_DIST_M = 30.0


def _signed_loop_dist(a: float, b: float, total: float) -> float:
    d = b - a
    if total <= 0:
        return d
    while d > total / 2:
        d -= total
    while d < -total / 2:
        d += total
    return d


class LiveCompare:
    def __init__(self, tactics_path: str = TACTICS_PATH, ref_path: str = REF_TRACK_PATH):
        self._tactics_path = tactics_path
        self._ref_path = ref_path
        self.ref_samples: list[dict] = []
        self.track_length_m = 0.0
        self.ref_meta = ""
        self.ref_duration_ms = 0
        self.turns: list[dict] = []
        self._last_idx = 0
        self.reload()

    def reload(self) -> None:
        ref_samples: list[dict] = []
        track_length_m = 0.0
        ref_meta = ""
        ref_duration_ms = 0
        turns: list[dict] = []

        if os.path.exists(self._ref_path):
            with open(self._ref_path) as f:
                rt = json.load(f)
            ref_samples = rt["samples"]
            track_length_m = rt.get("track_length_m", 0.0)
            ref_meta = f"{rt.get('source','?')} L{rt.get('lap','?')}"
            ref_duration_ms = rt.get("duration_ms", 0)

        if os.path.exists(self._tactics_path):
            with open(self._tactics_path) as f:
                data = json.load(f)
            for t in data:
                turns.append(
                    {
                        "turn": t["turn"],
                        "apex_x": t["apex_x"],
                        "apex_z": t["apex_z"],
                        "apex_track_dist_m": t.get("apex_track_dist_m"),
                        "direction": t.get("direction"),
                        "radius_m": t.get("radius_m"),
                    }
                )

        self.ref_samples = ref_samples
        self.track_length_m = track_length_m
        self.ref_meta = ref_meta
        self.ref_duration_ms = ref_duration_ms
        self.turns = turns
        self._last_idx = 0

    def loaded(self) -> bool:
        return bool(self.ref_samples)

    def _nearest_ref_idx(self, x: float, z: float) -> tuple[int, float]:
        n = len(self.ref_samples)
        if n == 0:
            return -1, 1e18

        lo = max(0, self._last_idx - LOCAL_SEARCH_WINDOW)
        hi = min(n, self._last_idx + LOCAL_SEARCH_WINDOW)
        best_i = lo
        best_d = 1e18
        for i in range(lo, hi):
            s = self.ref_samples[i]
            d = math.hypot(x - s["x"], z - s["z"])
            if d < best_d:
                best_d = d
                best_i = i

        if best_d > FALLBACK_DIST_M:
            for i in range(n):
                s = self.ref_samples[i]
                d = math.hypot(x - s["x"], z - s["z"])
                if d < best_d:
                    best_d = d
                    best_i = i

        self._last_idx = best_i
        return best_i, best_d

    def compare(self, telemetry: dict) -> dict | None:
        if not self.ref_samples:
            return None

        x, z = telemetry["x"], telemetry["z"]
        idx, line_off = self._nearest_ref_idx(x, z)
        if idx < 0 or line_off > LINE_OFFSET_LIMIT_M:
            return None

        ref = self.ref_samples[idx]
        cur_dist = ref["track_dist_m"]

        nearest_turn = None
        nearest_d = 1e18
        for t in self.turns:
            if t["apex_track_dist_m"] is None:
                continue
            d = _signed_loop_dist(cur_dist, t["apex_track_dist_m"], self.track_length_m)
            if abs(d) < abs(nearest_d):
                nearest_d = d
                nearest_turn = t

        if nearest_turn is None or abs(nearest_d) > TURN_PROXIMITY_M:
            phase = "straight"
            turn_id = None
            direction = None
        else:
            phase = "entry" if nearest_d > 0 else "exit"
            turn_id = nearest_turn["turn"]
            direction = nearest_turn["direction"]

        return {
            "turn": turn_id,
            "phase": phase,
            "direction": direction,
            "track_dist_m": cur_dist,
            "ref_idx": idx,
            "dist_to_apex_along_track_m": nearest_d if nearest_turn else None,
            "racing_line_offset_m": line_off,
            "delta_speed_kph": telemetry["speed_kph"] - ref["speed_kph"],
            "delta_throttle_pct": telemetry["throttle_pct"] - ref["throttle_pct"],
            "delta_brake_pct": telemetry["brake_pct"] - ref["brake_pct"],
            "delta_gear": telemetry["gear"] - ref["gear"],
            "delta_rpm": telemetry["rpm"] - ref["rpm"],
            "ref_speed_kph": ref["speed_kph"],
            "ref_throttle_pct": ref["throttle_pct"],
            "ref_brake_pct": ref["brake_pct"],
            "ref_gear": ref["gear"],
            "ref_source": self.ref_meta,
        }


def format_delta(c: dict) -> str:
    if c["turn"] is not None:
        head = f"T{c['turn']}({c['phase'][0].upper()})"
    else:
        head = "STR"
    return (
        f"{head:>6} "
        f"line {c['racing_line_offset_m']:>4.1f}m | "
        f"dV {c['delta_speed_kph']:+6.1f}kph "
        f"dThr {c['delta_throttle_pct']:+5.1f}% "
        f"dBrk {c['delta_brake_pct']:+5.1f}% "
        f"dG {c['delta_gear']:+d} "
        f"dRPM {c['delta_rpm']:+5.0f}"
    )
