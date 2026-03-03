import { useEffect, useState } from 'react'
import { isLoggedIn, logout, fetchGraph, fetchStreamHistory } from './api'
import Login from './components/Login'
import MindClock from './components/MindClock'
import StreamView from './views/StreamView'
import LibraryView from './views/LibraryView'
import ContemplationView from './views/ContemplationView'
import type { GraphData, ThoughtEvent } from './types'

type Tab = 'stream' | 'library' | 'contemplate'

const TABS: { id: Tab; label: string; icon: string; short: string }[] = [
  { id: 'stream',      label: 'ПОТОК',      icon: '◈', short: 'Поток' },
  { id: 'library',     label: 'БИБЛИОТЕКА', icon: '≡', short: 'Граф' },
  { id: 'contemplate', label: 'СОЗЕРЦАНИЕ', icon: '◇', short: 'Разум' },
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
        <div className="px-4 md:px-5 py-3 border-r border-border">
          <span className="text-accent font-bold tracking-[0.2em] glow-accent text-sm">
            IMPLUS
          </span>
        </div>

        {/* Tabs — hidden on mobile (bottom nav handles it) */}
        <nav className="hidden md:flex flex-1">
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

        {/* Mobile: flexible spacer */}
        <div className="flex-1 md:hidden" />

        {/* Right: compact clock + logout */}
        <div className="flex items-center gap-3 md:gap-4 px-3 md:px-4 border-l border-border">
          <MindClock compact />
          <button
            onClick={() => { logout(); setAuthed(false) }}
            className="text-text-dim/50 hover:text-text-dim text-[10px] uppercase tracking-widest"
          >
            Выйти
          </button>
        </div>
      </header>

      {/* Main content — pb-16 on mobile reserves space for bottom nav */}
      <main className="flex-1 overflow-hidden pb-16 md:pb-0">
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

      {/* Bottom navigation — mobile only */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 flex border-t border-border bg-deep z-50">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex-1 flex flex-col items-center justify-center py-3 gap-1 transition-colors relative
                        ${tab === t.id ? 'text-accent' : 'text-text-dim'}`}
          >
            <span className="text-lg leading-none">{t.icon}</span>
            <span className="text-[10px] uppercase tracking-widest">{t.short}</span>
            {tab === t.id && (
              <span className="absolute top-0 left-0 right-0 h-0.5 bg-accent" />
            )}
          </button>
        ))}
      </nav>
    </div>
  )
}
