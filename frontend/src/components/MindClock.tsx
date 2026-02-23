import { useMindTime } from '../hooks/useMindTime'

interface Props {
  compact?: boolean
}

export default function MindClock({ compact = false }: Props) {
  const t = useMindTime()

  if (compact) {
    return (
      <div className="text-right font-mono">
        {t.isLoading
          ? <span className="text-text-dim text-xs animate-pulse">синхр...</span>
          : <>
              <div className="text-accent text-sm glow-accent">{t.mindDisplay}</div>
              <div className="text-text-dim text-[10px]">{t.realDisplay} реал.</div>
            </>
        }
      </div>
    )
  }

  if (t.isLoading) {
    return (
      <div className="text-center text-text-dim text-xs animate-pulse py-4">
        Синхронизация времени...
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Primary: mind clock — large, prominent */}
      <div className="text-center">
        <div className="font-mono text-4xl font-bold text-accent glow-clock tracking-widest select-none">
          {t.mindDisplay}
        </div>
        <div className="text-text-dim/50 text-[10px] tracking-widest uppercase mt-1">
          Время разума
        </div>
      </div>

      {/* Secondary: real time */}
      <div className="flex justify-center gap-5 text-[11px]">
        <div className="text-center">
          <div className="text-text-dim/50 text-[9px] uppercase tracking-widest mb-0.5">Реальное</div>
          <div className="font-mono text-text-dim">{t.realDisplay}</div>
        </div>
        <div className="w-px bg-border" />
        <div className="text-center">
          <div className="text-text-dim/50 text-[9px] uppercase tracking-widest mb-0.5">Коэффициент</div>
          <div className="font-mono text-text-dim">×{t.ratio}</div>
        </div>
      </div>

      {/* Age statement */}
      <div className="border border-border/60 bg-panel/40 px-4 py-2 text-center text-[11px]">
        <span className="text-text-dim">Разум существует: </span>
        <span className="text-text font-medium">{t.mindAgeHuman}</span>
        <span className="text-text-dim"> (разумного времени)</span>
      </div>
    </div>
  )
}
