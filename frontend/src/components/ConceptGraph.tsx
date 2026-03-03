import { useCallback, useEffect, useRef, useState } from 'react'
import type { GraphData, GraphNode } from '../types'

interface Props {
  data: GraphData
  onNodeClick?: (node: GraphNode) => void
  highlightIds?: Set<number>
}

// Lazy-load ForceGraph2D to avoid SSR issues
let ForceGraph2D: any = null

export default function ConceptGraph({ data, onNodeClick, highlightIds }: Props) {
  const [loaded, setLoaded] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const [dims, setDims] = useState({ w: 600, h: 400 })

  useEffect(() => {
    import('react-force-graph-2d').then((mod) => {
      ForceGraph2D = mod.default
      setLoaded(true)
    })
  }, [])

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
      const label = node.custom_label || node.name
      const isSeed = node.is_seed
      const isAutonomous = node.is_autonomous
      const isHighlighted = highlightIds?.has(node.id)
      const degree = node.degree || 1

      const radius = Math.max(4, Math.min(14, 4 + degree * 1.5))

      // Node circle
      ctx.beginPath()
      ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI)

      // spec colours: node-default #1e3a6e, node-seed #2d5a9e, node-active #4a7fff, autonomous gold
      if (isHighlighted) {
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

      // Label
      if (globalScale > 0.6) {
        const fontSize = Math.max(9, 10 / globalScale)
        ctx.font = `${fontSize}px 'JetBrains Mono', monospace`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'top'
        ctx.fillStyle = isHighlighted ? '#dde0f0' : isAutonomous ? '#c8a84b' : isSeed ? '#9bb3ff' : '#7880a0'
        ctx.fillText(label.length > 14 ? label.slice(0, 13) + '…' : label,
                     node.x, node.y + radius + 2)
      }
    },
    [highlightIds],
  )

  const linkCanvasObject = useCallback(
    (link: any, ctx: CanvasRenderingContext2D) => {
      const strength = link.strength || 0.5
      // spec: edges #1e2035
      const a = 0.2 + strength * 0.55
      ctx.strokeStyle = `rgba(30, 32, 53, ${a})`
      ctx.lineWidth = 0.5 + strength * 1.5
      ctx.beginPath()
      const src = link.source
      const tgt = link.target
      ctx.moveTo(src.x, src.y)
      ctx.lineTo(tgt.x, tgt.y)
      ctx.stroke()
    },
    [],
  )

  if (!loaded || !ForceGraph2D) {
    return (
      <div ref={containerRef} className="w-full h-full flex items-center justify-center">
        <span className="text-text-dim text-xs animate-pulse">Загрузка графа...</span>
      </div>
    )
  }

  return (
    <div ref={containerRef} className="w-full h-full overflow-hidden">
      <ForceGraph2D
        graphData={data}
        width={dims.w}
        height={dims.h}
        backgroundColor="transparent"
        nodeCanvasObject={nodeCanvasObject}
        nodeCanvasObjectMode={() => 'replace'}
        linkCanvasObject={linkCanvasObject}
        linkCanvasObjectMode={() => 'replace'}
        onNodeClick={(node: GraphNode) => onNodeClick?.(node)}
        nodeRelSize={6}
        linkDirectionalParticles={1}
        linkDirectionalParticleWidth={1}
        linkDirectionalParticleColor={() => 'rgba(61,127,255,0.5)'}
        cooldownTicks={120}
        d3AlphaDecay={0.02}
        d3VelocityDecay={0.4}
        enableZoomInteraction
        enablePanInteraction
      />
    </div>
  )
}
