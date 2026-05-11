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
