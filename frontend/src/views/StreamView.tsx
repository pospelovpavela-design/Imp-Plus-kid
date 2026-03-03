import { useState } from 'react'
import MindClock from '../components/MindClock'
import ThoughtFeed from '../components/ThoughtFeed'
import ConceptGraph from '../components/ConceptGraph'
import NodeDetail from '../components/NodeDetail'
import type { GraphData, GraphNode, ThoughtEvent } from '../types'

interface Props {
  graphData: GraphData
  initialEvents: ThoughtEvent[]
  token: string
  onGraphUpdate: (g: GraphData) => void
}

export default function StreamView({ graphData, initialEvents, token, onGraphUpdate }: Props) {
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [feedExpanded, setFeedExpanded] = useState(false)

  return (
    <div className="flex flex-col md:flex-row h-full overflow-hidden">
      {/* Left panel — clock + feed */}
      <div className={`md:w-[40%] w-full flex flex-col border-b md:border-b-0 md:border-r border-border overflow-hidden transition-all duration-300
                       ${feedExpanded ? 'flex-1 md:h-full' : 'h-[48vh] md:h-full'}`}>
        {/* Clock + expand toggle (mobile only) */}
        <div className="p-4 border-b border-border shrink-0 flex items-start justify-between">
          <MindClock />
          <button
            onClick={() => setFeedExpanded(!feedExpanded)}
            className="md:hidden ml-3 shrink-0 text-text-dim/60 hover:text-accent border border-border px-2 py-1 text-[10px] uppercase tracking-widest transition-colors"
          >
            {feedExpanded ? '↓ свернуть' : '↑ развернуть'}
          </button>
        </div>

        {/* Stats */}
        <div className="flex gap-4 px-4 py-2 border-b border-border text-[10px] text-text-dim shrink-0">
          <span>Концепций: <span className="text-text font-mono">{graphData.nodes.length}</span></span>
          <span>Связей: <span className="text-text font-mono">{graphData.links.length}</span></span>
        </div>

        {/* Thought feed */}
        <div className="flex-1 p-4 overflow-hidden">
          <ThoughtFeed initial={initialEvents} token={token} />
        </div>
      </div>

      {/* Right panel — concept graph (60%), hidden on mobile when feed expanded */}
      <div className={`flex-1 relative overflow-hidden bg-void ${feedExpanded ? 'hidden md:block' : 'block'}`}>
        <div className="absolute inset-0">
          <ConceptGraph
            data={graphData}
            onNodeClick={setSelectedNode}
            highlightIds={selectedNode ? new Set([selectedNode.id]) : undefined}
          />
        </div>

        {/* Legend — spec colours */}
        <div className="absolute top-3 left-3 text-[10px] text-text-dim space-y-1 pointer-events-none bg-void/70 px-2 py-1.5 border border-border/30">
          <div className="flex items-center gap-1.5">
            <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: '#4a2a7f' }} />
            семенные концепции
          </div>
          <div className="flex items-center gap-1.5">
            <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: '#2a4a7f' }} />
            добавленные
          </div>
          <div className="flex items-center gap-1.5">
            <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: '#6a4e00', boxShadow: '0 0 6px #c8a84b' }} />
            синтез разума
          </div>
          <div className="flex items-center gap-1.5">
            <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: '#7ab3ff' }} />
            выбранная
          </div>
        </div>

        <NodeDetail node={selectedNode} onClose={() => setSelectedNode(null)} />
      </div>
    </div>
  )
}
