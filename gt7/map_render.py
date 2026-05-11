import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402

from .geometry import compute_curvature, find_turns, smooth

MAPS_DIR = "maps"
TURNS_DIR = "turns"


def pedal_color(thr_pct: float, brk_pct: float) -> tuple[float, float, float]:
    if brk_pct >= thr_pct and brk_pct > 0:
        v = 0.25 + 0.75 * min(brk_pct / 100.0, 1.0)
        return (v, 0.0, 0.0)
    if thr_pct > 0:
        v = 0.25 + 0.75 * min(thr_pct / 100.0, 1.0)
        return (0.0, v, 0.0)
    return (0.4, 0.4, 0.4)


def save_lap_map(
    lap_num: int,
    xs: list[float],
    zs: list[float],
    thr: list[float],
    brk: list[float],
    session_tag: str,
):
    if len(xs) < 2:
        return

    plot_xs = xs
    plot_zs = [-z for z in zs]

    pts = [(plot_xs[i], plot_zs[i]) for i in range(len(plot_xs))]
    segs = [[pts[i], pts[i + 1]] for i in range(len(pts) - 1)]
    colors = [pedal_color(thr[i + 1], brk[i + 1]) for i in range(len(pts) - 1)]

    fig, ax = plt.subplots(figsize=(8, 8))
    lc = LineCollection(segs, colors=colors, linewidths=2)
    ax.add_collection(lc)

    ax.scatter(
        [plot_xs[0]],
        [plot_zs[0]],
        c="white",
        edgecolors="black",
        s=40,
        zorder=3,
        label="start",
    )
    ax.scatter(
        [plot_xs[-1]],
        [plot_zs[-1]],
        c="black",
        s=40,
        zorder=3,
        label="end",
    )

    kappa = smooth(compute_curvature(xs, zs), window=21)
    turns = find_turns(kappa, threshold=0.013, min_len=10, thr=thr, brk=brk)
    for n_, (s, e, apex, kp) in enumerate(turns, start=1):
        ax.scatter(
            [plot_xs[s]],
            [plot_zs[s]],
            marker="^",
            c="cyan",
            edgecolors="black",
            s=70,
            zorder=4,
        )
        ax.scatter(
            [plot_xs[e]],
            [plot_zs[e]],
            marker="v",
            c="magenta",
            edgecolors="black",
            s=70,
            zorder=4,
        )
        ax.scatter(
            [plot_xs[apex]],
            [plot_zs[apex]],
            c="yellow",
            edgecolors="black",
            s=80,
            zorder=4,
        )
        ax.annotate(
            f"T{n_}",
            (plot_xs[apex], plot_zs[apex]),
            textcoords="offset points",
            xytext=(6, 6),
            fontsize=9,
            fontweight="bold",
        )

    os.makedirs(TURNS_DIR, exist_ok=True)
    turns_path = os.path.join(TURNS_DIR, f"lap_{session_tag}_{lap_num:02d}_turns.json")
    with open(turns_path, "w") as f:
        json.dump(
            [
                {
                    "turn": n_,
                    "entry_idx": s,
                    "exit_idx": e,
                    "apex_idx": apex,
                    "entry_x": xs[s],
                    "entry_z": zs[s],
                    "exit_x": xs[e],
                    "exit_z": zs[e],
                    "apex_x": xs[apex],
                    "apex_z": zs[apex],
                    "peak_curvature": kp,
                    "direction": "left" if kp > 0 else "right",
                    "radius_m": (1.0 / abs(kp)) if abs(kp) > 1e-6 else None,
                }
                for n_, (s, e, apex, kp) in enumerate(turns, start=1)
            ],
            f,
            indent=2,
        )
    print(f"[turns] {len(turns)} turns -> {turns_path}")

    pad = 20
    ax.set_xlim(min(plot_xs) - pad, max(plot_xs) + pad)
    ax.set_ylim(min(plot_zs) - pad, max(plot_zs) + pad)
    ax.set_aspect("equal")
    ax.set_xlabel("x")
    ax.set_ylabel("z")
    ax.set_title(f"Lap {lap_num} — green=throttle, red=brake")
    ax.grid(True, alpha=0.3)

    os.makedirs(MAPS_DIR, exist_ok=True)
    path = os.path.join(MAPS_DIR, f"lap_{session_tag}_{lap_num:02d}.png")
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)

    print(f"[map] saved {path} ({len(xs)} pts)")
