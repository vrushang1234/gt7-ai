import { useEffect, useRef, useState } from "react";
import "./App.css";
import { TrackMap } from "./components/TrackMap";
import { LiveStats } from "./components/LiveStats";
import { TurnFeed } from "./components/TurnFeed";
import { MetricsPanel } from "./components/MetricsPanel";
import { CoachPanel } from "./components/CoachPanel";
import { PlaybackBar } from "./components/PlaybackBar";
import type {
  Telemetry,
  CompareResult,
  TurnSummary,
  CoachMsg,
  ReferenceTrack,
  Tactic,
  StreamMessage,
  PlaybackSample,
} from "./types";

type Playback = {
  turn: number;
  samples: PlaybackSample[];
  idx: number;
  playing: boolean;
  speed: number;
};

function App() {
  const [reference, setReference] = useState<ReferenceTrack | null>(null);
  const [tactics, setTactics] = useState<Tactic[] | null>(null);
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);
  const [compare, setCompare] = useState<CompareResult | null>(null);
  const [summaries, setSummaries] = useState<TurnSummary[]>([]);
  const [coach, setCoach] = useState<CoachMsg | null>(null);
  const [coachCache, setCoachCache] = useState<Record<number, CoachMsg>>({});
  const [pendingTurn, setPendingTurn] = useState<number | null>(null);
  const [focusedTurn, setFocusedTurn] = useState<number | null>(null);
  const [playback, setPlayback] = useState<Playback | null>(null);
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);
  const playbackRef = useRef<Playback | null>(null);
  playbackRef.current = playback;

  useEffect(() => {
    const es = new EventSource("/api/stream");
    esRef.current = es;

    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);

    es.onmessage = (e) => {
      try {
        const msg: StreamMessage = JSON.parse(e.data);
        switch (msg.type) {
          case "snapshot_reference":
            setReference(msg.data as ReferenceTrack);
            break;
          case "snapshot_tactics":
            setTactics(msg.data as Tactic[]);
            break;
          case "telemetry":
            setTelemetry(msg.data as Telemetry);
            break;
          case "compare":
            setCompare(msg.data as CompareResult);
            break;
          case "summary":
            setSummaries((prev) => [
              ...prev.slice(-19),
              msg.data as TurnSummary,
            ]);
            break;
          case "coach": {
            const c = msg.data as CoachMsg;
            setCoach(c);
            setPendingTurn((p) => (p === c.turn ? null : p));
            if (c.turn != null) {
              setCoachCache((prev) => ({ ...prev, [c.turn as number]: c }));
            }
            break;
          }
        }
      } catch {
        /* ignore */
      }
    };

    return () => {
      es.close();
    };
  }, []);

  // Playback ticker — advances idx based on real elapsed time scaled by speed
  useEffect(() => {
    if (!playback?.playing) return;
    const startedAt = performance.now();
    const startIdx = playback.idx;
    const samples = playback.samples;
    const t0 = samples[startIdx]?.t_ms ?? 0;
    const speed = playback.speed;

    let raf = 0;
    const step = () => {
      const elapsed = (performance.now() - startedAt) * speed;
      const target = t0 + elapsed;
      let i = startIdx;
      while (i < samples.length - 1 && samples[i + 1].t_ms <= target) i++;
      if (i >= samples.length - 1) {
        setPlayback((p) =>
          p ? { ...p, idx: samples.length - 1, playing: false } : p,
        );
        return;
      }
      setPlayback((p) => (p ? { ...p, idx: i } : p));
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
    // restart effect when play/pause toggles or speed changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playback?.playing, playback?.speed]);

  const requestCoach = async (turn: number) => {
    setFocusedTurn(turn);

    // Start playback for latest summary of this turn (if available)
    const matching = [...summaries]
      .reverse()
      .find((s) => s.summary.turn === turn);
    if (matching?.summary.samples && matching.summary.samples.length > 1) {
      setPlayback({
        turn,
        samples: matching.summary.samples,
        idx: 0,
        playing: true,
        speed: 1,
      });
    } else {
      setPlayback(null);
    }

    if (coachCache[turn]) {
      setCoach(coachCache[turn]);
      setPendingTurn(null);
      return;
    }

    setPendingTurn(turn);
    try {
      const r = await fetch(`/api/coach?turn=${turn}`);
      const j = await r.json();
      if (j.error) {
        setPendingTurn(null);
        setCoach({ turn, text: `error: ${j.error}`, audio_path: null });
      }
    } catch (e) {
      setPendingTurn(null);
      setCoach({ turn, text: `request failed: ${e}`, audio_path: null });
    }
  };

  const playbackForMap = playback
    ? {
        sample: playback.samples[playback.idx],
        trail: playback.samples.slice(0, playback.idx + 1),
      }
    : null;

  const playbackTelemetry: Telemetry | null = playback
    ? ({
        ...(telemetry ?? ({} as Telemetry)),
        x: playback.samples[playback.idx].x,
        z: playback.samples[playback.idx].z,
        speed_kph: playback.samples[playback.idx].speed_kph,
        speed_mph: playback.samples[playback.idx].speed_kph * 0.621371,
        throttle_pct: playback.samples[playback.idx].throttle_pct,
        brake_pct: playback.samples[playback.idx].brake_pct,
        gear: playback.samples[playback.idx].gear,
        rpm: playback.samples[playback.idx].rpm,
      } as Telemetry)
    : telemetry;

  return (
    <div className="dashboard">
      <header className="topbar">
        <h1>GT7 Live Dashboard</h1>
        <div className={`status ${connected ? "ok" : "bad"}`}>
          {connected ? "connected" : "disconnected"}
        </div>
      </header>
      <div className="grid">
        <div className="col col-map">
          <div className="map-pane">
            <TrackMap
              reference={reference}
              tactics={tactics}
              telemetry={telemetry}
              focusedTurn={focusedTurn}
              playback={playbackForMap}
              onTurnClick={requestCoach}
              onClearFocus={() => {
                setFocusedTurn(null);
                setPlayback(null);
              }}
            />
          </div>
          {playback && (
            <PlaybackBar
              turn={playback.turn}
              samples={playback.samples}
              idx={playback.idx}
              playing={playback.playing}
              speed={playback.speed}
              onPlayPause={() =>
                setPlayback((p) => (p ? { ...p, playing: !p.playing } : p))
              }
              onSeek={(i) =>
                setPlayback((p) => (p ? { ...p, idx: i, playing: false } : p))
              }
              onStop={() => setPlayback(null)}
              onSpeedChange={(s) =>
                setPlayback((p) => (p ? { ...p, speed: s } : p))
              }
            />
          )}
        </div>
        <div className="col col-mid">
          <div className="stats-pane">
            <LiveStats telemetry={playbackTelemetry} compare={compare} />
          </div>
          <div className="feed-pane">
            <TurnFeed summaries={summaries} onTurnClick={requestCoach} />
          </div>
        </div>
        <div className="col col-right">
          <div className="metrics-pane">
            <MetricsPanel telemetry={telemetry} />
          </div>
          <div className="coach-pane">
            <CoachPanel coach={coach} pending={pendingTurn} />
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
