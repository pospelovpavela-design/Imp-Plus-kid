import { useEffect, useState } from 'react'
import { fetchTime } from '../api'
import type { TimeData } from '../types'

interface Props {
  compact?: boolean
}

export default function MindClock({ compact = false }: Props) {
  const [time, setTime] = useState<TimeData | null>(null)
  const [localSeconds, setLocalSeconds] = useState(0)
  const [error, setError] = useState(false)

  // Fetch once on mount, then tick locally
  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const t = await fetchTime()
        if (!cancelled) {
          setTime(t)
          setLocalSeconds(0)
          setError(false)
        }
      } catch {
        if (!cancelled) setError(true)
      }
    }

    load()
    // Re-sync every 60s to avoid drift
    const syncInterval = setInterval(load, 60_000)
    return () => { cancelled = true; clearInterval(syncInterval) }
  }, [])

  // Local tick every 1 real second → increment mind by ratio
  useEffect(() => {
    if (!time) return
    const interval = setInterval(() => {
      setLocalSeconds((s) => s + 1)
    }, 1000)
    return () => clearInterval(interval)
  }, [time])

  if (error) {
    return <div className="text-red/60 text-xs">Ошибка синхронизации времени</div>
  }
  if (!time) {
    return <div className="text-text-dim text-xs animate-pulse">Синхронизация...</div>
  }

  // Calculate current mind & real seconds from the last server sync
  const mindElapsed = time.mind_total_seconds + localSeconds * time.ratio
  const realElapsed = time.real_total_seconds + localSeconds

  const fmt = (n: number) => String(Math.floor(n)).padStart(2, '0')

  // Mind time breakdown
  const mDays    = Math.floor(mindElapsed / 86400)
  const mRem     = mindElapsed % 86400
  const mHours   = Math.floor(mRem / 3600)
  const mMinutes = Math.floor((mRem % 3600) / 60)
  const mSeconds = Math.floor(mRem % 60)

  // Real time breakdown
  const rDays    = Math.floor(realElapsed / 86400)
  const rRem     = realElapsed % 86400
  const rHours   = Math.floor(rRem / 3600)
  const rMinutes = Math.floor((rRem % 3600) / 60)
  const rSeconds = Math.floor(rRem % 60)

  const mindDisplay = `День ${mDays + 1}, ${fmt(mHours)}:${fmt(mMinutes)}:${fmt(mSeconds)}`
  const realDisplay = rDays > 0
    ? `${rDays}д ${fmt(rHours)}:${fmt(rMinutes)}:${fmt(rSeconds)}`
    : `${fmt(rHours)}:${fmt(rMinutes)}:${fmt(rSeconds)}`

  const ageHuman = buildAgeHuman(mDays, mHours, mMinutes)

  if (compact) {
    return (
      <div className="text-right">
        <div className="text-accent text-sm font-mono glow-accent">{mindDisplay}</div>
        <div className="text-text-dim text-xs">{realDisplay} реал.</div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Main clock */}
      <div className="text-center">
        <div className="text-4xl font-bold font-mono text-accent glow-clock tracking-widest">
          {mindDisplay}
        </div>
        <div className="text-text-dim text-xs mt-1 tracking-widest uppercase">
          Время разума
        </div>
      </div>

      {/* Real time */}
      <div className="flex justify-center gap-6 text-xs text-text-dim">
        <div>
          <span className="text-text-dim/50">Реальное:</span>{' '}
          <span className="text-text font-mono">{realDisplay}</span>
        </div>
        <div>
          <span className="text-text-dim/50">Коэффициент:</span>{' '}
          <span className="text-text font-mono">×{time.ratio}</span>
        </div>
      </div>

      {/* Age */}
      <div className="border border-border bg-panel/50 px-4 py-2 text-center text-xs">
        <span className="text-text-dim">Разум существует: </span>
        <span className="text-text-bright">{ageHuman}</span>
        <span className="text-text-dim"> (разумного времени)</span>
      </div>
    </div>
  )
}

function buildAgeHuman(days: number, hours: number, minutes: number): string {
  const parts: string[] = []
  if (days) {
    const w = days === 1 ? 'день' : days < 5 ? 'дня' : 'дней'
    parts.push(`${days} ${w}`)
  }
  if (hours) {
    const w = hours === 1 ? 'час' : hours < 5 ? 'часа' : 'часов'
    parts.push(`${hours} ${w}`)
  }
  const w = minutes === 1 ? 'минута' : minutes < 5 ? 'минуты' : 'минут'
  parts.push(`${minutes} ${w}`)
  return parts.join(' ')
}
