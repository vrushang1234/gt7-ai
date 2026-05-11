import type { CompareResult, Telemetry } from '../types'

type Props = {
  telemetry: Telemetry | null
  compare: CompareResult | null
}

function fmtLap(ms: number | undefined): string {
  if (!ms || ms <= 0) return '--:--.---'
  const s = ms / 1000
  const m = Math.floor(s / 60)
  const r = s - m * 60
  return `${m}:${r.toFixed(3).padStart(6, '0')}`
}

function Bar({ value, color }: { value: number; color: string }) {
  const v = Math.max(0, Math.min(100, value))
  return (
    <div className="bar">
      <div
        className="bar-fill"
        style={{ width: `${v}%`, background: color }}
      />
    </div>
  )
}

function Delta({ v, unit, neg }: { v: number; unit: string; neg?: boolean }) {
  const good = neg ? v < 0 : v > 0
  const color = Math.abs(v) < 0.5 ? '#888' : good ? '#3ee07a' : '#ff5959'
  return (
    <span style={{ color }}>
      {v >= 0 ? '+' : ''}
      {v.toFixed(1)}
      {unit}
    </span>
  )
}

export function LiveStats({ telemetry, compare }: Props) {
  if (!telemetry) {
    return <div className="panel"><h2>Live</h2><p>waiting for telemetry…</p></div>
  }
  return (
    <div className="panel live-stats">
      <h2>Live</h2>
      <div className="big-metric">
        <span className="num">{telemetry.speed_mph.toFixed(0)}</span>
        <span className="lbl">mph</span>
      </div>
      <div className="row">
        <div className="cell">
          <div className="lbl">Gear</div>
          <div className="num">{telemetry.gear}</div>
        </div>
        <div className="cell">
          <div className="lbl">RPM</div>
          <div className="num">{telemetry.rpm.toFixed(0)}</div>
        </div>
        <div className="cell">
          <div className="lbl">Lap</div>
          <div className="num">
            {telemetry.lap}/{telemetry.total_laps}
          </div>
        </div>
      </div>
      <div className="pedals">
        <div>
          <div className="lbl">Throttle {telemetry.throttle_pct.toFixed(0)}%</div>
          <Bar value={telemetry.throttle_pct} color="#3ee07a" />
        </div>
        <div>
          <div className="lbl">Brake {telemetry.brake_pct.toFixed(0)}%</div>
          <Bar value={telemetry.brake_pct} color="#ff5959" />
        </div>
      </div>
      <div className="laptimes">
        <div>
          <div className="lbl">Cur</div>
          <div>{fmtLap(telemetry.current_lap_ms)}</div>
        </div>
        <div>
          <div className="lbl">Last</div>
          <div>{fmtLap(telemetry.last_lap_ms)}</div>
        </div>
        <div>
          <div className="lbl">Best</div>
          <div>{fmtLap(telemetry.best_lap_ms)}</div>
        </div>
      </div>
      <h3>vs reference</h3>
      {compare ? (
        <div className="compare">
          <div className="phase">
            {compare.turn != null
              ? `T${compare.turn} (${compare.phase})`
              : 'straight'}
            <span className="off">
              {' '}
              line off {compare.racing_line_offset_m.toFixed(1)}m
            </span>
          </div>
          <div className="dgrid">
            <div>
              <span className="lbl">dV</span>
              <Delta v={compare.delta_speed_kph} unit="kph" />
            </div>
            <div>
              <span className="lbl">dThr</span>
              <Delta v={compare.delta_throttle_pct} unit="%" />
            </div>
            <div>
              <span className="lbl">dBrk</span>
              <Delta v={compare.delta_brake_pct} unit="%" neg />
            </div>
            <div>
              <span className="lbl">dG</span>
              <span>{compare.delta_gear >= 0 ? '+' : ''}{compare.delta_gear}</span>
            </div>
          </div>
          <div className="ref-src">ref: {compare.ref_source}</div>
        </div>
      ) : (
        <p>no comparison yet</p>
      )}
    </div>
  )
}
