import type { TimeData, Concept, GraphData, ThoughtEvent, MindState, Milestone } from './types'

const BASE = ''  // proxied by Vite

function getToken(): string {
  return localStorage.getItem('implus_token') || ''
}

function authHeaders(): HeadersInit {
  return { Authorization: `Bearer ${getToken()}`, 'Content-Type': 'application/json' }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.status === 401) {
    localStorage.removeItem('implus_token')
    window.location.reload()
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(body.detail || res.statusText)
  }
  return res.json()
}

// ── Auth ────────────────────────────────────────────────────────────────────

export async function login(password: string): Promise<string> {
  const res = await fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password }),
  })
  const data = await handleResponse<{ token: string }>(res)
  localStorage.setItem('implus_token', data.token)
  return data.token
}

export function logout(): void {
  localStorage.removeItem('implus_token')
}

export function isLoggedIn(): boolean {
  return !!localStorage.getItem('implus_token')
}

// ── Time ────────────────────────────────────────────────────────────────────

export async function fetchTime(): Promise<TimeData> {
  const res = await fetch(`${BASE}/time`, { headers: authHeaders() })
  return handleResponse<TimeData>(res)
}

export async function fetchMilestones(): Promise<Milestone[]> {
  const res = await fetch(`${BASE}/time/milestones`, { headers: authHeaders() })
  return handleResponse<Milestone[]>(res)
}

// ── Concept ─────────────────────────────────────────────────────────────────

export async function fetchGraph(): Promise<GraphData> {
  const res = await fetch(`${BASE}/concept/graph`, { headers: authHeaders() })
  return handleResponse<GraphData>(res)
}

export async function fetchConcepts(): Promise<Concept[]> {
  const res = await fetch(`${BASE}/concept/list`, { headers: authHeaders() })
  return handleResponse<Concept[]>(res)
}

export async function fetchConcept(id: number): Promise<Concept> {
  const res = await fetch(`${BASE}/concept/${id}`, { headers: authHeaders() })
  return handleResponse<Concept>(res)
}

/**
 * Add concept with streaming.
 * onChunk: called with each text chunk.
 * Returns the final graph data and concept_id.
 */
export async function addConceptStream(
  name: string,
  definition: string,
  onChunk: (text: string) => void,
): Promise<{ concept_id: number; graph: GraphData }> {
  const res = await fetch(`${BASE}/concept/add`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ name, definition }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(body.detail || res.statusText)
  }
  return readSSEStream(res, onChunk)
}

// ── Contemplation ───────────────────────────────────────────────────────────

export async function contemplateStream(
  thought: string,
  onChunk: (text: string) => void,
): Promise<void> {
  const res = await fetch(`${BASE}/contemplate`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ thought }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(body.detail || res.statusText)
  }
  await readSSEStream(res, onChunk)
}

// ── Stream SSE ──────────────────────────────────────────────────────────────

export function openEventStream(
  onEvent: (event: ThoughtEvent) => void,
): () => void {
  const token = getToken()
  const url = `${BASE}/stream?token=${encodeURIComponent(token)}`
  const es = new EventSource(url)
  es.onmessage = (e) => {
    if (!e.data || e.data.startsWith(':')) return
    try {
      const ev = JSON.parse(e.data) as ThoughtEvent
      if (ev.id) onEvent(ev)
    } catch { /* ignore parse errors */ }
  }
  es.onerror = () => {
    // EventSource auto-reconnects
  }
  return () => es.close()
}

// ── Mind State ──────────────────────────────────────────────────────────────

export async function fetchMindState(): Promise<MindState> {
  const res = await fetch(`${BASE}/mind/state`, { headers: authHeaders() })
  return handleResponse<MindState>(res)
}

// ── History ─────────────────────────────────────────────────────────────────

export async function fetchStreamHistory(limit = 50, offset = 0): Promise<ThoughtEvent[]> {
  const res = await fetch(`${BASE}/history/stream?limit=${limit}&offset=${offset}`, {
    headers: authHeaders(),
  })
  return handleResponse<ThoughtEvent[]>(res)
}

// ── Shared SSE reader ────────────────────────────────────────────────────────

async function readSSEStream(res: Response, onChunk: (t: string) => void): Promise<any> {
  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let finalData: any = null

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const raw = line.slice(6)
      try {
        const parsed = JSON.parse(raw)
        if (parsed.chunk !== undefined) {
          onChunk(parsed.chunk)
        } else if (parsed.done) {
          finalData = parsed
        }
      } catch { /* ignore */ }
    }
  }
  return finalData
}
