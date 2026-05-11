import { useEffect, useRef } from 'react'
import type { ReferenceTrack, ReferenceSample, Tactic, Telemetry } from '../types'

type Props = {
  reference: ReferenceTrack | null
  tactics: Tactic[] | null
  telemetry: Telemetry | null
  focusedTurn: number | null
  onTurnClick?: (turn: number) => void
  onClearFocus?: () => void
}

type Transform = {
  tx: (x: number) => number
  ty: (z: number) => number
}

const FOCUS_WINDOW_SAMPLES = 400

export function TrackMap({
  reference,
  tactics,
  telemetry,
  focusedTurn,
  onTurnClick,
  onClearFocus,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const transformRef = useRef<Transform | null>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !reference) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const dpr = window.devicePixelRatio || 1
    const rect = canvas.getBoundingClientRect()
    canvas.width = rect.width * dpr
    canvas.height = rect.height * dpr
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    ctx.scale(dpr, dpr)
    const W = rect.width
    const H = rect.height

    const allSamples = reference.samples
    let drawSamples: ReferenceSample[] = allSamples
    let focusedTactic: Tactic | null = null

    if (focusedTurn != null && tactics) {
      focusedTactic = tactics.find((t) => t.turn === focusedTurn) ?? null
      if (focusedTactic && focusedTactic.apex_ref_idx != null) {
        const apexIdx = focusedTactic.apex_ref_idx
        const lo = Math.max(0, apexIdx - FOCUS_WINDOW_SAMPLES)
        const hi = Math.min(allSamples.length, apexIdx + FOCUS_WINDOW_SAMPLES)
        drawSamples = allSamples.slice(lo, hi)
      }
    }

    let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity
    for (const s of drawSamples) {
      if (s.x < minX) minX = s.x
      if (s.x > maxX) maxX = s.x
      if (s.z < minZ) minZ = s.z
      if (s.z > maxZ) maxZ = s.z
    }
    if (!isFinite(minX)) {
      minX = 0; maxX = 1; minZ = 0; maxZ = 1
    }
    const pad = 30
    const sx = (W - 2 * pad) / Math.max(maxX - minX, 1)
    const sy = (H - 2 * pad) / Math.max(maxZ - minZ, 1)
    const scale = Math.min(sx, sy)
    const ox = pad + ((W - 2 * pad) - scale * (maxX - minX)) / 2
    const oy = pad + ((H - 2 * pad) - scale * (maxZ - minZ)) / 2
    const tx = (x: number) => ox + (x - minX) * scale
    const ty = (z: number) => H - (oy + (z - minZ) * scale)
    transformRef.current = { tx, ty }

    ctx.clearRect(0, 0, W, H)

    const inView = (x: number, z: number) => {
      const px = tx(x)
      const py = ty(z)
      return px >= -10 && px <= W + 10 && py >= -10 && py <= H + 10
    }

    ctx.strokeStyle = '#3a3a3a'
    ctx.lineWidth = focusedTurn != null ? 4 : 2
    ctx.beginPath()
    for (let i = 0; i < drawSamples.length; i++) {
      const px = tx(drawSamples[i].x)
      const py = ty(drawSamples[i].z)
      if (i === 0) ctx.moveTo(px, py)
      else ctx.lineTo(px, py)
    }
    ctx.stroke()

    const baseLw = focusedTurn != null ? 3 : 1.5
    for (let i = 1; i < drawSamples.length; i++) {
      const s = drawSamples[i]
      const t = Math.min(1, s.speed_kph / 280)
      const hue = 210 - 210 * t
      ctx.strokeStyle = `hsl(${hue}, 70%, 55%)`
      ctx.lineWidth = baseLw
      ctx.beginPath()
      ctx.moveTo(tx(drawSamples[i - 1].x), ty(drawSamples[i - 1].z))
      ctx.lineTo(tx(s.x), ty(s.z))
      ctx.stroke()
    }

    if (tactics) {
      const apexR = focusedTurn != null ? 11 : 8
      const fontSize = focusedTurn != null ? 14 : 11
      for (const tac of tactics) {
        if (!inView(tac.apex_x, tac.apex_z)) continue
        const px = tx(tac.apex_x)
        const py = ty(tac.apex_z)
        const isFocused = focusedTactic && tac.turn === focusedTactic.turn
        ctx.fillStyle = isFocused ? '#ff8c00' : '#ffd400'
        ctx.strokeStyle = '#000'
        ctx.lineWidth = isFocused ? 2 : 1
        ctx.beginPath()
        ctx.arc(px, py, isFocused ? apexR + 2 : apexR, 0, 2 * Math.PI)
        ctx.fill()
        ctx.stroke()
        ctx.fillStyle = '#fff'
        ctx.font = `bold ${fontSize}px sans-serif`
        ctx.fillText(`T${tac.turn}`, px + apexR + 2, py - apexR)
      }
    }

    if (telemetry && inView(telemetry.x, telemetry.z)) {
      const px = tx(telemetry.x)
      const py = ty(telemetry.z)
      ctx.fillStyle = '#fff'
      ctx.strokeStyle = '#00d4ff'
      ctx.lineWidth = 2
      ctx.beginPath()
      ctx.arc(px, py, 8, 0, 2 * Math.PI)
      ctx.fill()
      ctx.stroke()
    }
  }, [reference, tactics, telemetry, focusedTurn])

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!tactics || !transformRef.current || !onTurnClick) return
    const rect = e.currentTarget.getBoundingClientRect()
    const px = e.clientX - rect.left
    const py = e.clientY - rect.top
    let bestT: Tactic | null = null
    let bestD = 1e18
    for (const t of tactics) {
      const dx = transformRef.current.tx(t.apex_x) - px
      const dy = transformRef.current.ty(t.apex_z) - py
      const d = Math.hypot(dx, dy)
      if (d < bestD) {
        bestD = d
        bestT = t
      }
    }
    if (bestT && bestD < 24) onTurnClick(bestT.turn)
  }

  return (
    <div className="track-map">
      <canvas
        ref={canvasRef}
        onClick={handleClick}
        style={{ cursor: tactics && tactics.length > 0 ? 'pointer' : 'default' }}
      />
      {focusedTurn != null && (
        <button className="zoom-out" onClick={onClearFocus}>
          ← all turns
        </button>
      )}
      {!reference && (
        <div className="overlay">
          no reference track — run <code>make analyze</code>
        </div>
      )}
    </div>
  )
}
