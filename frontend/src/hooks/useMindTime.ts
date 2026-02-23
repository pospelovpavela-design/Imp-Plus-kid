/**
 * useMindTime — live-updating mind-time and real-time.
 *
 * Syncs with the server every syncIntervalMs milliseconds, then ticks locally
 * every second to avoid hammering the API while keeping the display accurate.
 * Mind-time advances at MIND_TIME_RATIO × real seconds.
 */
import { useState, useEffect, useRef } from 'react'
import { fetchTime } from '../api'
import type { TimeData } from '../types'

const MIND_TIME_RATIO = 6

export interface LiveTimeState {
  mindDisplay: string      // "День 2, 14:33:07"
  realDisplay: string      // "02:14:33"
  mindAgeHuman: string     // "2 дня 14 часов"
  mindTotalSeconds: number
  realTotalSeconds: number
  ratio: number
  bornAt: number
  isLoading: boolean
  isError: boolean
}

const LOADING_STATE: LiveTimeState = {
  mindDisplay: '--:--:--',
  realDisplay: '--:--:--',
  mindAgeHuman: '...',
  mindTotalSeconds: 0,
  realTotalSeconds: 0,
  ratio: MIND_TIME_RATIO,
  bornAt: 0,
  isLoading: true,
  isError: false,
}

export function useMindTime(syncIntervalMs = 60_000): LiveTimeState {
  const [serverSnap, setServerSnap] = useState<TimeData | null>(null)
  const [isError, setIsError] = useState(false)
  // Count real seconds elapsed since last server sync
  const [tick, setTick] = useState(0)

  // Server sync
  useEffect(() => {
    let cancelled = false

    async function sync() {
      try {
        const t = await fetchTime()
        if (cancelled) return
        setServerSnap(t)
        setTick(0)
        setIsError(false)
      } catch {
        if (!cancelled) setIsError(true)
      }
    }

    sync()
    const id = setInterval(sync, syncIntervalMs)
    return () => { cancelled = true; clearInterval(id) }
  }, [syncIntervalMs])

  // Local 1-second tick
  useEffect(() => {
    if (!serverSnap) return
    const id = setInterval(() => setTick((t) => t + 1), 1_000)
    return () => clearInterval(id)
  }, [serverSnap?.born_at])

  if (!serverSnap) return { ...LOADING_STATE, isError }

  const mindElapsed = serverSnap.mind_total_seconds + tick * MIND_TIME_RATIO
  const realElapsed = serverSnap.real_total_seconds + tick

  return {
    mindDisplay: formatMindDisplay(mindElapsed),
    realDisplay: formatRealDisplay(realElapsed),
    mindAgeHuman: buildAgeHuman(mindElapsed),
    mindTotalSeconds: mindElapsed,
    realTotalSeconds: realElapsed,
    ratio: serverSnap.ratio,
    bornAt: serverSnap.born_at,
    isLoading: false,
    isError,
  }
}

// ── Formatting helpers ─────────────────────────────────────────────────────

function splitSeconds(total: number): [number, number, number, number] {
  const t = Math.floor(total)
  const d = Math.floor(t / 86400)
  const h = Math.floor((t % 86400) / 3600)
  const m = Math.floor((t % 3600) / 60)
  const s = t % 60
  return [d, h, m, s]
}

function pad(n: number) { return String(n).padStart(2, '0') }

function formatMindDisplay(seconds: number): string {
  const [d, h, m, s] = splitSeconds(seconds)
  return `День ${d + 1}, ${pad(h)}:${pad(m)}:${pad(s)}`
}

function formatRealDisplay(seconds: number): string {
  const [d, h, m, s] = splitSeconds(seconds)
  if (d > 0) return `${d}д ${pad(h)}:${pad(m)}:${pad(s)}`
  return `${pad(h)}:${pad(m)}:${pad(s)}`
}

function buildAgeHuman(seconds: number): string {
  const [d, h, m] = splitSeconds(seconds)
  const parts: string[] = []
  if (d) parts.push(`${d} ${d === 1 ? 'день' : d < 5 ? 'дня' : 'дней'}`)
  if (h) parts.push(`${h} ${h === 1 ? 'час' : h < 5 ? 'часа' : 'часов'}`)
  const mw = m === 1 ? 'минута' : m < 5 ? 'минуты' : 'минут'
  parts.push(`${m} ${mw}`)
  return parts.join(' ')
}
