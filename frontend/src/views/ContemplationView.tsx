import { useRef, useState } from 'react'
import { addConceptStream, contemplateStream } from '../api'
import type { GraphData } from '../types'

type Mode = 'contemplate' | 'add-concept'

interface Props {
  onGraphUpdate: (g: GraphData) => void
}

export default function ContemplationView({ onGraphUpdate }: Props) {
  const [mode, setMode] = useState<Mode>('contemplate')
  const [thought, setThought] = useState('')
  const [conceptName, setConceptName] = useState('')
  const [conceptDef, setConceptDef] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [response, setResponse] = useState('')
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)
  const responseRef = useRef<HTMLDivElement>(null)

  function reset() {
    setResponse('')
    setError('')
    setDone(false)
  }

  async function handleContemplate() {
    if (!thought.trim() || streaming) return
    reset()
    setStreaming(true)
    try {
      await contemplateStream(thought, (chunk) => {
        setResponse((r) => r + chunk)
        if (responseRef.current) {
          responseRef.current.scrollTop = responseRef.current.scrollHeight
        }
      })
      setDone(true)
    } catch (err: any) {
      setError(err.message || 'Ошибка созерцания')
    } finally {
      setStreaming(false)
    }
  }

  async function handleAddConcept() {
    if (!conceptName.trim() || !conceptDef.trim() || streaming) return
    reset()
    setStreaming(true)
    try {
      const result = await addConceptStream(conceptName, conceptDef, (chunk) => {
        setResponse((r) => r + chunk)
        if (responseRef.current) {
          responseRef.current.scrollTop = responseRef.current.scrollHeight
        }
      })
      if (result?.graph) {
        onGraphUpdate(result.graph)
      }
      setDone(true)
      setConceptName('')
      setConceptDef('')
    } catch (err: any) {
      setError(err.message || 'Ошибка добавления концепции')
    } finally {
      setStreaming(false)
    }
  }

  return (
    <div className="flex flex-col h-full p-6 max-w-3xl mx-auto space-y-4 overflow-hidden">
      {/* Mode tabs */}
      <div className="flex gap-1 shrink-0">
        {(['contemplate', 'add-concept'] as Mode[]).map((m) => (
          <button
            key={m}
            onClick={() => { setMode(m); reset() }}
            className={`px-4 py-2 text-xs uppercase tracking-widest border transition-colors
              ${mode === m
                ? 'border-accent text-accent bg-accent/10'
                : 'border-border text-text-dim hover:border-dim'}`}
          >
            {m === 'contemplate' ? 'Созерцание' : 'Новая концепция'}
          </button>
        ))}
      </div>

      {/* Input area */}
      <div className="shrink-0 space-y-3">
        {mode === 'contemplate' && (
          <>
            <label className="text-text-dim text-[10px] uppercase tracking-widest block">
              Введите мысль для анализа
            </label>
            <textarea
              value={thought}
              onChange={(e) => setThought(e.target.value)}
              placeholder="Что значит знать что-то?..."
              rows={4}
              className="w-full bg-panel border border-border text-text-bright
                         px-4 py-3 text-sm font-mono resize-none
                         focus:outline-none focus:border-accent
                         placeholder-text-dim/40"
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
                <button onClick={reset} className="text-text-dim/60 text-[10px] hover:text-text-dim">
                  ✕ Очистить
                </button>
              )}
            </div>
          </>
        )}

        {mode === 'add-concept' && (
          <>
            <div className="space-y-2">
              <label className="text-text-dim text-[10px] uppercase tracking-widest block">
                Имя концепции
              </label>
              <input
                type="text"
                value={conceptName}
                onChange={(e) => setConceptName(e.target.value)}
                placeholder="Например: время"
                className="w-full bg-panel border border-border text-text-bright
                           px-4 py-2 text-sm font-mono
                           focus:outline-none focus:border-accent placeholder-text-dim/40"
              />
            </div>
            <div className="space-y-2">
              <label className="text-text-dim text-[10px] uppercase tracking-widest block">
                Определение
              </label>
              <textarea
                value={conceptDef}
                onChange={(e) => setConceptDef(e.target.value)}
                placeholder="Последовательность состояний, отличающихся одно от другого..."
                rows={3}
                className="w-full bg-panel border border-border text-text-bright
                           px-4 py-3 text-sm font-mono resize-none
                           focus:outline-none focus:border-accent placeholder-text-dim/40"
              />
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={handleAddConcept}
                disabled={!conceptName.trim() || !conceptDef.trim() || streaming}
                className="px-6 py-2 text-xs uppercase tracking-widest border border-teal
                           text-teal bg-teal/10 hover:bg-teal/20
                           disabled:opacity-30 disabled:cursor-not-allowed transition-all"
              >
                {streaming ? 'Обработка...' : 'Добавить в граф'}
              </button>
              {done && (
                <span className="text-teal text-xs">✓ Концепция добавлена</span>
              )}
            </div>
          </>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="shrink-0 text-red text-xs border border-red/30 bg-red/5 px-3 py-2">
          {error}
        </div>
      )}

      {/* Streaming response */}
      {(response || streaming) && (
        <div className="flex-1 overflow-hidden flex flex-col min-h-0">
          <div className="text-text-dim text-[10px] uppercase tracking-widest mb-2 shrink-0 flex items-center gap-2">
            <span>Ответ разума</span>
            {streaming && (
              <span className="inline-block w-1.5 h-3 bg-accent animate-blink" />
            )}
          </div>
          <div
            ref={responseRef}
            className="flex-1 overflow-y-auto border border-border bg-panel/30 p-4
                       text-text text-sm leading-relaxed font-mono whitespace-pre-wrap mind-text"
          >
            {response}
            {streaming && <span className="cursor" />}
          </div>
        </div>
      )}

      {/* Empty state */}
      {!response && !streaming && !error && (
        <div className="flex-1 flex flex-col items-center justify-center text-text-dim/40 text-xs space-y-2">
          <div className="text-4xl">◈</div>
          <div>
            {mode === 'contemplate'
              ? 'Разум ожидает мысли для анализа'
              : 'Введите концепцию для интеграции в граф знаний'}
          </div>
        </div>
      )}
    </div>
  )
}
