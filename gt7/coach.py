import os
import threading

try:
    from google import genai

    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

COACH_MODEL = "gemini-3-flash-preview"

SYSTEM_PROMPT = """You are an AI race engineer for Gran Turismo 7.
You receive a detailed telemetry comparison for ONE corner vs the driver's best reference lap.

Input shape:
- Turn ID, direction (left/right), lap number, total duration (ms).
- Entry phase aggregates: sample count, avg/min/max of dV (speed delta kph), dThr (throttle delta %), dBrk (brake delta %), avg/max racing-line offset (m).
- Exit phase aggregates: same shape.

Field semantics (driver minus reference, so positive = driver higher):
- dV: speed delta (kph).
- dThr: throttle delta (%).
- dBrk: brake delta (%).
- line_off: lateral distance from reference racing line (m). Always positive.

Interpretation hints:
- Negative entry dV with similar/less brake = over-slowing on approach; carry more speed.
- Positive entry dV plus higher dBrk = late braking compensated by hard brake; brake earlier.
- Negative exit dThr = late throttle reapplication; get on power sooner after apex.
- Positive exit dBrk = braking after apex (instability, mid-corner correction); smooth out.
- Negative exit dV = poor exit drive; could be late throttle, off-line, or missed apex.
- line_off 2-8m is workable. If max line_off > 8m, downweight that phase (different line).
- Big swings between min and max (wide range) on dV/dThr/dBrk = inconsistent within the phase.

Output format (plain text, no markdown asterisks):

VERDICT: <one short line summarizing where time was won/lost>

ENTRY:
- <observation citing specific numbers>
- <observation>

EXIT:
- <observation citing specific numbers>
- <observation>

ACTIONS:
1. <concrete change for next lap, e.g. "brake 10m later", "shift up earlier", "trail brake less">
2. <concrete change>

Priority order: apex speed, exit speed gain, throttle timing, brake consistency, line offset.
Be specific with numbers from input. Keep response under 14 lines. No preamble, no sign-off.
"""


class Coach:
    def __init__(self):
        self.enabled = False
        self.client = None

        if not HAS_GENAI:
            print("[coach] google-genai not installed; pip install google-genai")
            return
        if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
            print("[coach] GEMINI_API_KEY/GOOGLE_API_KEY not set; coach disabled")
            return
        try:
            self.client = genai.Client()
            self.enabled = True
            print("[coach] enabled (text only)")
        except Exception as e:
            print(f"[coach] init failed: {e}")

    def coach_async(self, summary: dict, summary_text: str) -> None:
        if not self.enabled:
            return
        threading.Thread(
            target=self._run,
            args=(summary, summary_text),
            daemon=True,
        ).start()

    def _run(self, summary: dict, summary_text: str) -> None:
        turn_id = summary.get("turn")
        try:
            prompt = SYSTEM_PROMPT + "\n\nInput:\n" + summary_text
            print(f"[coach] requesting Gemini for T{turn_id} ({len(prompt)} chars)")
            resp = self.client.models.generate_content(
                model=COACH_MODEL,
                contents=prompt,
            )
            advice = (resp.text or "").strip()
            if not advice:
                advice = "(Gemini returned empty response)"
            print(f"\n[coach T{turn_id}] {advice}\n")
            self._push(turn_id, advice)
        except Exception as e:
            err = f"Gemini error: {type(e).__name__}: {e}"
            print(f"[coach] {err}")
            self._push(turn_id, err)

    def _push(self, turn_id, text: str) -> None:
        try:
            from .server import HUB
            HUB.push(
                "coach",
                {"turn": turn_id, "text": text, "audio_path": None},
            )
        except Exception as e:
            print(f"[coach] HUB push failed: {e}")
