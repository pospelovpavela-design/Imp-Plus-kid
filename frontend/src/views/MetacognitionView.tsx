import { useEffect, useState } from 'react'
import {
  addExternalObservation,
  fetchCognitiveBeliefs,
  fetchCognitiveInquiries,
  fetchCognitiveMetrics,
  fetchCognitivePredictions,
  fetchExternalObservations,
  fetchSelfModel,
  resolvePrediction,
} from '../api'
import type {
  CognitiveBelief,
  CognitiveInquiry,
  CognitiveMetrics,
  CognitivePrediction,
  ExternalObservation,
  SelfModelEntry,
} from '../types'

type View = 'inquiries' | 'beliefs' | 'predictions' | 'self'

const EMPTY_METRICS: CognitiveMetrics = {
  concepts: 0,
  active_edges: 0,
  archived_edges: 0,
  active_graph_density: 0,
  grounded_concepts: 0,
  grounding_coverage: 0,
  defined_concepts: 0,
  definition_coverage: 0,
  open_inquiries: 0,
  pending_predictions: 0,
  daily_insights: 0,
  unsent_daily_insights: 0,
  latest_daily_insight_date: null,
  active_self_loops: 0,
  active_fallback_edges: 0,
  cognitive_cycles: 0,
  accepted_cycle_rate: null,
  resolved_predictions: 0,
  prediction_brier_score: null,
}

export default function MetacognitionView() {
  const [view, setView] = useState<View>('inquiries')
  const [metrics, setMetrics] = useState<CognitiveMetrics>(EMPTY_METRICS)
  const [inquiries, setInquiries] = useState<CognitiveInquiry[]>([])
  const [beliefs, setBeliefs] = useState<CognitiveBelief[]>([])
  const [predictions, setPredictions] = useState<CognitivePrediction[]>([])
  const [selfModel, setSelfModel] = useState<SelfModelEntry[]>([])
  const [observations, setObservations] = useState<ExternalObservation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function refresh() {
    setError('')
    try {
      const [nextMetrics, nextInquiries, nextBeliefs, nextPredictions, nextSelf, nextObservations] =
        await Promise.all([
          fetchCognitiveMetrics(),
          fetchCognitiveInquiries(),
          fetchCognitiveBeliefs(),
          fetchCognitivePredictions(),
          fetchSelfModel(),
          fetchExternalObservations(),
        ])
      setMetrics(nextMetrics)
      setInquiries(nextInquiries)
      setBeliefs(nextBeliefs)
      setPredictions(nextPredictions)
      setSelfModel(nextSelf)
      setObservations(nextObservations)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось загрузить данные')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto w-full max-w-7xl px-4 py-4 md:px-6 md:py-6">
        <div className="flex items-end justify-between border-b border-border pb-3">
          <div>
            <p className="text-[10px] uppercase tracking-widest text-text-dim">Контур проверки</p>
            <h1 className="mt-1 text-lg font-medium text-text-bright">Метакогниция</h1>
          </div>
          <button
            type="button"
            onClick={() => void refresh()}
            className="border border-border px-3 py-1.5 text-[10px] uppercase tracking-widest text-text-dim hover:border-accent/50 hover:text-accent"
          >
            Обновить
          </button>
        </div>

        <MetricBand metrics={metrics} />

        {error && (
          <div className="mt-4 border-l-2 border-red px-3 py-2 text-xs text-red">{error}</div>
        )}

        <ObservationForm onSaved={refresh} />

        <div className="mt-6 flex overflow-x-auto border-b border-border">
          {([
            ['inquiries', `Вопросы ${metrics.open_inquiries}`],
            ['beliefs', `Убеждения ${beliefs.length}`],
            ['predictions', `Прогнозы ${metrics.pending_predictions}`],
            ['self', `Самомодель ${selfModel.length}`],
          ] as [View, string][]).map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => setView(id)}
              className={`shrink-0 border-b-2 px-3 py-2 text-[10px] uppercase tracking-widest ${
                view === id
                  ? 'border-accent text-accent'
                  : 'border-transparent text-text-dim hover:text-text'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="py-3">
          {loading && <p className="py-8 text-center text-xs text-text-dim">Загрузка...</p>}
          {!loading && view === 'inquiries' && <InquiryList items={inquiries} />}
          {!loading && view === 'beliefs' && <BeliefList items={beliefs} />}
          {!loading && view === 'predictions' && (
            <PredictionList items={predictions} onResolved={refresh} />
          )}
          {!loading && view === 'self' && (
            <SelfModelList items={selfModel} observations={observations} />
          )}
        </div>
      </div>
    </div>
  )
}

function MetricBand({ metrics }: { metrics: CognitiveMetrics }) {
  const items = [
    ['Активные связи', String(metrics.active_edges)],
    ['Архив связей', String(metrics.archived_edges)],
    ['Покрытие опытом', percent(metrics.grounding_coverage)],
    ['Принято циклов', nullablePercent(metrics.accepted_cycle_rate)],
    ['Brier', metrics.prediction_brier_score?.toFixed(3) ?? 'нет данных'],
    ['Инварианты', metrics.active_self_loops + metrics.active_fallback_edges === 0 ? 'чисто' : 'нарушены'],
  ]
  return (
    <div className="mt-4 grid grid-cols-2 border-l border-t border-border sm:grid-cols-3 lg:grid-cols-6">
      {items.map(([label, value]) => (
        <div key={label} className="min-w-0 border-b border-r border-border px-3 py-3">
          <div className="truncate text-[9px] uppercase tracking-widest text-text-dim">{label}</div>
          <div className="mt-1 truncate font-mono text-sm text-text-bright">{value}</div>
        </div>
      ))}
    </div>
  )
}

function ObservationForm({ onSaved }: { onSaved: () => Promise<void> }) {
  const [content, setContent] = useState('')
  const [source, setSource] = useState('')
  const [concepts, setConcepts] = useState('')
  const [reliability, setReliability] = useState(0.8)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      await addExternalObservation({
        content,
        source,
        concept_names: concepts.split(',').map((name) => name.trim()).filter(Boolean),
        reliability,
      })
      setContent('')
      setSource('')
      setConcepts('')
      await onSaved()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось сохранить наблюдение')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={submit} className="mt-6 border-y border-border py-4">
      <div className="grid gap-3 lg:grid-cols-[1fr_220px]">
        <label className="block">
          <span className="text-[10px] uppercase tracking-widest text-text-dim">Внешнее наблюдение</span>
          <textarea
            value={content}
            onChange={(event) => setContent(event.target.value)}
            required
            rows={3}
            className="mt-2 w-full resize-y border border-border bg-deep px-3 py-2 text-sm text-text outline-none focus:border-accent/60"
          />
        </label>
        <div className="grid gap-3">
          <label className="block">
            <span className="text-[10px] uppercase tracking-widest text-text-dim">Источник</span>
            <input
              value={source}
              onChange={(event) => setSource(event.target.value)}
              required
              className="mt-2 w-full border border-border bg-deep px-3 py-2 text-sm text-text outline-none focus:border-accent/60"
            />
          </label>
          <label className="block">
            <span className="text-[10px] uppercase tracking-widest text-text-dim">Концепции через запятую</span>
            <input
              value={concepts}
              onChange={(event) => setConcepts(event.target.value)}
              className="mt-2 w-full border border-border bg-deep px-3 py-2 text-sm text-text outline-none focus:border-accent/60"
            />
          </label>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-4">
        <label className="flex min-w-[240px] flex-1 items-center gap-3 text-xs text-text-dim">
          Надёжность
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={reliability}
            onChange={(event) => setReliability(Number(event.target.value))}
            className="min-w-0 flex-1 accent-accent"
          />
          <span className="w-10 text-right font-mono text-text">{reliability.toFixed(2)}</span>
        </label>
        <button
          type="submit"
          disabled={saving}
          className="border border-accent/50 px-4 py-2 text-[10px] uppercase tracking-widest text-accent hover:bg-accent/10 disabled:opacity-40"
        >
          {saving ? 'Сохранение...' : 'Зафиксировать'}
        </button>
      </div>
      {error && <p className="mt-2 text-xs text-red">{error}</p>}
    </form>
  )
}

function InquiryList({ items }: { items: CognitiveInquiry[] }) {
  if (!items.length) return <Empty text="Вопросов пока нет" />
  return (
    <div className="divide-y divide-border">
      {items.map((item) => (
        <div key={item.id} className="grid gap-2 py-3 md:grid-cols-[90px_1fr_120px]">
          <Status value={item.status} />
          <div className="min-w-0">
            <p className="text-sm leading-relaxed text-text">{item.question}</p>
            <Meta concepts={item.concept_names} text={`${item.origin} · попыток ${item.attempts}`} />
          </div>
          <div className="font-mono text-xs text-text-dim md:text-right">
            приоритет {item.priority.toFixed(2)}
          </div>
        </div>
      ))}
    </div>
  )
}

function BeliefList({ items }: { items: CognitiveBelief[] }) {
  if (!items.length) return <Empty text="Консолидация ещё не сформировала убеждений" />
  return (
    <div className="divide-y divide-border">
      {items.map((item) => (
        <div key={item.id} className="grid gap-2 py-3 md:grid-cols-[1fr_150px]">
          <div className="min-w-0">
            <p className="text-sm leading-relaxed text-text">{item.statement}</p>
            <Meta
              concepts={item.concept_names}
              text={`свидетельства: ${item.evidence_event_ids.join(', ') || 'нет'}`}
            />
          </div>
          <div className="font-mono text-xs text-text-dim md:text-right">
            уверенность {item.confidence.toFixed(2)}
          </div>
        </div>
      ))}
    </div>
  )
}

function PredictionList({
  items,
  onResolved,
}: {
  items: CognitivePrediction[]
  onResolved: () => Promise<void>
}) {
  if (!items.length) return <Empty text="Проверяемых прогнозов пока нет" />
  return (
    <div className="divide-y divide-border">
      {items.map((item) => (
        <PredictionRow key={item.id} item={item} onResolved={onResolved} />
      ))}
    </div>
  )
}

function PredictionRow({
  item,
  onResolved,
}: {
  item: CognitivePrediction
  onResolved: () => Promise<void>
}) {
  const [outcome, setOutcome] =
    useState<'confirmed' | 'disconfirmed' | 'inconclusive'>('confirmed')
  const [evidence, setEvidence] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      await resolvePrediction(item.id, outcome, evidence)
      await onResolved()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось закрыть прогноз')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="py-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-sm leading-relaxed text-text">{item.statement}</p>
          <p className="mt-1 text-xs leading-relaxed text-text-dim">Проверка: {item.test_method}</p>
          <Meta concepts={item.concept_names} text={`прогноз #${item.id}`} />
        </div>
        <span className="font-mono text-xs text-text-dim">{item.confidence.toFixed(2)}</span>
      </div>
      {item.status === 'pending' ? (
        <form onSubmit={submit} className="mt-3 grid gap-2 md:grid-cols-[170px_1fr_auto]">
          <select
            value={outcome}
            onChange={(event) => setOutcome(event.target.value as typeof outcome)}
            className="border border-border bg-deep px-2 py-2 text-xs text-text outline-none focus:border-accent/60"
          >
            <option value="confirmed">Подтверждён</option>
            <option value="disconfirmed">Опровергнут</option>
            <option value="inconclusive">Недостаточно данных</option>
          </select>
          <input
            value={evidence}
            onChange={(event) => setEvidence(event.target.value)}
            required
            placeholder="Свидетельство исхода"
            className="min-w-0 border border-border bg-deep px-3 py-2 text-xs text-text outline-none placeholder:text-text-dim/40 focus:border-accent/60"
          />
          <button
            type="submit"
            disabled={saving}
            className="border border-accent/50 px-3 py-2 text-[10px] uppercase tracking-widest text-accent hover:bg-accent/10 disabled:opacity-40"
          >
            Закрыть
          </button>
          {error && <p className="text-xs text-red md:col-span-3">{error}</p>}
        </form>
      ) : (
        <p className="mt-2 text-xs text-text-dim">
          {item.outcome}: {item.evidence}
        </p>
      )}
    </div>
  )
}

function SelfModelList({
  items,
  observations,
}: {
  items: SelfModelEntry[]
  observations: ExternalObservation[]
}) {
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section>
        <h2 className="pb-2 text-[10px] uppercase tracking-widest text-text-dim">Ограничения системы</h2>
        <div className="divide-y divide-border border-t border-border">
          {items.map((item) => (
            <div key={item.key} className="py-3">
              <p className="font-mono text-[10px] text-accent">{item.key}</p>
              <p className="mt-1 text-sm leading-relaxed text-text">{item.value}</p>
              <p className="mt-1 text-[10px] text-text-dim">{item.evidence}</p>
            </div>
          ))}
        </div>
      </section>
      <section>
        <h2 className="pb-2 text-[10px] uppercase tracking-widest text-text-dim">Последние наблюдения</h2>
        <div className="divide-y divide-border border-t border-border">
          {observations.map((item) => (
            <div key={item.id} className="py-3">
              <p className="text-sm leading-relaxed text-text">{item.content}</p>
              <Meta concepts={item.concept_names} text={`${item.source} · ${item.reliability.toFixed(2)}`} />
            </div>
          ))}
          {!observations.length && <Empty text="Наблюдений пока нет" />}
        </div>
      </section>
    </div>
  )
}

function Meta({ concepts, text }: { concepts: string[]; text: string }) {
  return (
    <p className="mt-1 break-words font-mono text-[10px] text-text-dim/70">
      {concepts.length ? `[${concepts.join(', ')}] · ` : ''}{text}
    </p>
  )
}

function Status({ value }: { value: string }) {
  const style =
    value === 'resolved'
      ? 'border-teal/50 text-teal'
      : value === 'blocked'
        ? 'border-red/50 text-red'
        : 'border-accent/50 text-accent'
  return (
    <span className={`h-fit w-fit border px-2 py-1 text-[9px] uppercase tracking-widest ${style}`}>
      {value}
    </span>
  )
}

function Empty({ text }: { text: string }) {
  return <p className="py-8 text-center text-xs text-text-dim">{text}</p>
}

function percent(value: number) {
  return `${Math.round(value * 100)}%`
}

function nullablePercent(value: number | null) {
  return value === null ? 'нет данных' : percent(value)
}
