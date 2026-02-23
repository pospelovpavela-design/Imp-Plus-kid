export interface TimeData {
  mind_display: string       // "День 2, 14:33:07"
  mind_age_human: string     // "2 дня 14 часов 33 минуты"
  mind_total_seconds: number
  mind_days: number
  mind_hours: number
  mind_minutes: number
  mind_seconds: number
  real_display: string       // "00:47:12"
  real_total_seconds: number
  ratio: number
  born_at: number
}

export interface Concept {
  id: number
  name: string
  definition: string
  mind_time_added: string
  real_time_added: number
  is_seed: boolean
  custom_label: string | null
  connection_count: number
  connections: ConceptConnection[]
  processing_logs: ProcessingLog[]
}

export interface ConceptConnection {
  other_name: string
  relationship: string
  strength: number
}

export interface ProcessingLog {
  content: string
  created_at: number
}

export interface GraphNode {
  id: number
  name: string
  is_seed: boolean
  mind_time_added: string
  degree: number
  custom_label: string | null
  // react-force-graph runtime fields
  x?: number
  y?: number
  vx?: number
  vy?: number
  fx?: number
  fy?: number
}

export interface GraphLink {
  source: number | GraphNode
  target: number | GraphNode
  relationship: string
  strength: number
}

export interface GraphData {
  nodes: GraphNode[]
  links: GraphLink[]
}

export interface ThoughtEvent {
  id: number
  mind_time: string
  type: 'spontaneous' | 'reaction' | 'milestone' | 'contemplation'
  content: string
  concepts_involved: string[]
  created_at: number
}

export interface Milestone {
  id: number
  milestone_key: string
  reached_at_real: number
  reached_at_mind: string
  reflection: string
}

export interface MindState {
  name: string
  born_at: number
  time: {
    mind_display: string
    mind_age_human: string
    real_display: string
  }
  concept_count: number
  connection_count: number
  stream_event_count: number
  milestones_reached: number
}
