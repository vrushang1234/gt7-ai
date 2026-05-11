import type { Telemetry } from '../types'

type Props = {
  telemetry: Telemetry | null
}

function tempColor(c: number, hot: number, warn: number): string {
  if (c >= hot) return '#ff5959'
  if (c >= warn) return '#ffb84d'
  return '#79e09c'
}

function Bar({
  value,
  max,
  color,
}: {
  value: number
  max: number
  color: string
}) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100))
  return (
    <div className="bar">
      <div
        className="bar-fill"
        style={{ width: `${pct}%`, background: color }}
      />
    </div>
  )
}

function TyreCell({
  label,
  temp,
  slip,
}: {
  label: string
  temp: number
  slip: number
}) {
  return (
    <div className="tyre-cell">
      <div className="t-lbl">{label}</div>
      <div className="t-temp" style={{ color: tempColor(temp, 110, 90) }}>
        {temp.toFixed(0)}°C
      </div>
      <div className="t-slip">slip {slip.toFixed(2)}</div>
    </div>
  )
}

export function MetricsPanel({ telemetry }: Props) {
  if (!telemetry) {
    return (
      <div className="panel">
        <h2>Metrics</h2>
        <p>waiting…</p>
      </div>
    )
  }

  const t = telemetry as Telemetry & {
    tyre_temp_fl: number
    tyre_temp_fr: number
    tyre_temp_rl: number
    tyre_temp_rr: number
    tyre_slip_fl: number
    tyre_slip_fr: number
    tyre_slip_rl: number
    tyre_slip_rr: number
    boost: number
    oil_pressure: number
    suspension_fl: number
    suspension_fr: number
    suspension_rl: number
    suspension_rr: number
    ride_height_mm: number
    suggested_gear: number
  }

  return (
    <div className="panel metrics-panel">
      <h2>Car</h2>

      <div className="metric-grid">
        <div className="m-cell">
          <div className="lbl">Speed</div>
          <div className="num">{t.speed_kph.toFixed(0)} <span className="unit">kph</span></div>
        </div>
        <div className="m-cell">
          <div className="lbl">Boost</div>
          <div className="num">{t.boost.toFixed(2)} <span className="unit">bar</span></div>
        </div>
        <div className="m-cell">
          <div className="lbl">Sug. Gear</div>
          <div className="num">
            {t.suggested_gear > 0 && t.suggested_gear !== 15 ? t.suggested_gear : '-'}
          </div>
        </div>
      </div>

      <h3>Fuel</h3>
      <div className="lbl">
        {t.fuel.toFixed(1)} / {(t.fuel_pct > 0 ? t.fuel / (t.fuel_pct / 100) : 0).toFixed(1)} L · {t.fuel_pct.toFixed(0)}%
      </div>
      <Bar
        value={t.fuel_pct}
        max={100}
        color={t.fuel_pct < 15 ? '#ff5959' : t.fuel_pct < 30 ? '#ffb84d' : '#79e09c'}
      />

      <h3>Temps</h3>
      <div className="metric-grid">
        <div className="m-cell">
          <div className="lbl">Water</div>
          <div className="num" style={{ color: tempColor(t.water_temp, 105, 95) }}>
            {t.water_temp.toFixed(0)}°C
          </div>
        </div>
        <div className="m-cell">
          <div className="lbl">Oil</div>
          <div className="num" style={{ color: tempColor(t.oil_temp, 130, 110) }}>
            {t.oil_temp.toFixed(0)}°C
          </div>
        </div>
        <div className="m-cell">
          <div className="lbl">Oil P</div>
          <div className="num">{t.oil_pressure.toFixed(2)}</div>
        </div>
      </div>

      <h3>Tyres</h3>
      <div className="tyre-grid">
        <TyreCell label="FL" temp={t.tyre_temp_fl} slip={t.tyre_slip_fl} />
        <TyreCell label="FR" temp={t.tyre_temp_fr} slip={t.tyre_slip_fr} />
        <TyreCell label="RL" temp={t.tyre_temp_rl} slip={t.tyre_slip_rl} />
        <TyreCell label="RR" temp={t.tyre_temp_rr} slip={t.tyre_slip_rr} />
      </div>

      <h3>Suspension (mm)</h3>
      <div className="tyre-grid">
        <div className="tyre-cell"><div className="t-lbl">FL</div><div className="t-temp">{(t.suspension_fl * 1000).toFixed(0)}</div></div>
        <div className="tyre-cell"><div className="t-lbl">FR</div><div className="t-temp">{(t.suspension_fr * 1000).toFixed(0)}</div></div>
        <div className="tyre-cell"><div className="t-lbl">RL</div><div className="t-temp">{(t.suspension_rl * 1000).toFixed(0)}</div></div>
        <div className="tyre-cell"><div className="t-lbl">RR</div><div className="t-temp">{(t.suspension_rr * 1000).toFixed(0)}</div></div>
      </div>
      <div className="lbl" style={{ marginTop: 6 }}>
        Ride height: {t.ride_height_mm.toFixed(0)} mm
      </div>
    </div>
  )
}
