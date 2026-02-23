import { useEffect, useRef, useState } from 'react'
import { openEventStream } from '../api'
import type { ThoughtEvent } from '../types'

interface Props {
  initial: ThoughtEvent[]
}

const TYPE_CONFIG: Record<ThoughtEvent['type'], { label: string; color: string }> = {
  spontaneous:  { label: 'спонтанное',  color: 'text-text-dim border-dim/40' },
  reaction:     { label: 'реакция',     color: 'text-accent border-accent/30' },
  milestone:    { label: 'рубеж',       color: 'text-gold border-gold/40' },
  contemplation:{ label: 'созерцание',  color: 'text-text-bright border-border-bright/60' },
}

export default function ThoughtFeed({ initial }: Props) {
  const [events, setEvents] = useState<ThoughtEvent[]>(initial)
  const bottomRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)

  // Connect SSE
  useEffect(() => {
    const close = openEventStream((ev) => {
      setEvents((prev) => {
        // Deduplicate by id
        if (prev.some((e) => e.id === ev.id)) return prev
        return [ev, ...prev]
      })
    })
    return close
  }, [])

  // Auto-scroll to top (newest) when new events arrive
  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = 0
    }
  }, [events.length, autoScroll])

  function handleScroll() {
    const el = containerRef.current
    if (!el) return
    setAutoScroll(el.scrollTop < 50)
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-2 shrink-0">
        <h2 className="text-xs tracking-widest uppercase text-text-dim">
          Поток мыслей
        </h2>
        <span className="text-text-dim text-xs">{events.length} записей</span>
      </div>

      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto space-y-2 pr-1"
      >
        {events.length === 0 && (
          <div className="text-text-dim text-xs text-center py-8">
            Разум молчит. Ожидание первой мысли...
          </div>
        )}
        {events.map((ev) => (
          <EventCard key={ev.id} event={ev} />
        ))}
        <div ref={bottomRef} />
      </div>

      {!autoScroll && (
        <button
          onClick={() => { if (containerRef.current) containerRef.current.scrollTop = 0; setAutoScroll(true) }}
          className="shrink-0 mt-1 text-xs text-accent/70 hover:text-accent text-center py-1 border border-accent/20 hover:border-accent/40"
        >
          ↑ К новым мыслям
        </button>
      )}
    </div>
  )
}

function EventCard({ event }: { event: ThoughtEvent }) {
  const [expanded, setExpanded] = useState(false)
  const cfg = TYPE_CONFIG[event.type] || TYPE_CONFIG.spontaneous
  const preview = event.content.slice(0, 140)
  const hasMore = event.content.length > 140

  return (
    <div className={`border-l-2 pl-3 py-1.5 text-xs animate-fade-in ${cfg.color}`}>
      <div className="flex items-center gap-2 mb-1">
        <span className="font-mono text-text-dim/60 text-[10px]">{event.mind_time}</span>
        <span className={`text-[10px] uppercase tracking-widest px-1 border ${cfg.color}`}>
          {cfg.label}
        </span>
        {event.concepts_involved?.length > 0 && (
          <span className="text-text-dim/50 text-[10px]">
            [{event.concepts_involved.join(', ')}]
          </span>
        )}
      </div>
      <div className="text-text leading-relaxed">
        {expanded ? event.content : preview}
        {hasMore && !expanded && '…'}
      </div>
      {hasMore && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-text-dim/50 hover:text-text-dim text-[10px] mt-1"
        >
          {expanded ? '↑ свернуть' : '↓ развернуть'}
        </button>
      )}
    </div>
  )
}
