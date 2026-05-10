import math


def compute_curvature(xs: list[float], zs: list[float]) -> list[float]:
    n = len(xs)
    k = [0.0] * n
    for i in range(1, n - 1):
        ax_, az_ = xs[i] - xs[i - 1], zs[i] - zs[i - 1]
        bx_, bz_ = xs[i + 1] - xs[i], zs[i + 1] - zs[i]
        cross = ax_ * bz_ - az_ * bx_
        dot = ax_ * bx_ + az_ * bz_
        angle = math.atan2(cross, dot)
        arc = (math.hypot(ax_, az_) + math.hypot(bx_, bz_)) / 2.0
        if arc < 1e-6:
            continue
        k[i] = angle / arc
    return k


def smooth(arr: list[float], window: int = 15) -> list[float]:
    n = len(arr)
    out = [0.0] * n
    half = window // 2
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        out[i] = sum(arr[lo:hi]) / (hi - lo)
    return out


def find_turns(
    kappa: list[float],
    threshold: float = 0.005,
    min_len: int = 10,
    thr: list[float] | None = None,
    brk: list[float] | None = None,
    brake_lookback: int = 120,
    brake_on: float = 5.0,
    throttle_full: float = 80.0,
) -> list[tuple[int, int, int, float]]:
    turns: list[tuple[int, int, int, float]] = []
    n = len(kappa)
    thr_s = smooth(thr, window=11) if thr is not None else None
    brk_s = smooth(brk, window=11) if brk is not None else None

    i = 0
    while i < n:
        if abs(kappa[i]) < threshold:
            i += 1
            continue
        sign = 1 if kappa[i] > 0 else -1
        start = i
        j = i
        while (
            j < n and abs(kappa[j]) >= threshold and (1 if kappa[j] > 0 else -1) == sign
        ):
            j += 1
        run_end = j - 1
        if run_end - start + 1 < min_len:
            i = j
            continue

        seg = kappa[start : run_end + 1]
        peak_off = max(range(len(seg)), key=lambda k_: abs(seg[k_]))
        apex = start + peak_off

        entry_idx = start
        if brk_s is not None:
            lo = max(0, start - brake_lookback)
            earliest = start
            for b in range(start, lo - 1, -1):
                if brk_s[b] > brake_on:
                    earliest = b
                else:
                    if start - b > 5 and earliest < start:
                        break
            entry_idx = earliest

        if thr_s is None:
            exit_idx = run_end
        else:
            exit_idx = run_end
            k = apex + 1
            while k < n:
                kappa_low = abs(kappa[k]) < threshold
                rising = k + 1 < n and thr_s[k + 1] > thr_s[k]
                full = thr_s[k] >= throttle_full
                if kappa_low and (full or rising):
                    exit_idx = k
                    if full:
                        break
                if full and kappa_low:
                    exit_idx = k
                    break
                k += 1

        turns.append((entry_idx, exit_idx, apex, seg[peak_off]))
        i = max(j, exit_idx + 1)
    return turns
