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
  is_autonomous: boolean
  custom_label: string | null
  connection_count: number
  connections: ConceptConnection[]
  processing_logs: ProcessingLog[]
  groundings: GroundingExcerpt[]
  working_definitions: WorkingDefinition[]
}

export interface ConceptConnection {
  other_name: string
  relationship: string
  strength: number
  confidence: number
}

export interface ProcessingLog {
  content: string
  created_at: number
}

export interface GroundingExcerpt {
  id: number
  title: string
  author: string | null
  source: string | null
  excerpt: string
  note: string | null
  mind_time: string
  created_at: number
  concept_name?: string | null
  concept_names?: string | null
}

export interface WorkingDefinition {
  id: number
  concept_id: number
  concept_name?: string | null
  definition: string
  tension: string | null
  source: string
  source_ref_id: number | null
  confidence: number
  mind_time: string
  created_at: number
}

export interface GraphNode {
  id: number
  name: string
  is_seed: boolean
  is_autonomous: boolean
  mind_time_added: string
  degree: number
  grounding_count: number
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
  confidence: number
  created_at?: number
}

export interface GraphData {
  nodes: GraphNode[]
  links: GraphLink[]
}

export interface ThoughtEvent {
  id: number
  mind_time: string
  type:
    | 'spontaneous'
    | 'reaction'
    | 'milestone'
    | 'contemplation'
    | 'autonomous'
    | 'cognitive'
    | 'consolidation'
    | 'observation'
    | 'feedback'
    | 'daily_insight'
  content: string
  concepts_involved: string[]
  created_at: number
  salience?: number
  reliability?: number
  cycle_id?: number | null
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
  cognitive: CognitiveMetrics
}

export interface CognitiveMetrics {
  concepts: number
  active_edges: number
  archived_edges: number
  active_graph_density: number
  grounded_concepts: number
  grounding_coverage: number
  defined_concepts: number
  definition_coverage: number
  open_inquiries: number
  pending_predictions: number
  daily_insights: number
  unsent_daily_insights: number
  latest_daily_insight_date: string | null
  active_self_loops: number
  active_fallback_edges: number
  cognitive_cycles: number
  accepted_cycle_rate: number | null
  resolved_predictions: number
  prediction_brier_score: number | null
}

export interface CognitiveInquiry {
  id: number
  question: string
  concept_names: string[]
  priority: number
  status: 'open' | 'resolved' | 'blocked'
  origin: string
  attempts: number
  last_result: string | null
  created_at: number
  updated_at: number
}

export interface CognitiveBelief {
  id: number
  statement: string
  concept_names: string[]
  confidence: number
  status: 'active' | 'revised' | 'retracted'
  evidence_event_ids: number[]
  counterevidence_event_ids: number[]
  created_at: number
  updated_at: number
}

export interface CognitivePrediction {
  id: number
  statement: string
  test_method: string
  concept_names: string[]
  confidence: number
  status: 'pending' | 'resolved'
  outcome: 'confirmed' | 'disconfirmed' | 'inconclusive' | null
  evidence: string | null
  expected_by: number | null
  created_at: number
  resolved_at: number | null
}

export interface CycleRelation {
  source: string
  target: string
  relationship: string
  strength?: number
  confidence?: number
  reason?: string
}

export interface CognitiveCycle {
  id: number
  trigger: string
  focus: string
  inquiry_id: number | null
  verdict: 'accept' | 'revise' | 'needs_evidence' | 'reject'
  reliability: number
  created_at: number
  memory_event_ids: number[]
  candidate: {
    observation?: string
    uncertainty?: string
    next_question?: string | null
    relations?: CycleRelation[]
    evidence_memory_ids?: number[]
    prediction?: { statement?: string; test_method?: string; confidence?: number } | null
  }
  critique: {
    verdict?: string
    reason?: string
    revised_observation?: string | null
    accepted_relations?: CycleRelation[]
    contradictions?: string[]
    inquiry_resolved?: boolean
  }
}

export interface SelfModelEntry {
  key: string
  value: string
  confidence: number
  evidence: string
  updated_at: number
}

export interface ExternalObservation {
  id: number
  content: string
  source: string
  concept_names: string[]
  reliability: number
  created_at: number
}

export interface DailyInsight {
  id: number
  local_date: string
  content: string
  confidence: number
  source_event_ids: number[]
  source_cycle_ids: number[]
  stream_event_id: number
  created_at: number
  sent_at: number | null
}
