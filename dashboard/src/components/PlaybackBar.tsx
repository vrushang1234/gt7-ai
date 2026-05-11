import type { PlaybackSample } from '../types'

type Props = {
  turn: number
  samples: PlaybackSample[]
  idx: number
  playing: boolean
  onPlayPause: () => void
  onSeek: (idx: number) => void
  onStop: () => void
  onSpeedChange: (speed: number) => void
  speed: number
}

function fmtMs(ms: number): string {
  const s = ms / 1000
  return `${s.toFixed(2)}s`
}

export function PlaybackBar({
  turn,
  samples,
  idx,
  playing,
  onPlayPause,
  onSeek,
  onStop,
  onSpeedChange,
  speed,
}: Props) {
  const cur = samples[idx]
  const tElapsed = cur ? cur.t_ms - samples[0].t_ms : 0
  const tTotal = samples.length
    ? samples[samples.length - 1].t_ms - samples[0].t_ms
    : 0
  return (
    <div className="playback-bar">
      <div className="row">
        <span className="tag">PLAYBACK T{turn}</span>
        <button onClick={onPlayPause}>{playing ? '⏸' : '▶'}</button>
        <button onClick={onStop}>⏹</button>
        <select
          value={speed}
          onChange={(e) => onSpeedChange(parseFloat(e.target.value))}
        >
          <option value={0.25}>0.25x</option>
          <option value={0.5}>0.5x</option>
          <option value={1}>1x</option>
          <option value={2}>2x</option>
          <option value={4}>4x</option>
        </select>
        <span className="time">
          {fmtMs(tElapsed)} / {fmtMs(tTotal)}
        </span>
      </div>
      <input
        type="range"
        min={0}
        max={Math.max(0, samples.length - 1)}
        value={idx}
        onChange={(e) => onSeek(parseInt(e.target.value))}
      />
      {cur && (
        <div className="row deltas">
          <span>spd {cur.speed_kph.toFixed(0)}/{cur.ref_speed_kph.toFixed(0)} kph</span>
          <span>thr {cur.throttle_pct.toFixed(0)}/{cur.ref_throttle_pct.toFixed(0)}%</span>
          <span>brk {cur.brake_pct.toFixed(0)}/{cur.ref_brake_pct.toFixed(0)}%</span>
          <span>gear {cur.gear}</span>
          <span>line {cur.racing_line_offset_m.toFixed(1)}m</span>
          <span className="phase">{cur.phase}</span>
        </div>
      )}
    </div>
  )
}
