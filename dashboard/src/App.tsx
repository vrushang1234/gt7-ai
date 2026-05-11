import { useEffect, useRef, useState } from "react";
import "./App.css";
import { TrackMap } from "./components/TrackMap";
import { LiveStats } from "./components/LiveStats";
import { TurnFeed } from "./components/TurnFeed";
import { MetricsPanel } from "./components/MetricsPanel";
import { CoachPanel } from "./components/CoachPanel";
import type {
  Telemetry,
  CompareResult,
  TurnSummary,
  CoachMsg,
  ReferenceTrack,
  Tactic,
  StreamMessage,
} from "./types";

function App() {
  const [reference, setReference] = useState<ReferenceTrack | null>(null);
  const [tactics, setTactics] = useState<Tactic[] | null>(null);
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);
  const [compare, setCompare] = useState<CompareResult | null>(null);
  const [summaries, setSummaries] = useState<TurnSummary[]>([]);
  const [coach, setCoach] = useState<CoachMsg | null>(null);
  const [pendingTurn, setPendingTurn] = useState<number | null>(null);
  const [focusedTurn, setFocusedTurn] = useState<number | null>(null);
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);

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

  const requestCoach = async (turn: number) => {
    setFocusedTurn(turn);
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
              onTurnClick={requestCoach}
              onClearFocus={() => setFocusedTurn(null)}
            />
          </div>
        </div>
        <div className="col col-mid">
          <div className="stats-pane">
            <LiveStats telemetry={telemetry} compare={compare} />
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
