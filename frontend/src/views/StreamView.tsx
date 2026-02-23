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

  return (
    <div className="flex h-full overflow-hidden">
      {/* Left panel — clock + feed (40%) */}
      <div className="w-[40%] flex flex-col border-r border-border overflow-hidden">
        {/* Clock */}
        <div className="p-4 border-b border-border shrink-0">
          <MindClock />
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

      {/* Right panel — concept graph (60%) */}
      <div className="flex-1 relative overflow-hidden bg-void">
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
            <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: '#7ab3ff' }} />
            выбранная
          </div>
        </div>

        <NodeDetail node={selectedNode} onClose={() => setSelectedNode(null)} />
      </div>
    </div>
  )
}
