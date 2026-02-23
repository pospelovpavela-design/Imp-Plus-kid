import { useEffect, useState } from 'react'
import { isLoggedIn, logout, fetchGraph, fetchStreamHistory } from './api'
import Login from './components/Login'
import MindClock from './components/MindClock'
import StreamView from './views/StreamView'
import LibraryView from './views/LibraryView'
import ContemplationView from './views/ContemplationView'
import type { GraphData, ThoughtEvent } from './types'

type Tab = 'stream' | 'library' | 'contemplate'

const TABS: { id: Tab; label: string }[] = [
  { id: 'stream',      label: 'ПОТОК' },
  { id: 'library',     label: 'БИБЛИОТЕКА' },
  { id: 'contemplate', label: 'СОЗЕРЦАНИЕ' },
]

export default function App() {
  const [authed, setAuthed] = useState(isLoggedIn())
  const [tab, setTab] = useState<Tab>('stream')
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], links: [] })
  const [initialEvents, setInitialEvents] = useState<ThoughtEvent[]>([])
  const [loading, setLoading] = useState(true)
  const token = localStorage.getItem('implus_token') ?? ''

  useEffect(() => {
    if (!authed) return
    Promise.all([fetchGraph(), fetchStreamHistory(50)])
      .then(([g, events]) => {
        setGraphData(g)
        setInitialEvents(events)
      })
      .catch(() => {
        // Token may have expired
        localStorage.removeItem('implus_token')
        setAuthed(false)
      })
      .finally(() => setLoading(false))
  }, [authed])

  if (!authed) {
    return <Login onLogin={() => setAuthed(true)} />
  }

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-text-dim text-xs animate-pulse tracking-widest">
          Загрузка разума...
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-void">
      {/* Top nav bar */}
      <header className="flex items-center gap-0 border-b border-border shrink-0 bg-deep">
        {/* Logo */}
        <div className="px-5 py-3 border-r border-border">
          <span className="text-accent font-bold tracking-[0.2em] glow-accent text-sm">
            IMPLUS
          </span>
        </div>

        {/* Tabs */}
        <nav className="flex flex-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-5 py-3 text-xs tracking-widest uppercase border-r border-border
                          transition-colors relative
                          ${tab === t.id
                            ? 'text-accent bg-accent/5'
                            : 'text-text-dim hover:text-text hover:bg-panel/40'}`}
            >
              {t.label}
              {tab === t.id && (
                <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-accent" />
              )}
            </button>
          ))}
        </nav>

        {/* Right: compact clock + logout */}
        <div className="flex items-center gap-4 px-4 border-l border-border">
          <MindClock compact />
          <button
            onClick={() => { logout(); setAuthed(false) }}
            className="text-text-dim/50 hover:text-text-dim text-[10px] uppercase tracking-widest"
          >
            Выйти
          </button>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 overflow-hidden">
        {tab === 'stream' && (
          <StreamView
            graphData={graphData}
            initialEvents={initialEvents}
            token={token}
            onGraphUpdate={setGraphData}
          />
        )}
        {tab === 'library' && (
          <LibraryView />
        )}
        {tab === 'contemplate' && (
          <ContemplationView onGraphUpdate={setGraphData} />
        )}
      </main>
    </div>
  )
}
