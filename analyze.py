import json
import math
import os
from glob import glob

from gt7.geometry import compute_curvature, find_turns, smooth

LOGS_DIR = "logs"
OUT_DIR = "tactics"
MATCH_RADIUS_M = 50.0
MIN_LAP_PACKETS = 100
MIN_DETECTIONS = 2

BRAKE_ON_PCT = 5.0
THROTTLE_LIFT_PCT = 5.0
THROTTLE_ON_PCT = 20.0
THROTTLE_FULL_PCT = 95.0
G = 9.81


def load_laps(paths: list[str]) -> list[dict]:
    laps: list[dict] = []
    for path in paths:
        with open(path) as f:
            packets = [json.loads(line) for line in f if line.strip()]
        by_lap: dict[int, list[dict]] = {}
        for p in packets:
            by_lap.setdefault(p["lap"], []).append(p)

        for lap_num, pkts in sorted(by_lap.items()):
            if lap_num <= 0 or len(pkts) < MIN_LAP_PACKETS:
                continue
            xs = [p["x"] for p in pkts]
            zs = [p["z"] for p in pkts]
            thr = [p["throttle_pct"] for p in pkts]
            brk = [p["brake_pct"] for p in pkts]
            speeds = [p["speed_kph"] for p in pkts]
            kappa = smooth(compute_curvature(xs, zs), window=21)
            turns = find_turns(kappa, threshold=0.013, min_len=10, thr=thr, brk=brk)
            laps.append(
                {
                    "source": path,
                    "lap": lap_num,
                    "packets": pkts,
                    "xs": xs,
                    "zs": zs,
                    "thr": thr,
                    "brk": brk,
                    "speeds": speeds,
                    "turns": turns,
                }
            )
    return laps


def _centroid(members: list[dict]) -> tuple[float, float]:
    cx = sum(m["x"] for m in members) / len(members)
    cz = sum(m["z"] for m in members) / len(members)
    return cx, cz


def build_reference_track(laps: list[dict]) -> dict | None:
    if not laps:
        return None

    def lap_duration(lap):
        return lap["packets"][-1]["time_on_track_ms"] - lap["packets"][0]["time_on_track_ms"]

    best = min(laps, key=lap_duration)
    pkts = best["packets"]
    t0 = pkts[0]["time_on_track_ms"]
    samples: list[dict] = []
    cum = 0.0
    for i, p in enumerate(pkts):
        if i > 0:
            prev = pkts[i - 1]
            cum += math.hypot(p["x"] - prev["x"], p["z"] - prev["z"])
        samples.append(
            {
                "idx": i,
                "x": p["x"],
                "z": p["z"],
                "track_dist_m": cum,
                "t_ms_from_lap_start": p["time_on_track_ms"] - t0,
                "speed_kph": p["speed_kph"],
                "speed_mps": p["speed_mps"],
                "throttle_pct": p["throttle_pct"],
                "brake_pct": p["brake_pct"],
                "gear": p["gear"],
                "rpm": p["rpm"],
                "yaw_rate_rad_s": p["angular_velocity_y"],
            }
        )
    return {
        "source": os.path.basename(best["source"]),
        "lap": best["lap"],
        "duration_ms": lap_duration(best),
        "track_length_m": cum,
        "samples": samples,
    }


def assign_apex_track_dist(canonical: list[dict], ref_track: dict) -> None:
    samples = ref_track["samples"]
    for c in canonical:
        ax, az = c["ref_apex_x"], c["ref_apex_z"]
        best_i = 0
        best_d = 1e18
        for i, s in enumerate(samples):
            d = math.hypot(s["x"] - ax, s["z"] - az)
            if d < best_d:
                best_d = d
                best_i = i
        c["apex_ref_idx"] = best_i
        c["apex_track_dist_m"] = samples[best_i]["track_dist_m"]


def build_canonical_turns(laps: list[dict]) -> list[dict]:
    all_apexes: list[dict] = []
    for lap in laps:
        for s, e, apex, kp in lap["turns"]:
            all_apexes.append(
                {
                    "lap": lap,
                    "s": s,
                    "apex": apex,
                    "e": e,
                    "kp": kp,
                    "x": lap["xs"][apex],
                    "z": lap["zs"][apex],
                }
            )

    clusters: list[dict] = []
    for ap in all_apexes:
        best_c = None
        best_d = 1e18
        for c in clusters:
            cx, cz = _centroid(c["members"])
            d = math.hypot(cx - ap["x"], cz - ap["z"])
            if d < best_d:
                best_d = d
                best_c = c
        if best_c is not None and best_d < MATCH_RADIUS_M:
            best_c["members"].append(ap)
        else:
            clusters.append({"members": [ap]})

    clusters = [c for c in clusters if len(c["members"]) >= MIN_DETECTIONS]

    ref = max(laps, key=lambda lap: len(lap["turns"]))
    for c in clusters:
        cx, cz = _centroid(c["members"])
        c["ref_apex_x"] = cx
        c["ref_apex_z"] = cz
        c["avg_peak_curvature"] = sum(m["kp"] for m in c["members"]) / len(c["members"])
        c["radius_m"] = (
            1.0 / abs(c["avg_peak_curvature"])
            if abs(c["avg_peak_curvature"]) > 1e-6
            else None
        )
        c["direction"] = "left" if c["avg_peak_curvature"] > 0 else "right"
        min_d = 1e18
        min_i = 0
        for i in range(len(ref["xs"])):
            d = math.hypot(ref["xs"][i] - cx, ref["zs"][i] - cz)
            if d < min_d:
                min_d = d
                min_i = i
        c["_order_idx"] = min_i

    clusters.sort(key=lambda c: c["_order_idx"])
    for ti, c in enumerate(clusters, start=1):
        c["turn"] = ti
        del c["_order_idx"]
    return clusters


def _segment_arrays(lap: dict, lo: int, hi: int) -> dict:
    pkts = lap["packets"][lo : hi + 1]
    n = len(pkts)
    xs = lap["xs"][lo : hi + 1]
    zs = lap["zs"][lo : hi + 1]
    speeds_kph = lap["speeds"][lo : hi + 1]
    speeds_mps = [p["speed_mps"] for p in pkts]
    thr = lap["thr"][lo : hi + 1]
    brk = lap["brk"][lo : hi + 1]
    gears = [p["gear"] for p in pkts]
    rpms = [p["rpm"] for p in pkts]
    yawrates = [p["angular_velocity_y"] for p in pkts]
    slip_fl = [p["tyre_slip_fl"] for p in pkts]
    slip_fr = [p["tyre_slip_fr"] for p in pkts]
    slip_rl = [p["tyre_slip_rl"] for p in pkts]
    slip_rr = [p["tyre_slip_rr"] for p in pkts]
    times = [p["time_on_track_ms"] for p in pkts]

    dist = [0.0] * n
    for i in range(1, n):
        dist[i] = dist[i - 1] + math.hypot(xs[i] - xs[i - 1], zs[i] - zs[i - 1])

    return {
        "n": n,
        "pkts": pkts,
        "xs": xs,
        "zs": zs,
        "speeds_kph": speeds_kph,
        "speeds_mps": speeds_mps,
        "thr": thr,
        "brk": brk,
        "gears": gears,
        "rpms": rpms,
        "yawrates": yawrates,
        "slip_fl": slip_fl,
        "slip_fr": slip_fr,
        "slip_rl": slip_rl,
        "slip_rr": slip_rr,
        "times": times,
        "dist": dist,
    }


def _first_idx(seq, pred, start: int = 0) -> int:
    for i in range(start, len(seq)):
        if pred(seq[i]):
            return i
    return -1


def _last_idx(seq, pred, end: int | None = None) -> int:
    upper = len(seq) - 1 if end is None else end
    for i in range(upper, -1, -1):
        if pred(seq[i]):
            return i
    return -1


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def _max_abs(xs):
    return max((abs(x) for x in xs), default=0.0)


def _slip_avgs(arr: dict) -> tuple[list[float], list[float]]:
    front = [(arr["slip_fl"][i] + arr["slip_fr"][i]) / 2 for i in range(arr["n"])]
    rear = [(arr["slip_rl"][i] + arr["slip_rr"][i]) / 2 for i in range(arr["n"])]
    return front, rear


def _lat_g(arr: dict) -> list[float]:
    return [
        (arr["speeds_mps"][i] * arr["yawrates"][i]) / G for i in range(arr["n"])
    ]


def reference_profile(arr: dict, apex_off: int) -> list[dict]:
    apex_t = arr["times"][apex_off]
    apex_d = arr["dist"][apex_off]
    front, rear = _slip_avgs(arr)
    lat_g = _lat_g(arr)
    out = []
    for i in range(arr["n"]):
        out.append(
            {
                "t_ms_rel_apex": arr["times"][i] - apex_t,
                "dist_m_rel_apex": arr["dist"][i] - apex_d,
                "x": arr["xs"][i],
                "z": arr["zs"][i],
                "speed_kph": arr["speeds_kph"][i],
                "throttle_pct": arr["thr"][i],
                "brake_pct": arr["brk"][i],
                "gear": arr["gears"][i],
                "rpm": arr["rpms"][i],
                "yaw_rate_rad_s": arr["yawrates"][i],
                "lat_g": lat_g[i],
                "slip_front_avg": front[i],
                "slip_rear_avg": rear[i],
                "balance": rear[i] - front[i],
            }
        )
    return out


def entry_metrics(lap: dict, lo: int, apex_idx: int) -> tuple[dict, dict]:
    arr = _segment_arrays(lap, lo, apex_idx)
    n = arr["n"]
    apex_off = n - 1

    brake_start = _first_idx(arr["brk"], lambda b: b >= BRAKE_ON_PCT)
    brake_release = _last_idx(arr["brk"], lambda b: b >= BRAKE_ON_PCT)
    max_brk = max(arr["brk"]) if arr["brk"] else 0.0
    max_brk_off = arr["brk"].index(max_brk) if arr["brk"] else 0

    throttle_lift = -1
    if brake_start >= 0:
        throttle_lift = _last_idx(
            arr["thr"], lambda t: t >= THROTTLE_LIFT_PCT, end=brake_start
        )
    else:
        throttle_lift = _last_idx(arr["thr"], lambda t: t >= THROTTLE_LIFT_PCT)

    coast_ms = 0
    if 0 <= throttle_lift < brake_start:
        coast_ms = arr["times"][brake_start] - arr["times"][throttle_lift]

    brake_duration_ms = 0
    if brake_start >= 0 and brake_release >= brake_start:
        brake_duration_ms = arr["times"][brake_release] - arr["times"][brake_start]

    initial_ramp_pct_s = 0.0
    if brake_start >= 0:
        target_t = arr["times"][brake_start] + 100
        end_i = brake_start
        while end_i < n - 1 and arr["times"][end_i] < target_t:
            end_i += 1
        if end_i > brake_start:
            dt = (arr["times"][end_i] - arr["times"][brake_start]) / 1000.0
            if dt > 0:
                initial_ramp_pct_s = (
                    arr["brk"][end_i] - arr["brk"][brake_start]
                ) / dt

    avg_brake_release_pct_s = 0.0
    if brake_release > max_brk_off:
        dt = (arr["times"][brake_release] - arr["times"][max_brk_off]) / 1000.0
        if dt > 0:
            avg_brake_release_pct_s = (
                arr["brk"][max_brk_off] - arr["brk"][brake_release]
            ) / dt

    downshifts = sum(1 for i in range(1, n) if arr["gears"][i] < arr["gears"][i - 1])

    front, rear = _slip_avgs(arr)
    lat_g = _lat_g(arr)

    def pt(off: int) -> dict | None:
        if off is None or off < 0 or off >= n:
            return None
        return {
            "x": arr["xs"][off],
            "z": arr["zs"][off],
            "t_ms": arr["times"][off],
            "dist_m": arr["dist"][off],
            "speed_kph": arr["speeds_kph"][off],
        }

    return (
        {
            "entry_idx": lo,
            "apex_idx": apex_idx,
            "brake_start_idx": (lo + brake_start) if brake_start >= 0 else None,
            "brake_release_idx": (lo + brake_release) if brake_release >= 0 else None,
            "max_brake_idx": lo + max_brk_off,
            "throttle_lift_idx": (lo + throttle_lift) if throttle_lift >= 0 else None,
            "points": {
                "entry": pt(0),
                "throttle_lift": pt(throttle_lift) if throttle_lift >= 0 else None,
                "brake_start": pt(brake_start) if brake_start >= 0 else None,
                "max_brake": pt(max_brk_off),
                "brake_release": pt(brake_release) if brake_release >= 0 else None,
                "apex": pt(apex_off),
            },
            "duration_ms": arr["times"][-1] - arr["times"][0] if n else 0,
            "distance_m": arr["dist"][-1] if n else 0.0,
            "entry_speed_kph": arr["speeds_kph"][0] if n else 0,
            "apex_speed_kph": arr["speeds_kph"][-1] if n else 0,
            "min_speed_kph": min(arr["speeds_kph"]) if n else 0,
            "speed_drop_kph": (arr["speeds_kph"][0] - min(arr["speeds_kph"]))
            if n
            else 0,
            "brake_start_speed_kph": arr["speeds_kph"][brake_start]
            if brake_start >= 0
            else None,
            "brake_start_dist_to_apex_m": (arr["dist"][-1] - arr["dist"][brake_start])
            if brake_start >= 0
            else None,
            "brake_start_time_to_apex_ms": (
                arr["times"][-1] - arr["times"][brake_start]
            )
            if brake_start >= 0
            else None,
            "max_brake_pct": max_brk,
            "brake_at_apex_pct": arr["brk"][-1] if n else 0,
            "brake_duration_ms": brake_duration_ms,
            "brake_initial_ramp_pct_per_s": initial_ramp_pct_s,
            "brake_release_rate_pct_per_s": avg_brake_release_pct_s,
            "trail_brake_distance_m": (
                arr["dist"][-1] - arr["dist"][max_brk_off]
            )
            if max_brk_off < n
            else 0.0,
            "coast_ms": coast_ms,
            "max_yaw_rate_rad_s": _max_abs(arr["yawrates"]),
            "yaw_rate_at_apex": arr["yawrates"][-1] if n else 0,
            "max_lat_g": max((abs(g) for g in lat_g), default=0.0),
            "lat_g_at_apex": lat_g[-1] if n else 0,
            "gear_at_entry": arr["gears"][0] if n else 0,
            "gear_at_apex": arr["gears"][-1] if n else 0,
            "downshift_count": downshifts,
            "rpm_at_apex": arr["rpms"][-1] if n else 0,
            "avg_slip_front": _mean(front),
            "avg_slip_rear": _mean(rear),
            "balance_indicator": _mean([rear[i] - front[i] for i in range(n)]),
            "max_understeer": max((front[i] - rear[i] for i in range(n)), default=0.0),
            "max_oversteer": max((rear[i] - front[i] for i in range(n)), default=0.0),
        },
        arr,
    )


def exit_metrics(lap: dict, apex_idx: int, hi: int) -> tuple[dict, dict]:
    arr = _segment_arrays(lap, apex_idx, hi)
    n = arr["n"]

    throttle_on = _first_idx(arr["thr"], lambda t: t >= THROTTLE_ON_PCT)
    full_throttle = _first_idx(arr["thr"], lambda t: t >= THROTTLE_FULL_PCT)
    max_thr = max(arr["thr"]) if arr["thr"] else 0.0
    max_thr_off = arr["thr"].index(max_thr) if arr["thr"] else 0

    upshifts = sum(1 for i in range(1, n) if arr["gears"][i] > arr["gears"][i - 1])

    apex_t = arr["times"][0] if n else 0

    duration_s = ((arr["times"][-1] - arr["times"][0]) / 1000.0) if n else 0.0
    avg_thr_ramp = (
        (arr["thr"][-1] - arr["thr"][0]) / duration_s if duration_s > 1e-3 else 0.0
    )

    initial_thr_ramp = 0.0
    if throttle_on >= 0:
        target_t = arr["times"][throttle_on] + 100
        end_i = throttle_on
        while end_i < n - 1 and arr["times"][end_i] < target_t:
            end_i += 1
        if end_i > throttle_on:
            dt = (arr["times"][end_i] - arr["times"][throttle_on]) / 1000.0
            if dt > 0:
                initial_thr_ramp = (
                    arr["thr"][end_i] - arr["thr"][throttle_on]
                ) / dt

    front, rear = _slip_avgs(arr)
    lat_g = _lat_g(arr)

    def pt(off: int) -> dict | None:
        if off is None or off < 0 or off >= n:
            return None
        return {
            "x": arr["xs"][off],
            "z": arr["zs"][off],
            "t_ms": arr["times"][off],
            "dist_m": arr["dist"][off],
            "speed_kph": arr["speeds_kph"][off],
        }

    return (
        {
            "apex_idx": apex_idx,
            "exit_idx": hi,
            "throttle_on_idx": (apex_idx + throttle_on) if throttle_on >= 0 else None,
            "full_throttle_idx": (apex_idx + full_throttle)
            if full_throttle >= 0
            else None,
            "max_throttle_idx": apex_idx + max_thr_off,
            "points": {
                "apex": pt(0),
                "throttle_on": pt(throttle_on) if throttle_on >= 0 else None,
                "full_throttle": pt(full_throttle) if full_throttle >= 0 else None,
                "max_throttle": pt(max_thr_off),
                "exit": pt(n - 1),
            },
            "duration_ms": arr["times"][-1] - arr["times"][0] if n else 0,
            "distance_m": arr["dist"][-1] if n else 0.0,
            "apex_speed_kph": arr["speeds_kph"][0] if n else 0,
            "exit_speed_kph": arr["speeds_kph"][-1] if n else 0,
            "speed_gain_kph": (arr["speeds_kph"][-1] - arr["speeds_kph"][0])
            if n
            else 0,
            "throttle_at_apex_pct": arr["thr"][0] if n else 0,
            "throttle_on_offset_ms": (arr["times"][throttle_on] - apex_t)
            if throttle_on >= 0
            else None,
            "throttle_on_dist_from_apex_m": arr["dist"][throttle_on]
            if throttle_on >= 0
            else None,
            "time_to_full_throttle_ms": (arr["times"][full_throttle] - apex_t)
            if full_throttle >= 0
            else None,
            "dist_to_full_throttle_m": arr["dist"][full_throttle]
            if full_throttle >= 0
            else None,
            "max_throttle_pct": max_thr,
            "avg_throttle_ramp_pct_per_s": avg_thr_ramp,
            "initial_throttle_ramp_pct_per_s": initial_thr_ramp,
            "max_yaw_rate_rad_s": _max_abs(arr["yawrates"]),
            "yaw_rate_at_apex": arr["yawrates"][0] if n else 0,
            "yaw_rate_at_exit": arr["yawrates"][-1] if n else 0,
            "max_lat_g": max((abs(g) for g in lat_g), default=0.0),
            "lat_g_at_exit": lat_g[-1] if n else 0,
            "gear_at_apex": arr["gears"][0] if n else 0,
            "gear_at_exit": arr["gears"][-1] if n else 0,
            "upshift_count": upshifts,
            "rpm_at_exit": arr["rpms"][-1] if n else 0,
            "avg_slip_front": _mean(front),
            "avg_slip_rear": _mean(rear),
            "balance_indicator": _mean([rear[i] - front[i] for i in range(n)]),
            "max_understeer": max((front[i] - rear[i] for i in range(n)), default=0.0),
            "max_oversteer": max((rear[i] - front[i] for i in range(n)), default=0.0),
        },
        arr,
    )


def serialize_segment(member: dict, kind: str) -> dict:
    lap = member["lap"]
    s, apex, e = member["s"], member["apex"], member["e"]
    if kind == "entry":
        metrics, arr = entry_metrics(lap, s, apex)
        apex_off = arr["n"] - 1
    else:
        metrics, arr = exit_metrics(lap, apex, e)
        apex_off = 0
    profile = reference_profile(arr, apex_off)
    return {
        "source_log": os.path.basename(lap["source"]),
        "source_lap": lap["lap"],
        "kind": kind,
        "metrics": metrics,
        "reference_profile": profile,
    }


def main():
    paths = sorted(glob(os.path.join(LOGS_DIR, "*.jsonl")))
    if not paths:
        print(f"no logs in {LOGS_DIR}/")
        return

    laps = load_laps(paths)
    if not laps:
        print("no usable laps (need lap > 0 and >= 100 packets)")
        return

    print(f"loaded {len(laps)} laps from {len(paths)} files")
    for lap in laps:
        print(
            f"  {os.path.basename(lap['source'])} lap {lap['lap']}: "
            f"{len(lap['packets'])} packets, {len(lap['turns'])} turns"
        )

    ref_track = build_reference_track(laps)
    canonical = build_canonical_turns(laps)
    if ref_track is not None:
        assign_apex_track_dist(canonical, ref_track)

    os.makedirs(OUT_DIR, exist_ok=True)
    if ref_track is not None:
        ref_path = os.path.join(OUT_DIR, "reference_track.json")
        with open(ref_path, "w") as f:
            json.dump(ref_track, f)
        print(
            f"saved reference track ({len(ref_track['samples'])} samples, "
            f"{ref_track['track_length_m']:.0f}m, "
            f"{ref_track['duration_ms']/1000:.3f}s) -> {ref_path}"
        )

    out: list[dict] = []
    for c in canonical:
        members = c["members"]
        if not members:
            continue

        per_lap_metrics = []
        for m in members:
            em, _ = entry_metrics(m["lap"], m["s"], m["apex"])
            xm, _ = exit_metrics(m["lap"], m["apex"], m["e"])
            per_lap_metrics.append(
                {
                    "source_log": os.path.basename(m["lap"]["source"]),
                    "source_lap": m["lap"]["lap"],
                    "entry_metrics": em,
                    "exit_metrics": xm,
                }
            )

        best_entry_m = max(members, key=lambda m: m["lap"]["speeds"][m["apex"]])
        best_exit_m = max(members, key=lambda m: m["lap"]["speeds"][m["e"]])

        out.append(
            {
                "turn": c["turn"],
                "apex_x": c["ref_apex_x"],
                "apex_z": c["ref_apex_z"],
                "apex_track_dist_m": c.get("apex_track_dist_m"),
                "apex_ref_idx": c.get("apex_ref_idx"),
                "direction": c["direction"],
                "avg_peak_curvature": c["avg_peak_curvature"],
                "radius_m": c["radius_m"],
                "lap_count": len(members),
                "all_laps": per_lap_metrics,
                "best_entry": serialize_segment(best_entry_m, "entry"),
                "best_exit": serialize_segment(best_exit_m, "exit"),
            }
        )

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, "best_tactics.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"saved {len(out)} turns -> {out_path}")

    summary_path = os.path.join(OUT_DIR, "best_tactics_summary.txt")
    with open(summary_path, "w") as f:
        for t in out:
            be = t["best_entry"]["metrics"]
            bx = t["best_exit"]["metrics"]
            radius_str = f"{t['radius_m']:.0f}m" if t["radius_m"] else "?"
            brk_dist = be.get("brake_start_dist_to_apex_m") or 0
            thr_on_dist = bx.get("throttle_on_dist_from_apex_m") or 0
            full_thr_dist = bx.get("dist_to_full_throttle_m") or 0
            f.write(
                f"T{t['turn']} ({t['direction']}, R={radius_str}): "
                f"ENTRY {t['best_entry']['source_log']} L{t['best_entry']['source_lap']} "
                f"brk@-{brk_dist:.0f}m "
                f"max_brk {be['max_brake_pct']:.0f}% "
                f"trail {be['brake_at_apex_pct']:.0f}% "
                f"apex {be['apex_speed_kph']:.1f}kph "
                f"latG {be['max_lat_g']:.2f} "
                f"| EXIT {t['best_exit']['source_log']} L{t['best_exit']['source_lap']} "
                f"thr_on@+{thr_on_dist:.0f}m "
                f"full@+{full_thr_dist:.0f}m "
                f"exit {bx['exit_speed_kph']:.1f}kph "
                f"gain +{bx['speed_gain_kph']:.1f}\n"
            )
    print(f"saved summary -> {summary_path}")


if __name__ == "__main__":
    main()
