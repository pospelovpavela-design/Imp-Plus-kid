import { useState } from 'react'
import type { Concept } from '../types'

interface Props {
  concept: Concept
  isSelected?: boolean
  compact?: boolean
  onClick?: () => void
}

/**
 * ConceptCard — used in both LibraryView (list) and as suggestion chips
 * after contemplation analysis.
 */
export default function ConceptCard({ concept, isSelected, compact, onClick }: Props) {
  if (compact) {
    return (
      <button
        onClick={onClick}
        className={`w-full text-left px-3 py-2 border transition-colors text-xs
          ${isSelected
            ? 'border-accent bg-accent/10 text-accent'
            : 'border-border text-text hover:border-accent/50 hover:bg-panel-raised'}`}
      >
        <div className="flex items-center justify-between">
          <span className={`font-mono font-medium ${concept.is_seed ? 'text-node-seed' : 'text-accent'}`}>
            {concept.name}
          </span>
          {concept.custom_label && (
            <span className="text-text-dim text-[10px]">[{concept.custom_label}]</span>
          )}
        </div>
        <div className="text-text-dim text-[10px] mt-0.5 flex gap-2">
          <span>{concept.mind_time_added}</span>
          <span>·</span>
          <span>{concept.connection_count} связей</span>
          {concept.is_seed && <span className="text-node-seed/70">seed</span>}
        </div>
      </button>
    )
  }

  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-3 py-3 border-b border-border/50 text-xs
                  transition-colors group
                  ${isSelected
                    ? 'bg-panel-raised border-l-2 border-l-accent'
                    : 'border-l-2 border-l-transparent hover:bg-panel hover:border-l-accent/40'}`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className={`font-mono font-medium ${concept.is_seed ? 'text-node-seed' : 'text-text-bright'}`}>
          {concept.name}
        </span>
        {concept.custom_label && (
          <span className="text-accent/60 text-[10px] shrink-0">[{concept.custom_label}]</span>
        )}
        {concept.is_seed && (
          <span className="text-[9px] text-node-seed/70 border border-node-seed/30 px-1 shrink-0">SEED</span>
        )}
      </div>
      <div className="flex gap-3 mt-0.5 text-[10px] text-text-dim">
        <span className="font-mono">{concept.mind_time_added}</span>
        <span>{concept.connection_count} связей</span>
      </div>
      <p className="text-text-dim/70 mt-1 line-clamp-1 text-[10px]">{concept.definition}</p>
    </button>
  )
}
