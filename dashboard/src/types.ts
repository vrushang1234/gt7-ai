export type Telemetry = {
  x: number
  z: number
  speed_kph: number
  speed_mph: number
  rpm: number
  rpm_rev_limiter: number
  gear: number
  suggested_gear: number
  throttle_pct: number
  brake_pct: number
  lap: number
  total_laps: number
  last_lap_ms: number
  best_lap_ms: number
  current_lap_ms?: number
  fuel: number
  fuel_pct: number
  oil_temp: number
  water_temp: number
}

export type CompareResult = {
  turn: number | null
  phase: 'entry' | 'exit' | 'straight'
  direction: string | null
  track_dist_m: number
  ref_idx: number
  dist_to_apex_along_track_m: number | null
  racing_line_offset_m: number
  delta_speed_kph: number
  delta_throttle_pct: number
  delta_brake_pct: number
  delta_gear: number
  delta_rpm: number
  ref_speed_kph: number
  ref_throttle_pct: number
  ref_brake_pct: number
  ref_gear: number
  ref_source: string
}

export type ReferenceSample = {
  idx: number
  x: number
  z: number
  track_dist_m: number
  speed_kph: number
  throttle_pct: number
  brake_pct: number
  gear: number
}

export type ReferenceTrack = {
  source: string
  lap: number
  duration_ms: number
  track_length_m: number
  samples: ReferenceSample[]
}

export type Tactic = {
  turn: number
  apex_x: number
  apex_z: number
  direction: string
  radius_m: number | null
  apex_track_dist_m: number | null
  apex_ref_idx: number | null
}

export type PhaseAggregate = {
  samples: number
  avg_delta_speed_kph: number
  min_delta_speed_kph: number
  max_delta_speed_kph: number
  avg_delta_throttle_pct: number
  max_delta_throttle_pct: number
  min_delta_throttle_pct: number
  avg_delta_brake_pct: number
  max_delta_brake_pct: number
  min_delta_brake_pct: number
  avg_racing_line_offset_m: number
  max_racing_line_offset_m: number
}

export type TurnSummary = {
  summary: {
    turn: number
    direction: string
    ref_source: string
    lap: number
    duration_ms: number
    total_samples: number
    entry: PhaseAggregate | null
    exit: PhaseAggregate | null
  }
  text: string
}

export type CoachMsg = {
  turn: number | null
  text: string
  audio_path: string | null
}

export type StreamMessage = {
  type:
    | 'snapshot_reference'
    | 'snapshot_tactics'
    | 'telemetry'
    | 'compare'
    | 'summary'
    | 'coach'
  data: unknown
  t: number
}
