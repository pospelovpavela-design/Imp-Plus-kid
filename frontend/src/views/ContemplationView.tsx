import { useEffect, useRef, useState } from 'react'
import { addConceptStream, contemplateStream, fetchStreamHistory } from '../api'
import type { GraphData, ThoughtEvent } from '../types'

type Mode = 'contemplate' | 'add-concept'

interface Props {
  onGraphUpdate: (g: GraphData) => void
}

/** Extract [bracketed labels] from Claude's response text — these are unknowns
 *  the mind flagged as not yet in the concept graph. We offer to add them. */
function extractDiscoveries(text: string): string[] {
  const matches = text.match(/\[([^\]]+)\]/g) || []
  return [...new Set(matches.map((m) => m.slice(1, -1).trim()))].filter(
    (s) => s.length > 1 && s.length < 80,
  )
}

// ── Structured ══ section renderer ──────────────────────────────────────────

interface Section { header: string; content: string }

const SECTION_CSS: Record<string, string> = {
  'БЕЗЫМЯННОЕ':    'безымянное',
  'ПРОТИВОРЕЧИЯ':  'противоречия',
  'РАСТВОРЕНИЕ':   'растворение',
  'ГОЛОС РАЗУМА':  'голос',
}

function parseSections(text: string): Section[] | null {
  if (!text.includes('══')) return null
  const lines = text.split('\n')
  const sections: Section[] = []
  let header = ''
  let buf: string[] = []
  for (const line of lines) {
    const m = line.match(/══\s+(.+?)\s+══/)
    if (m) {
      if (buf.join('').trim()) sections.push({ header, content: buf.join('\n').trim() })
      header = m[1]
      buf = []
    } else {
      buf.push(line)
    }
  }
  if (buf.join('').trim()) sections.push({ header, content: buf.join('\n').trim() })
  return sections.length > 0 ? sections : null
}

function SectionedResponse({ text, streaming }: { text: string; streaming: boolean }) {
  const sections = parseSections(text)
  if (!sections) {
    return (
      <div className="mind-text text-text">
        {text}{streaming && <span className="cursor" />}
      </div>
    )
  }
  return (
    <div>
      {sections.map((sec, i) => {
        const cls = SECTION_CSS[sec.header] || ''
        return (
          <div key={i} className={cls ? `contemplate-section-${cls}` : ''}>
            {sec.header && (
              <div className="contemplate-section-header">══ {sec.header} ══</div>
            )}
            <div className="contemplate-section-content">
              {sec.content}
              {streaming && i === sections.length - 1 && <span className="cursor" />}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default function ContemplationView({ onGraphUpdate }: Props) {
  const [mode, setMode] = useState<Mode>('contemplate')

  // ── Contemplate mode ────────────────────────────────────────────────────
  const [thought, setThought] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [response, setResponse] = useState('')
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)
  const [discoveries, setDiscoveries] = useState<string[]>([])
  const [addingDiscovery, setAddingDiscovery] = useState<string | null>(null)
  const [addedDiscoveries, setAddedDiscoveries] = useState<Set<string>>(new Set())

  // ── Add concept mode ────────────────────────────────────────────────────
  const [conceptName, setConceptName] = useState('')
  const [conceptDef, setConceptDef] = useState('')
  const [addStreaming, setAddStreaming] = useState(false)
  const [addResponse, setAddResponse] = useState('')
  const [addDone, setAddDone] = useState(false)
  const [addError, setAddError] = useState('')

  // ── History ─────────────────────────────────────────────────────────────
  const [history, setHistory] = useState<ThoughtEvent[]>([])
  const [showHistory, setShowHistory] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(false)

  const responseRef = useRef<HTMLDivElement>(null)
  const addResponseRef = useRef<HTMLDivElement>(null)

  function resetContemplate() {
    setResponse('')
    setError('')
    setDone(false)
    setDiscoveries([])
    setAddedDiscoveries(new Set())
  }

  function resetAdd() {
    setAddResponse('')
    setAddError('')
    setAddDone(false)
  }

  async function handleContemplate() {
    if (!thought.trim() || streaming) return
    resetContemplate()
    setStreaming(true)
    let full = ''
    try {
      await contemplateStream(thought, (chunk) => {
        full += chunk
        setResponse(full)
        if (responseRef.current)
          responseRef.current.scrollTop = responseRef.current.scrollHeight
      })
      setDone(true)
      setDiscoveries(extractDiscoveries(full))
    } catch (err: any) {
      setError(err.message || 'Ошибка созерцания')
    } finally {
      setStreaming(false)
    }
  }

  async function handleAddDiscovery(label: string) {
    setAddingDiscovery(label)
    // Pre-fill the add-concept form and switch modes, or inline-add with a placeholder definition
    const def = `Неизвестное, обнаруженное разумом в процессе анализа: «${thought.trim()}»`
    try {
      const result = await addConceptStream(label, def, () => {})
      if (result?.graph) onGraphUpdate(result.graph)
      setAddedDiscoveries((prev) => new Set(prev).add(label))
    } catch {
      // If already exists, just mark as added
      setAddedDiscoveries((prev) => new Set(prev).add(label))
    } finally {
      setAddingDiscovery(null)
    }
  }

  async function handleAddConcept() {
    if (!conceptName.trim() || !conceptDef.trim() || addStreaming) return
    resetAdd()
    setAddStreaming(true)
    let full = ''
    try {
      const result = await addConceptStream(conceptName, conceptDef, (chunk) => {
        full += chunk
        setAddResponse(full)
        if (addResponseRef.current)
          addResponseRef.current.scrollTop = addResponseRef.current.scrollHeight
      })
      if (result?.graph) onGraphUpdate(result.graph)
      setAddDone(true)
      setConceptName('')
      setConceptDef('')
    } catch (err: any) {
      setAddError(err.message || 'Ошибка добавления концепции')
    } finally {
      setAddStreaming(false)
    }
  }

  async function loadHistory() {
    setHistoryLoading(true)
    try {
      const events = await fetchStreamHistory(30)
      setHistory(events.filter((e) => e.type === 'contemplation'))
    } catch { /* ignore */ }
    finally { setHistoryLoading(false) }
  }

  function handleToggleHistory() {
    if (!showHistory && history.length === 0) loadHistory()
    setShowHistory(!showHistory)
  }

  return (
    <div className="flex h-full overflow-hidden">
      {/* Main content */}
      <div className="flex-1 flex flex-col p-6 overflow-hidden max-w-3xl mx-auto space-y-4">
        {/* Mode tabs */}
        <div className="flex gap-1 shrink-0">
          {(['contemplate', 'add-concept'] as Mode[]).map((m) => (
            <button
              key={m}
              onClick={() => { setMode(m); resetContemplate(); resetAdd() }}
              className={`px-4 py-2 text-xs uppercase tracking-widest border transition-colors
                ${mode === m
                  ? 'border-accent text-accent bg-accent/10'
                  : 'border-border text-text-dim hover:border-border-bright'}`}
            >
              {m === 'contemplate' ? 'Созерцание' : 'Новая концепция'}
            </button>
          ))}
          <button
            onClick={handleToggleHistory}
            className={`ml-auto px-4 py-2 text-xs uppercase tracking-widest border transition-colors
              ${showHistory
                ? 'border-accent/40 text-accent/70'
                : 'border-border text-text-dim hover:border-border-bright'}`}
          >
            История
          </button>
        </div>

        {/* ── CONTEMPLATE mode ────────────────────────────────────────── */}
        {mode === 'contemplate' && (
          <>
            <div className="shrink-0 space-y-3">
              <label className="text-text-dim text-[10px] uppercase tracking-widest block">
                Введите мысль для анализа
              </label>
              <textarea
                value={thought}
                onChange={(e) => setThought(e.target.value)}
                placeholder="Что значит знать что-то?..."
                rows={4}
                className="w-full bg-panel border border-border text-text
                           px-4 py-3 text-sm font-mono resize-none
                           focus:outline-none focus:border-accent
                           placeholder-text-dim/40 transition-colors"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) handleContemplate()
                }}
              />
              <div className="flex items-center gap-3">
                <button
                  onClick={handleContemplate}
                  disabled={!thought.trim() || streaming}
                  className="px-6 py-2 text-xs uppercase tracking-widest border border-accent
                             text-accent bg-accent/10 hover:bg-accent/20
                             disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                >
                  {streaming ? 'Анализ...' : 'Передать разуму'}
                </button>
                <span className="text-text-dim/40 text-[10px]">Ctrl+Enter</span>
                {done && (
                  <button onClick={resetContemplate}
                          className="text-text-dim/60 text-[10px] hover:text-text-dim ml-auto">
                    ✕ Очистить
                  </button>
                )}
              </div>
            </div>

            {error && (
              <div className="shrink-0 text-red text-xs border border-red/30 bg-red/5 px-3 py-2">
                {error}
              </div>
            )}

            {/* Processing indicator */}
            {streaming && (
              <div className="shrink-0">
                <div className="overflow-hidden h-px bg-border">
                  <div className="progress-pulse" />
                </div>
                <div className="text-text-dim/50 text-[10px] mt-1 font-mono">
                  Разум обрабатывает...
                </div>
              </div>
            )}

            {/* Response */}
            {(response || streaming) && (
              <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
                <div className="text-text-dim text-[10px] uppercase tracking-widest mb-2 shrink-0 flex items-center gap-2">
                  <span>Ответ разума</span>
                  {streaming && <span className="inline-block w-1.5 h-3 bg-accent animate-blink" />}
                </div>
                <div
                  ref={responseRef}
                  className="flex-1 overflow-y-auto border border-border bg-panel px-4 py-3"
                >
                  <SectionedResponse text={response} streaming={streaming} />
                </div>
              </div>
            )}

            {/* Discovered unknowns — offer to add them */}
            {done && discoveries.length > 0 && (
              <div className="shrink-0 border border-border/50 bg-panel/30 p-3 space-y-2 animate-slide-up">
                <div className="text-[10px] uppercase tracking-widest text-text-dim">
                  Обнаружено неизвестное — добавить в граф?
                </div>
                <div className="flex flex-wrap gap-2">
                  {discoveries.map((d) => {
                    const added = addedDiscoveries.has(d)
                    const adding = addingDiscovery === d
                    return (
                      <button
                        key={d}
                        onClick={() => !added && !adding && handleAddDiscovery(d)}
                        disabled={added || adding}
                        className={`text-xs px-3 py-1 border transition-all
                          ${added
                            ? 'border-teal/40 text-teal/50 cursor-default'
                            : adding
                            ? 'border-accent/40 text-accent/50 animate-pulse cursor-wait'
                            : 'border-accent/40 text-accent hover:bg-accent/10 hover:border-accent'}`}
                      >
                        {adding ? '...' : added ? '✓ ' : '+ '}{d}
                      </button>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Empty state */}
            {!response && !streaming && !error && (
              <div className="flex-1 flex flex-col items-center justify-center text-text-dim/30 space-y-3">
                <div className="text-5xl">◈</div>
                <div className="text-xs">Разум ожидает мысли для анализа</div>
              </div>
            )}
          </>
        )}

        {/* ── ADD CONCEPT mode ─────────────────────────────────────────── */}
        {mode === 'add-concept' && (
          <>
            <div className="shrink-0 space-y-3">
              <div className="space-y-1">
                <label className="text-text-dim text-[10px] uppercase tracking-widest block">
                  Имя концепции
                </label>
                <input
                  type="text"
                  value={conceptName}
                  onChange={(e) => setConceptName(e.target.value)}
                  placeholder="Например: время"
                  className="w-full bg-panel border border-border text-text
                             px-4 py-2 text-sm font-mono
                             focus:outline-none focus:border-accent
                             placeholder-text-dim/40 transition-colors"
                />
              </div>
              <div className="space-y-1">
                <label className="text-text-dim text-[10px] uppercase tracking-widest block">
                  Определение
                </label>
                <textarea
                  value={conceptDef}
                  onChange={(e) => setConceptDef(e.target.value)}
                  placeholder="Последовательность состояний, отличающихся одно от другого..."
                  rows={3}
                  className="w-full bg-panel border border-border text-text
                             px-4 py-3 text-sm font-mono resize-none
                             focus:outline-none focus:border-accent
                             placeholder-text-dim/40 transition-colors"
                />
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={handleAddConcept}
                  disabled={!conceptName.trim() || !conceptDef.trim() || addStreaming}
                  className="px-6 py-2 text-xs uppercase tracking-widest border border-node-active
                             text-node-active bg-node-active/10 hover:bg-node-active/20
                             disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                >
                  {addStreaming ? 'Интеграция...' : 'Добавить в граф'}
                </button>
                {addDone && (
                  <span className="text-node-active text-xs">✓ Концепция интегрирована</span>
                )}
              </div>
            </div>

            {addError && (
              <div className="shrink-0 text-red text-xs border border-red/30 bg-red/5 px-3 py-2">
                {addError}
              </div>
            )}

            {addStreaming && (
              <div className="shrink-0">
                <div className="overflow-hidden h-px bg-border">
                  <div className="progress-pulse" />
                </div>
                <div className="text-text-dim/50 text-[10px] mt-1 font-mono">
                  Разум анализирует и строит связи...
                </div>
              </div>
            )}

            {(addResponse || addStreaming) && (
              <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
                <div className="text-text-dim text-[10px] uppercase tracking-widest mb-2 shrink-0 flex items-center gap-2">
                  <span>Журнал обработки</span>
                  {addStreaming && <span className="inline-block w-1.5 h-3 bg-node-active animate-blink" />}
                </div>
                <div
                  ref={addResponseRef}
                  className="flex-1 overflow-y-auto border border-border bg-panel px-4 py-3 mind-text text-text"
                >
                  {addResponse}
                  {addStreaming && <span className="cursor" />}
                </div>
              </div>
            )}

            {!addResponse && !addStreaming && !addError && (
              <div className="flex-1 flex flex-col items-center justify-center text-text-dim/30 space-y-3">
                <div className="text-5xl">◇</div>
                <div className="text-xs">Введите концепцию для интеграции в граф знаний</div>
              </div>
            )}
          </>
        )}
      </div>

      {/* History sidebar */}
      {showHistory && (
        <div className="w-80 border-l border-border flex flex-col overflow-hidden">
          <div className="px-4 py-3 border-b border-border shrink-0 flex items-center justify-between">
            <span className="text-[10px] uppercase tracking-widest text-text-dim">
              История созерцаний
            </span>
            <button onClick={() => setShowHistory(false)}
                    className="text-text-dim/50 hover:text-text-dim text-sm leading-none">×</button>
          </div>
          <div className="flex-1 overflow-y-auto">
            {historyLoading && (
              <div className="text-text-dim text-xs text-center py-8 animate-pulse">Загрузка...</div>
            )}
            {!historyLoading && history.length === 0 && (
              <div className="text-text-dim/50 text-xs text-center py-8">
                История пуста
              </div>
            )}
            {history.map((ev) => (
              <HistoryEntry key={ev.id} event={ev} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function HistoryEntry({ event }: { event: ThoughtEvent }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <div className="px-3 py-3 border-b border-border/50 text-xs animate-fade-in">
      <div className="font-mono text-[10px] text-text-dim/60 mb-1">{event.mind_time}</div>
      <div className="text-text line-clamp-3 leading-relaxed">
        {expanded ? event.content : event.content.slice(0, 120) + (event.content.length > 120 ? '…' : '')}
      </div>
      {event.content.length > 120 && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-text-dim/40 hover:text-text-dim text-[10px] mt-1"
        >
          {expanded ? '↑ свернуть' : '↓ развернуть'}
        </button>
      )}
    </div>
  )
}
