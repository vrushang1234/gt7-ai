import math


IDLE_FRAMES_TO_END = 60


def _phase_aggregate(records: list[tuple[dict, dict]], phase: str) -> dict | None:
    pts = [(c, t) for c, t in records if c["phase"] == phase]
    if not pts:
        return None

    dvs = [c["delta_speed_kph"] for c, _ in pts]
    dthrs = [c["delta_throttle_pct"] for c, _ in pts]
    dbrks = [c["delta_brake_pct"] for c, _ in pts]
    dgrs = [c["delta_gear"] for c, _ in pts]
    line_offs = [c["racing_line_offset_m"] for c, _ in pts]

    worst_speed_idx = min(range(len(pts)), key=lambda i: pts[i][0]["delta_speed_kph"])
    overbrake_idx = max(range(len(pts)), key=lambda i: pts[i][0]["delta_brake_pct"])
    underbrake_idx = min(range(len(pts)), key=lambda i: pts[i][0]["delta_brake_pct"])
    underthrottle_idx = min(
        range(len(pts)), key=lambda i: pts[i][0]["delta_throttle_pct"]
    )
    overthrottle_idx = max(
        range(len(pts)), key=lambda i: pts[i][0]["delta_throttle_pct"]
    )
    max_off_idx = max(range(len(pts)), key=lambda i: pts[i][0]["racing_line_offset_m"])

    def event(idx: int) -> dict:
        c, t = pts[idx]
        return {
            "x": t["x"],
            "z": t["z"],
            "track_dist_m": c.get("track_dist_m"),
            "dist_to_apex_along_track_m": c.get("dist_to_apex_along_track_m"),
            "racing_line_offset_m": c["racing_line_offset_m"],
            "speed_kph": t["speed_kph"],
            "ref_speed_kph": c["ref_speed_kph"],
            "delta_speed_kph": c["delta_speed_kph"],
            "throttle_pct": t["throttle_pct"],
            "ref_throttle_pct": c["ref_throttle_pct"],
            "delta_throttle_pct": c["delta_throttle_pct"],
            "brake_pct": t["brake_pct"],
            "ref_brake_pct": c["ref_brake_pct"],
            "delta_brake_pct": c["delta_brake_pct"],
            "gear": t["gear"],
            "ref_gear": c["ref_gear"],
        }

    return {
        "samples": len(pts),
        "avg_delta_speed_kph": sum(dvs) / len(dvs),
        "min_delta_speed_kph": min(dvs),
        "max_delta_speed_kph": max(dvs),
        "avg_delta_throttle_pct": sum(dthrs) / len(dthrs),
        "max_delta_throttle_pct": max(dthrs),
        "min_delta_throttle_pct": min(dthrs),
        "avg_delta_brake_pct": sum(dbrks) / len(dbrks),
        "max_delta_brake_pct": max(dbrks),
        "min_delta_brake_pct": min(dbrks),
        "avg_delta_gear": sum(dgrs) / len(dgrs),
        "avg_racing_line_offset_m": sum(line_offs) / len(line_offs),
        "max_racing_line_offset_m": max(line_offs),
        "worst_speed_event": event(worst_speed_idx),
        "overbrake_event": event(overbrake_idx),
        "underbrake_event": event(underbrake_idx),
        "underthrottle_event": event(underthrottle_idx),
        "overthrottle_event": event(overthrottle_idx),
        "max_line_offset_event": event(max_off_idx),
    }


class TurnSummaryBuilder:
    def __init__(self):
        self.current_turn: int | None = None
        self.records: list[tuple[dict, dict]] = []
        self.idle_frames = 0

    def _reset(self):
        self.current_turn = None
        self.records = []
        self.idle_frames = 0

    def _finalize(self) -> dict | None:
        if not self.records:
            return None
        first_c, first_t = self.records[0]
        last_c, last_t = self.records[-1]

        entry_agg = _phase_aggregate(self.records, "entry")
        exit_agg = _phase_aggregate(self.records, "exit")

        return {
            "turn": self.current_turn,
            "direction": first_c.get("direction"),
            "ref_source": first_c.get("ref_source"),
            "lap": first_t.get("lap"),
            "started_at_t_ms": first_t.get("time_on_track_ms"),
            "ended_at_t_ms": last_t.get("time_on_track_ms"),
            "duration_ms": (
                last_t.get("time_on_track_ms", 0) - first_t.get("time_on_track_ms", 0)
            ),
            "total_samples": len(self.records),
            "entry": entry_agg,
            "exit": exit_agg,
        }

    def push(self, cmp_result: dict | None, telemetry: dict) -> dict | None:
        turn = cmp_result["turn"] if cmp_result is not None else None

        if turn is None:
            if self.current_turn is not None:
                self.idle_frames += 1
                if self.idle_frames >= IDLE_FRAMES_TO_END:
                    summary = self._finalize()
                    self._reset()
                    return summary
            return None

        if self.current_turn is None:
            self.current_turn = turn
        elif turn != self.current_turn:
            summary = self._finalize()
            self._reset()
            self.current_turn = turn
            self.records.append((cmp_result, telemetry))
            return summary

        self.idle_frames = 0
        self.records.append((cmp_result, telemetry))
        return None

    def flush(self) -> dict | None:
        if self.current_turn is not None and self.records:
            s = self._finalize()
            self._reset()
            return s
        return None


def format_summary_text(s: dict) -> str:
    lines = [
        f"=== Turn {s['turn']} ({s['direction']}) lap {s['lap']} "
        f"duration {s['duration_ms']}ms ref={s['ref_source']} ===",
    ]
    for phase in ("entry", "exit"):
        agg = s.get(phase)
        if not agg:
            continue
        lines.append(
            f"[{phase}] n={agg['samples']} "
            f"dV avg{agg['avg_delta_speed_kph']:+.1f} "
            f"min{agg['min_delta_speed_kph']:+.1f} "
            f"max{agg['max_delta_speed_kph']:+.1f}kph | "
            f"dThr avg{agg['avg_delta_throttle_pct']:+.1f} "
            f"min{agg['min_delta_throttle_pct']:+.1f} "
            f"max{agg['max_delta_throttle_pct']:+.1f}% | "
            f"dBrk avg{agg['avg_delta_brake_pct']:+.1f} "
            f"min{agg['min_delta_brake_pct']:+.1f} "
            f"max{agg['max_delta_brake_pct']:+.1f}% | "
            f"line_off avg{agg['avg_racing_line_offset_m']:.1f} "
            f"max{agg['max_racing_line_offset_m']:.1f}m"
        )
    return "\n".join(lines)
