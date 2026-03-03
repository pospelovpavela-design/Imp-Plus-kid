import { useCallback, useRef, useState } from 'react'
import { useSSE } from '../hooks/useSSE'
import type { ThoughtEvent } from '../types'

interface Props {
  initial: ThoughtEvent[]
  token: string
}

const TYPE_CONFIG: Record<ThoughtEvent['type'], { label: string; colorClass: string }> = {
  spontaneous:   { label: 'спонтанное',  colorClass: 'border-dim/60 text-text-dim' },
  reaction:      { label: 'реакция',     colorClass: 'border-accent/40 text-accent' },
  milestone:     { label: 'рубеж',       colorClass: 'border-gold/50 text-gold' },
  contemplation: { label: 'созерцание',  colorClass: 'border-border-bright/70 text-text' },
  autonomous:    { label: '✦ синтез',    colorClass: 'border-gold text-gold' },
}

export default function ThoughtFeed({ initial, token }: Props) {
  const [events, setEvents] = useState<ThoughtEvent[]>(initial)
  const containerRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)

  const onEvent = useCallback((ev: ThoughtEvent) => {
    if (!ev.id) return
    setEvents((prev) => (prev.some((e) => e.id === ev.id) ? prev : [ev, ...prev]))
    if (autoScroll && containerRef.current) containerRef.current.scrollTop = 0
  }, [autoScroll])

  const { connected, reconnectCount } = useSSE<ThoughtEvent>(
    `/stream?token=${encodeURIComponent(token)}`,
    onEvent,
  )

  function handleScroll() {
    const el = containerRef.current
    if (el) setAutoScroll(el.scrollTop < 60)
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header with connection status */}
      <div className="flex items-center justify-between mb-2 shrink-0">
        <h2 className="text-[10px] tracking-widest uppercase text-text-dim">Поток мыслей</h2>
        <div className="flex items-center gap-2">
          <div className={`w-1.5 h-1.5 rounded-full ${connected ? 'dot-connected' : 'dot-disconnected'}`} />
          <span className="text-[10px] text-text-dim">
            {connected ? 'подключено' : `переподключение${reconnectCount > 0 ? ` (${reconnectCount})` : ''}`}
          </span>
          <span className="text-[10px] text-text-dim/50">{events.length}</span>
        </div>
      </div>

      {/* Events */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto space-y-2 pr-1"
      >
        {events.length === 0 && (
          <div className="text-text-dim/40 text-xs text-center py-10">
            Разум молчит. Ожидание первой мысли...
          </div>
        )}
        {events.map((ev) => <EventCard key={ev.id} event={ev} />)}
      </div>

      {!autoScroll && (
        <button
          onClick={() => { if (containerRef.current) containerRef.current.scrollTop = 0; setAutoScroll(true) }}
          className="shrink-0 mt-1 text-[10px] text-accent/70 hover:text-accent text-center py-1
                     border border-accent/20 hover:border-accent/40 transition-colors"
        >
          ↑ К новым мыслям
        </button>
      )}
    </div>
  )
}

function EventCard({ event }: { event: ThoughtEvent }) {
  const [expanded, setExpanded] = useState(false)
  const cfg = TYPE_CONFIG[event.type] ?? TYPE_CONFIG.spontaneous
  const SHORT = 140
  const hasMore = event.content.length > SHORT

  return (
    <div className={`border-l-2 pl-3 py-1.5 text-xs animate-fade-in ${cfg.colorClass}`}>
      <div className="flex items-center flex-wrap gap-1.5 mb-1">
        <span className="font-mono text-[9px] text-text-dim/50">{event.mind_time}</span>
        <span className={`text-[9px] uppercase tracking-widest px-1 border ${cfg.colorClass}`}>
          {cfg.label}
        </span>
        {event.concepts_involved?.length > 0 && (
          <span className="text-text-dim/40 text-[9px]">
            [{event.concepts_involved.join(', ')}]
          </span>
        )}
      </div>
      <p className="text-text/90 leading-relaxed">
        {expanded ? event.content : event.content.slice(0, SHORT)}
        {hasMore && !expanded && '…'}
      </p>
      {hasMore && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-text-dim/40 hover:text-text-dim text-[10px] mt-0.5"
        >
          {expanded ? '↑ свернуть' : '↓ развернуть'}
        </button>
      )}
    </div>
  )
}
