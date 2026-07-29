import { useCallback, useEffect, useState } from 'react'
import { fetchDailyInsights } from '../api'
import { useSSE } from '../hooks/useSSE'
import type { DailyInsight, ThoughtEvent } from '../types'

export default function DailyInsightPanel() {
  const [insights, setInsights] = useState<DailyInsight[]>([])
  const [index, setIndex] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    try {
      const next = await fetchDailyInsights()
      setInsights(next)
      setIndex(0)
      setError('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось загрузить итог')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const onEvent = useCallback((event: ThoughtEvent) => {
    if (event.type === 'daily_insight') void refresh()
  }, [refresh])

  const { connected } = useSSE<ThoughtEvent>('/stream', onEvent)
  const insight = insights[index]

  if (loading) {
    return <div className="py-10 text-center text-xs text-text-dim">Загрузка...</div>
  }

  if (error) {
    return (
      <div className="border-l-2 border-red px-3 py-2 text-xs text-red">
        {error}
      </div>
    )
  }

  if (!insight) {
    return (
      <div className="flex h-full flex-col items-center justify-center text-center">
        <p className="text-sm text-text-dim">Итог дня ещё формируется.</p>
        <span className={`mt-3 h-1.5 w-1.5 rounded-full ${connected ? 'dot-connected' : 'dot-disconnected'}`} />
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border pb-3">
        <button
          type="button"
          title="Предыдущий день"
          aria-label="Предыдущий день"
          disabled={index >= insights.length - 1}
          onClick={() => setIndex((value) => Math.min(insights.length - 1, value + 1))}
          className="h-8 w-8 border border-border text-sm text-text-dim hover:border-accent/50 hover:text-accent disabled:opacity-20"
        >
          ←
        </button>
        <div className="text-center">
          <p className="text-[10px] uppercase tracking-widest text-text-dim">Итог дня</p>
          <time className="mt-1 block font-mono text-xs text-text" dateTime={insight.local_date}>
            {formatDate(insight.local_date)}
          </time>
        </div>
        <button
          type="button"
          title="Следующий день"
          aria-label="Следующий день"
          disabled={index === 0}
          onClick={() => setIndex((value) => Math.max(0, value - 1))}
          className="h-8 w-8 border border-border text-sm text-text-dim hover:border-accent/50 hover:text-accent disabled:opacity-20"
        >
          →
        </button>
      </div>

      <div className="flex flex-1 items-center overflow-y-auto py-6">
        <p className="text-base leading-8 text-text-bright md:text-lg">
          {insight.content}
        </p>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3 font-mono text-[9px] text-text-dim/70">
        <span>
          опора: {insight.source_event_ids.length} событий · {insight.source_cycle_ids.length} циклов
        </span>
        <span>уверенность {insight.confidence.toFixed(2)}</span>
      </div>
    </div>
  )
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: 'Asia/Chita',
  }).format(new Date(`${value}T12:00:00+09:00`))
}
