import type { CoachMsg } from '../types'

type Props = {
  coach: CoachMsg | null
  pending: number | null
}

export function CoachPanel({ coach, pending }: Props) {
  const isStale = coach && pending !== null && coach.turn !== pending
  return (
    <div className="panel coach-panel">
      <h2>Feedback</h2>
      {!coach && pending === null && (
        <p className="hint">click an apex on map or a turn card</p>
      )}
      {pending !== null && (
        <p className="loading">analyzing T{pending}…</p>
      )}
      {coach && !isStale && pending === null && (
        <>
          <div className="turn-tag">T{coach.turn}</div>
          <pre className="advice">{coach.text}</pre>
        </>
      )}
    </div>
  )
}
