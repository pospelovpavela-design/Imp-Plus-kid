import { useEffect, useState } from 'react'
import { fetchConcepts } from '../api'
import type { Concept } from '../types'

export default function LibraryView() {
  const [concepts, setConcepts] = useState<Concept[]>([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<Concept | null>(null)
  const [sortBy, setSortBy] = useState<'time' | 'connections'>('time')

  useEffect(() => {
    fetchConcepts()
      .then(setConcepts)
      .finally(() => setLoading(false))
  }, [])

  const filtered = concepts
    .filter((c) =>
      c.name.toLowerCase().includes(query.toLowerCase()) ||
      c.definition.toLowerCase().includes(query.toLowerCase()),
    )
    .sort((a, b) =>
      sortBy === 'time'
        ? a.real_time_added - b.real_time_added
        : b.connection_count - a.connection_count,
    )

  return (
    <div className="flex h-full overflow-hidden">
      {/* Concept list */}
      <div className="w-96 flex flex-col border-r border-border overflow-hidden">
        {/* Toolbar */}
        <div className="p-3 border-b border-border space-y-2 shrink-0">
          <input
            type="text"
            placeholder="Поиск концепций..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full bg-void border border-border text-text-bright
                       px-3 py-1.5 text-xs focus:outline-none focus:border-accent"
          />
          <div className="flex gap-2 text-[10px]">
            <button
              onClick={() => setSortBy('time')}
              className={`px-2 py-0.5 border transition-colors ${
                sortBy === 'time'
                  ? 'border-accent text-accent'
                  : 'border-border text-text-dim hover:border-dim'
              }`}
            >
              По времени
            </button>
            <button
              onClick={() => setSortBy('connections')}
              className={`px-2 py-0.5 border transition-colors ${
                sortBy === 'connections'
                  ? 'border-accent text-accent'
                  : 'border-border text-text-dim hover:border-dim'
              }`}
            >
              По связям
            </button>
            <span className="ml-auto text-text-dim self-center">{filtered.length} конц.</span>
          </div>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto">
          {loading && (
            <div className="text-text-dim text-xs text-center py-8 animate-pulse">
              Загрузка библиотеки...
            </div>
          )}
          {!loading && filtered.length === 0 && (
            <div className="text-text-dim text-xs text-center py-8">
              Ничего не найдено
            </div>
          )}
          {filtered.map((c) => (
            <ConceptCard
              key={c.id}
              concept={c}
              isSelected={selected?.id === c.id}
              onClick={() => setSelected(c)}
            />
          ))}
        </div>
      </div>

      {/* Detail panel */}
      <div className="flex-1 overflow-y-auto p-6">
        {!selected && (
          <div className="h-full flex items-center justify-center text-text-dim text-xs">
            Выберите концепцию для просмотра
          </div>
        )}
        {selected && <ConceptDetail concept={selected} />}
      </div>
    </div>
  )
}

function ConceptCard({
  concept,
  isSelected,
  onClick,
}: {
  concept: Concept
  isSelected: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-3 py-2.5 border-b border-border/50
                  hover:bg-panel transition-colors text-xs
                  ${isSelected ? 'bg-panel border-l-2 border-l-accent' : 'border-l-2 border-l-transparent'}`}
    >
      <div className="flex items-center justify-between">
        <span className={`font-medium ${concept.is_seed ? 'text-seed-color' : 'text-text-bright'}`}>
          {concept.name}
        </span>
        {concept.custom_label && (
          <span className="text-accent/60 text-[10px]">[{concept.custom_label}]</span>
        )}
      </div>
      <div className="flex gap-3 mt-0.5 text-[10px] text-text-dim">
        <span>{concept.mind_time_added}</span>
        <span>{concept.connection_count} связей</span>
        {concept.is_seed && <span className="text-seed-color/60">seed</span>}
      </div>
    </button>
  )
}

function ConceptDetail({ concept }: { concept: Concept }) {
  const [expandedLog, setExpandedLog] = useState(false)

  return (
    <div className="space-y-5 max-w-2xl text-xs">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-text-bright flex items-center gap-3">
          {concept.name}
          {concept.is_seed && (
            <span className="text-xs text-seed-color border border-seed-color/40 px-2 py-0.5">
              ИСХОДНАЯ
            </span>
          )}
        </h2>
        {concept.custom_label && (
          <div className="text-accent/70 mt-1">Метка разума: [{concept.custom_label}]</div>
        )}
        <div className="text-text-dim mt-1">Добавлена: {concept.mind_time_added}</div>
      </div>

      {/* Definition */}
      <div className="border border-border bg-panel/40 p-4">
        <div className="text-text-dim uppercase tracking-widest text-[10px] mb-2">Определение</div>
        <p className="text-text leading-relaxed">{concept.definition}</p>
      </div>

      {/* Stats */}
      <div className="flex gap-6">
        <Stat label="Связей" value={concept.connection_count} />
        <Stat label="Записей" value={concept.processing_logs?.length || 0} />
      </div>

      {/* Connections */}
      {concept.connections?.length > 0 && (
        <div>
          <div className="text-text-dim uppercase tracking-widest text-[10px] mb-2">Связи с другими концепциями</div>
          <div className="space-y-1">
            {concept.connections.map((c, i) => (
              <div key={i}
                   className="flex items-center gap-3 border-l-2 border-teal/40 pl-3 py-1">
                <span className="text-teal font-medium">{c.other_name}</span>
                <span className="text-text-dim/70 flex-1">{c.relationship}</span>
                <div className="w-16 bg-border h-1 rounded">
                  <div
                    className="bg-teal h-1 rounded"
                    style={{ width: `${c.strength * 100}%` }}
                  />
                </div>
                <span className="text-text-dim/50 w-8 text-right">{c.strength.toFixed(1)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Processing logs */}
      {concept.processing_logs?.length > 0 && (
        <div>
          <button
            onClick={() => setExpandedLog(!expandedLog)}
            className="text-text-dim uppercase tracking-widest text-[10px] flex items-center gap-1 hover:text-text mb-2"
          >
            {expandedLog ? '▼' : '▶'} Журнал обработки ({concept.processing_logs.length})
          </button>
          {expandedLog && concept.processing_logs.map((log, i) => (
            <div key={i} className="border border-border/50 bg-panel/30 p-3 mb-2
                                    text-text/80 leading-relaxed whitespace-pre-wrap mind-text">
              {log.content}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="text-center">
      <div className="text-2xl font-bold text-accent">{value}</div>
      <div className="text-text-dim text-[10px] uppercase tracking-widest">{label}</div>
    </div>
  )
}
