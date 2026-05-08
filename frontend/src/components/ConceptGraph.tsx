import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { GraphData, GraphLink, GraphNode } from '../types'

interface Props {
  data: GraphData
  onNodeClick?: (node: GraphNode) => void
  highlightIds?: Set<number>
}

// Lazy-load ForceGraph2D to avoid SSR issues
let ForceGraph2D: any = null

type ViewMode = 'structure' | 'influence' | 'experience'

function linkEndpointId(endpoint: number | GraphNode): number {
  return typeof endpoint === 'number' ? endpoint : endpoint.id
}

function linkEndpointNode(endpoint: number | GraphNode): GraphNode | null {
  return typeof endpoint === 'number' ? null : endpoint
}

export default function ConceptGraph({ data, onNodeClick, highlightIds }: Props) {
  const [loaded, setLoaded] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const graphRef = useRef<any>(null)
  const [dims, setDims] = useState({ w: 600, h: 400 })
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [focusId, setFocusId] = useState('')
  const [viewMode, setViewMode] = useState<ViewMode>('influence')

  useEffect(() => {
    const ids = highlightIds ? Array.from(highlightIds) : []
    if (ids.length === 1) {
      setSelectedId(ids[0])
      setFocusId(String(ids[0]))
    } else if (ids.length === 0) {
      setSelectedId(null)
    }
  }, [highlightIds])

  const nodeById = useMemo(() => {
    const map = new Map<number, GraphNode>()
    data.nodes.forEach((node) => map.set(node.id, node))
    return map
  }, [data.nodes])

  const influence = useMemo(() => {
    if (!selectedId) return new Map<number, number>()
    const related = data.links
      .map((link) => {
        const sourceId = linkEndpointId(link.source)
        const targetId = linkEndpointId(link.target)
        if (sourceId === selectedId) return { id: targetId, strength: link.strength || 0.5 }
        if (targetId === selectedId) return { id: sourceId, strength: link.strength || 0.5 }
        return null
      })
      .filter(Boolean) as { id: number; strength: number }[]
    const total = related.reduce((sum, item) => sum + item.strength, 0) || 1
    return new Map(related.map((item) => [item.id, item.strength / total]))
  }, [data.links, selectedId])

  const globalInfluence = useMemo(() => {
    const weights = new Map<number, number>()
    data.links.forEach((link) => {
      const strength = link.strength || 0.5
      const sourceId = linkEndpointId(link.source)
      const targetId = linkEndpointId(link.target)
      weights.set(sourceId, (weights.get(sourceId) || 0) + strength)
      weights.set(targetId, (weights.get(targetId) || 0) + strength)
    })
    const max = Math.max(1, ...Array.from(weights.values()))
    return new Map(Array.from(weights.entries()).map(([id, value]) => [id, value / max]))
  }, [data.links])

  const sortedInfluence = useMemo(() => {
    return Array.from(influence.entries())
      .map(([id, value]) => ({ node: nodeById.get(id), value }))
      .filter((item): item is { node: GraphNode; value: number } => Boolean(item.node))
      .sort((a, b) => b.value - a.value)
      .slice(0, 8)
  }, [influence, nodeById])

  useEffect(() => {
    import('react-force-graph-2d').then((mod) => {
      ForceGraph2D = mod.default
      setLoaded(true)
    })
  }, [])

  function focusNode(node: GraphNode, zoom = 3.2) {
    setSelectedId(node.id)
    setFocusId(String(node.id))
    onNodeClick?.(node)
    if (graphRef.current && typeof node.x === 'number' && typeof node.y === 'number') {
      graphRef.current.centerAt(node.x, node.y, 700)
      graphRef.current.zoom(zoom, 700)
    }
  }

  function focusSelected() {
    const id = Number(focusId)
    const node = nodeById.get(id)
    if (node) focusNode(node)
  }

  function zoomToFit() {
    graphRef.current?.zoomToFit?.(700, 40)
  }

  useEffect(() => {
    if (!containerRef.current) return
    const ro = new ResizeObserver((entries) => {
      for (const e of entries) {
        setDims({ w: e.contentRect.width, h: e.contentRect.height })
      }
    })
    ro.observe(containerRef.current)
    return () => ro.disconnect()
  }, [])

  const nodeCanvasObject = useCallback(
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const label = node.name
      const isSeed = node.is_seed
      const isAutonomous = node.is_autonomous
      const isSelected = selectedId === node.id || highlightIds?.has(node.id)
      const degree = node.degree || 1
      const groundingCount = node.grounding_count || 0
      const localInfluence = influence.get(node.id) || 0
      const globalInfluenceValue = globalInfluence.get(node.id) || 0
      const displayInfluence = selectedId === null ? globalInfluenceValue : localInfluence
      const isInfluencer = viewMode === 'influence' && displayInfluence > 0 && selectedId !== node.id

      const baseRadius = Math.max(4, Math.min(14, 4 + degree * 1.5))
      const influenceBoost = viewMode === 'influence' ? displayInfluence * 18 : 0
      const experienceBoost = viewMode === 'experience' && groundingCount > 0 ? Math.min(6, groundingCount * 1.5) : 0
      const radius = baseRadius + influenceBoost + experienceBoost

      if (groundingCount > 0) {
        ctx.beginPath()
        ctx.arc(node.x, node.y, radius + 5 + Math.min(8, groundingCount * 2), 0, 2 * Math.PI)
        ctx.strokeStyle = viewMode === 'experience'
          ? `rgba(200, 168, 75, ${Math.min(0.9, 0.35 + groundingCount * 0.12)})`
          : 'rgba(200, 168, 75, 0.35)'
        ctx.lineWidth = viewMode === 'experience' ? 1.8 : 1
        ctx.setLineDash(viewMode === 'experience' ? [3, 4] : [])
        ctx.stroke()
        ctx.setLineDash([])
      }

      if (isInfluencer) {
        ctx.beginPath()
        ctx.arc(node.x, node.y, radius + 7, 0, 2 * Math.PI)
        ctx.strokeStyle = `rgba(45, 158, 107, ${0.2 + displayInfluence * 0.75})`
        ctx.lineWidth = 1 + displayInfluence * 5
        ctx.stroke()
      }

      // Node circle
      ctx.beginPath()
      ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI)

      // spec colours: node-default #1e3a6e, node-seed #2d5a9e, node-active #4a7fff, autonomous gold
      if (isSelected) {
        ctx.fillStyle = '#4a7fff'
        ctx.shadowColor = '#4a7fff'
        ctx.shadowBlur = 18
      } else if (isAutonomous) {
        ctx.fillStyle = '#6a4e00'
        ctx.shadowColor = '#c8a84b'
        ctx.shadowBlur = 16
      } else if (isSeed) {
        ctx.fillStyle = '#2d5a9e'
        ctx.shadowColor = '#3d7fff'
        ctx.shadowBlur = 10
      } else {
        ctx.fillStyle = '#1e3a6e'
        ctx.shadowColor = '#3d7fff'
        ctx.shadowBlur = 7
      }
      ctx.fill()
      ctx.shadowBlur = 0

      if (groundingCount > 0) {
        ctx.beginPath()
        ctx.arc(node.x + radius * 0.65, node.y - radius * 0.65, Math.max(2.2, Math.min(4, groundingCount + 1)), 0, 2 * Math.PI)
        ctx.fillStyle = '#c8a84b'
        ctx.fill()
      }

      // Label
      if (globalScale > 0.55 || isSelected || isInfluencer) {
        const fontSize = Math.max(9, 10 / globalScale)
        ctx.font = `${fontSize}px 'JetBrains Mono', monospace`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'top'
        ctx.fillStyle = isSelected ? '#dde0f0' : isInfluencer ? '#a0e0c0' : isAutonomous ? '#c8a84b' : isSeed ? '#9bb3ff' : '#7880a0'
        ctx.fillText(label.length > 14 ? label.slice(0, 13) + '…' : label,
                     node.x, node.y + radius + 2)
        if (isInfluencer && viewMode === 'influence') {
          ctx.font = `${Math.max(8, 8 / globalScale)}px 'JetBrains Mono', monospace`
          ctx.fillStyle = '#2d9e6b'
          ctx.fillText(`${Math.round(displayInfluence * 100)}%`, node.x, node.y + radius + fontSize + 3)
        }
      }
    },
    [globalInfluence, highlightIds, influence, selectedId, viewMode],
  )

  const linkCanvasObject = useCallback(
    (link: GraphLink, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const strength = link.strength || 0.5
      const sourceId = linkEndpointId(link.source)
      const targetId = linkEndpointId(link.target)
      const touchesSelected = selectedId !== null && (sourceId === selectedId || targetId === selectedId)
      const source = linkEndpointNode(link.source) || nodeById.get(sourceId)
      const target = linkEndpointNode(link.target) || nodeById.get(targetId)
      if (!source || !target) return

      // spec: edges #1e2035
      const a = touchesSelected ? 0.45 + strength * 0.5 : 0.16 + strength * 0.35
      ctx.strokeStyle = touchesSelected && viewMode === 'influence'
        ? `rgba(45, 158, 107, ${a})`
        : `rgba(61, 127, 255, ${a})`
      ctx.lineWidth = touchesSelected ? 1.5 + strength * 4 : 0.4 + strength * 1.4
      ctx.beginPath()
      ctx.moveTo(source.x || 0, source.y || 0)
      ctx.lineTo(target.x || 0, target.y || 0)
      ctx.stroke()

      if (touchesSelected && globalScale > 0.9) {
        const x = ((source.x || 0) + (target.x || 0)) / 2
        const y = ((source.y || 0) + (target.y || 0)) / 2
        ctx.font = `${Math.max(7, 8 / globalScale)}px 'JetBrains Mono', monospace`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillStyle = '#a0e0c0'
        ctx.fillText(strength.toFixed(1), x, y)
      }
    },
    [nodeById, selectedId, viewMode],
  )

  if (!loaded || !ForceGraph2D) {
    return (
      <div ref={containerRef} className="w-full h-full flex items-center justify-center">
        <span className="text-text-dim text-xs animate-pulse">Загрузка графа...</span>
      </div>
    )
  }

  return (
    <div ref={containerRef} className="w-full h-full overflow-hidden relative">
      <ForceGraph2D
        ref={graphRef}
        graphData={data}
        width={dims.w}
        height={dims.h}
        backgroundColor="transparent"
        nodeCanvasObject={nodeCanvasObject}
        nodeCanvasObjectMode={() => 'replace'}
        linkCanvasObject={linkCanvasObject}
        linkCanvasObjectMode={() => 'replace'}
        onNodeClick={(node: GraphNode) => focusNode(node)}
        nodeRelSize={6}
        linkDirectionalParticles={(link: GraphLink) => {
          const sourceId = linkEndpointId(link.source)
          const targetId = linkEndpointId(link.target)
          return selectedId !== null && (sourceId === selectedId || targetId === selectedId) ? 3 : 0
        }}
        linkDirectionalParticleWidth={(link: GraphLink) => 1 + (link.strength || 0.5) * 2}
        linkDirectionalParticleColor={() => viewMode === 'influence' ? 'rgba(45,158,107,0.8)' : 'rgba(61,127,255,0.5)'}
        cooldownTicks={120}
        d3AlphaDecay={0.02}
        d3VelocityDecay={0.4}
        enableZoomInteraction
        enablePanInteraction
      />

      <div className="absolute top-3 right-3 w-72 max-w-[calc(100%-1.5rem)] border border-border/60 bg-void/85 backdrop-blur-sm p-2 text-xs space-y-2">
        <div className="flex gap-1">
          {([
            ['structure', 'Структура'],
            ['influence', 'Влияние'],
            ['experience', 'Опыт'],
          ] as [ViewMode, string][]).map(([mode, label]) => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              className={`flex-1 px-2 py-1 border text-[10px] uppercase tracking-widest transition-colors ${
                viewMode === mode
                  ? 'border-accent text-accent bg-accent/10'
                  : 'border-border text-text-dim hover:text-text'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="flex gap-1">
          <select
            value={focusId}
            onChange={(e) => setFocusId(e.target.value)}
            className="min-w-0 flex-1 bg-panel border border-border text-text px-2 py-1 text-[11px] focus:outline-none focus:border-accent"
          >
            <option value="">Выбрать концепцию</option>
            {data.nodes
              .slice()
              .sort((a, b) => a.name.localeCompare(b.name, 'ru'))
              .map((node) => (
                <option key={node.id} value={node.id}>{node.name}</option>
              ))}
          </select>
          <button
            onClick={focusSelected}
            disabled={!focusId}
            className="px-2 py-1 border border-accent/60 text-accent disabled:opacity-30 disabled:cursor-not-allowed"
          >
            Фокус
          </button>
          <button onClick={zoomToFit} className="px-2 py-1 border border-border text-text-dim hover:text-text">
            Все
          </button>
        </div>
        {selectedId && (
          <div className="border-t border-border/50 pt-2">
            <div className="flex items-center justify-between gap-2">
              <div className="text-text-bright truncate">{nodeById.get(selectedId)?.name}</div>
              <button
                onClick={() => {
                  setSelectedId(null)
                  setFocusId('')
                }}
                className="text-text-dim/60 hover:text-text-dim"
              >
                x
              </button>
            </div>
            <div className="mt-2 space-y-1">
              {sortedInfluence.length === 0 && (
                <div className="text-text-dim/70">Связанные влияния не найдены</div>
              )}
              {sortedInfluence.map(({ node, value }) => (
                <button
                  key={node.id}
                  onClick={() => focusNode(node)}
                  className="w-full grid grid-cols-[1fr_auto] gap-2 items-center text-left hover:bg-panel/60 px-1 py-0.5"
                >
                  <span className="truncate text-text-dim">{node.name}</span>
                  <span className="text-teal font-mono">{Math.round(value * 100)}%</span>
                  <span className="col-span-2 h-1 bg-border overflow-hidden">
                    <span className="block h-full bg-teal" style={{ width: `${Math.max(3, value * 100)}%` }} />
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
