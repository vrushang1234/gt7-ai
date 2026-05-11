import type { TurnSummary } from "../types";

type Props = {
  summaries: TurnSummary[];
  onTurnClick?: (turn: number) => void;
};

export function TurnFeed({ summaries, onTurnClick }: Props) {
  const recent = [...summaries].reverse();
  return (
    <div className="panel turn-feed">
      <h2>Turns</h2>
      {recent.length === 0 && <p>no turn data yet</p>}
      <div className="cards">
        {recent.map((s, i) => {
          const sum = s.summary;
          const clickable = !!onTurnClick;
          return (
            <div
              className={`card ${clickable ? "clickable" : ""}`}
              key={i}
              onClick={() => clickable && onTurnClick!(sum.turn)}
            >
              <div className="head">
                T{sum.turn} <span className="dir">({sum.direction})</span>{" "}
                <span className="lap">lap {sum.lap}</span>{" "}
                <span className="dur">{sum.duration_ms}ms</span>
              </div>
              {sum.entry && (
                <div className="phase-row">
                  <span className="tag">ENTRY</span>
                  dV avg {sum.entry.avg_delta_speed_kph.toFixed(1)} min{" "}
                  {sum.entry.min_delta_speed_kph.toFixed(1)}kph · dBrk avg{" "}
                  {sum.entry.avg_delta_brake_pct.toFixed(0)}% · line{" "}
                  {sum.entry.max_racing_line_offset_m.toFixed(1)}m
                </div>
              )}
              {sum.exit && (
                <div className="phase-row">
                  <span className="tag">EXIT</span>
                  dV avg {sum.exit.avg_delta_speed_kph.toFixed(1)}kph · dThr min{" "}
                  {sum.exit.min_delta_throttle_pct.toFixed(0)}% · line{" "}
                  {sum.exit.max_racing_line_offset_m.toFixed(1)}m
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
