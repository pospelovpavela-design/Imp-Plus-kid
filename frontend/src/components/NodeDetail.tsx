import type { GraphNode } from '../types'
import { useEffect, useState } from 'react'
import { fetchConcept } from '../api'
import type { Concept } from '../types'

interface Props {
  node: GraphNode | null
  onClose: () => void
}

export default function NodeDetail({ node, onClose }: Props) {
  const [concept, setConcept] = useState<Concept | null>(null)
  const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    if (!node) { setConcept(null); return }
    setLoading(true)
    setExpanded(false)
    fetchConcept(node.id)
      .then(setConcept)
      .catch(() => setConcept(null))
      .finally(() => setLoading(false))
  }, [node?.id])

  if (!node) return null

  return (
    <div className="absolute bottom-0 md:bottom-4 left-0 md:left-auto right-0 md:right-4
                    w-full md:w-80 bg-panel border-t md:border border-border-bright
                    shadow-2xl z-10 max-h-[70vh] flex flex-col animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between p-3 border-b border-border shrink-0">
        <div>
          <div className="text-text-bright font-bold text-sm">
            {node.name}
            {node.is_seed && (
              <span className="ml-2 text-seed-color text-[10px] border border-seed-color/40 px-1">
                SEED
              </span>
            )}
          </div>
          {node.custom_label && (
            <div className="text-accent/70 text-xs mt-0.5">[{node.custom_label}]</div>
          )}
          <div className="text-text-dim text-[10px] mt-0.5">{node.mind_time_added}</div>
        </div>
        <button onClick={onClose} className="text-text-dim hover:text-text ml-2 text-lg leading-none">×</button>
      </div>

      {loading && (
        <div className="p-4 text-text-dim text-xs animate-pulse">Загрузка...</div>
      )}

      {concept && !loading && (
        <div className="flex-1 overflow-y-auto p-3 space-y-3 text-xs">
          {/* Definition */}
          <div>
            <div className="text-text-dim uppercase tracking-widest text-[10px] mb-1">Определение</div>
            <div className="text-text">{concept.definition}</div>
          </div>

          {/* Stats */}
          <div className="flex gap-4 text-[10px] text-text-dim">
            <span>{concept.connection_count} связей</span>
            <span>{concept.processing_logs?.length || 0} записей в журнале</span>
          </div>

          {/* Connections */}
          {concept.connections?.length > 0 && (
            <div>
              <div className="text-text-dim uppercase tracking-widest text-[10px] mb-1">Связи</div>
              <div className="space-y-1">
                {concept.connections.map((c, i) => (
                  <div key={i} className="flex justify-between items-center border-l-2 border-accent/30 pl-2">
                    <span className="text-teal">{c.other_name}</span>
                    <span className="text-text-dim/60 text-[10px]">{c.relationship}</span>
                    <span className="text-text-dim/40 text-[10px]">{c.strength.toFixed(1)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Processing log */}
          {concept.processing_logs?.length > 0 && (
            <div>
              <button
                onClick={() => setExpanded(!expanded)}
                className="text-text-dim uppercase tracking-widest text-[10px] flex items-center gap-1 hover:text-text"
              >
                {expanded ? '▼' : '▶'} Журнал обработки
              </button>
              {expanded && (
                <div className="mt-2 space-y-2">
                  {concept.processing_logs.map((log, i) => (
                    <div key={i} className="text-text/70 border-l border-dim/30 pl-2 whitespace-pre-wrap leading-relaxed">
                      {log.content.slice(0, 600)}
                      {log.content.length > 600 && '…'}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
