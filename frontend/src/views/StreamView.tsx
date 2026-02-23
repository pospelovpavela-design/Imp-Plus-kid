import { useState } from 'react'
import MindClock from '../components/MindClock'
import ThoughtFeed from '../components/ThoughtFeed'
import ConceptGraph from '../components/ConceptGraph'
import NodeDetail from '../components/NodeDetail'
import type { GraphData, GraphNode, ThoughtEvent } from '../types'

interface Props {
  graphData: GraphData
  initialEvents: ThoughtEvent[]
  onGraphUpdate: (g: GraphData) => void
}

export default function StreamView({ graphData, initialEvents, onGraphUpdate }: Props) {
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)

  return (
    <div className="flex h-full gap-0 overflow-hidden">
      {/* Left panel — clock + feed (40%) */}
      <div className="w-[40%] flex flex-col border-r border-border overflow-hidden">
        {/* Clock section */}
        <div className="p-4 border-b border-border shrink-0">
          <MindClock />
        </div>

        {/* Stats bar */}
        <div className="flex gap-4 px-4 py-2 border-b border-border text-[10px] text-text-dim shrink-0">
          <span>Концепций: <span className="text-text">{graphData.nodes.length}</span></span>
          <span>Связей: <span className="text-text">{graphData.links.length}</span></span>
        </div>

        {/* Thought feed */}
        <div className="flex-1 p-4 overflow-hidden">
          <ThoughtFeed initial={initialEvents} />
        </div>
      </div>

      {/* Right panel — concept graph (60%) */}
      <div className="flex-1 relative overflow-hidden">
        <div className="absolute inset-0">
          <ConceptGraph
            data={graphData}
            onNodeClick={setSelectedNode}
            highlightIds={selectedNode ? new Set([selectedNode.id]) : undefined}
          />
        </div>

        {/* Legend */}
        <div className="absolute top-3 left-3 text-[10px] text-text-dim space-y-1 pointer-events-none">
          <div className="flex items-center gap-1.5">
            <span className="inline-block w-3 h-3 rounded-full bg-seed-color" />
            семенные концепции
          </div>
          <div className="flex items-center gap-1.5">
            <span className="inline-block w-3 h-3 rounded-full bg-teal" />
            добавленные
          </div>
        </div>

        {/* Node detail panel */}
        <NodeDetail node={selectedNode} onClose={() => setSelectedNode(null)} />
      </div>
    </div>
  )
}
