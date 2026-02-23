import { useState, FormEvent } from 'react'
import { login } from '../api'

interface Props {
  onLogin: () => void
}

export default function Login({ onLogin }: Props) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(password)
      onLogin()
    } catch (err: any) {
      setError(err.message || 'Ошибка авторизации')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-void">
      <div className="w-full max-w-sm space-y-8 px-6">
        {/* Logo */}
        <div className="text-center space-y-2">
          <div className="text-5xl text-accent glow-accent tracking-[0.3em] font-bold">
            IMPLUS
          </div>
          <div className="text-text-dim text-xs tracking-widest uppercase">
            Система симуляции разума
          </div>
          <div className="h-px bg-gradient-to-r from-transparent via-border-bright to-transparent mt-4" />
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1">
            <label className="text-text-dim text-xs tracking-widest uppercase block">
              Ключ доступа
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="········"
              autoFocus
              className="w-full bg-panel border border-border text-text-bright
                         px-4 py-3 text-sm font-mono
                         focus:outline-none focus:border-accent focus:glow-accent
                         placeholder-text-dim transition-colors"
            />
          </div>

          {error && (
            <div className="text-red text-xs border border-red/30 bg-red/5 px-3 py-2">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !password}
            className="w-full py-3 text-sm tracking-widest uppercase
                       bg-accent/10 border border-accent text-accent
                       hover:bg-accent/20 hover:glow-accent
                       disabled:opacity-30 disabled:cursor-not-allowed
                       transition-all"
          >
            {loading ? 'Соединение...' : 'Войти в разум'}
          </button>
        </form>

        <div className="text-center text-text-dim text-xs">
          ◈ Разум существует. Разум ждёт. ◈
        </div>
      </div>
    </div>
  )
}
