/**
 * useSSE — Server-Sent Events with automatic exponential-backoff reconnect.
 *
 * The token is passed as a query param because EventSource does not support
 * custom request headers.
 */
import { useEffect, useRef, useState, useCallback } from 'react'

interface UseSSEOptions {
  /** Minimum reconnect delay in ms (doubles on each failure, capped at maxDelay). */
  minDelay?: number
  maxDelay?: number
  enabled?: boolean
}

export function useSSE<T>(
  url: string,
  onEvent: (data: T) => void,
  options: UseSSEOptions = {},
): { connected: boolean; reconnectCount: number } {
  const { minDelay = 1_000, maxDelay = 30_000, enabled = true } = options

  const [connected, setConnected] = useState(false)
  const [reconnectCount, setReconnectCount] = useState(0)

  // Use a ref so the latest onEvent is always called without recreating the effect
  const onEventRef = useRef(onEvent)
  useEffect(() => { onEventRef.current = onEvent }, [onEvent])

  useEffect(() => {
    if (!enabled) return

    let es: EventSource | null = null
    let retryTimer: ReturnType<typeof setTimeout> | null = null
    let retryDelay = minDelay
    let dead = false

    function connect() {
      if (dead) return
      es = new EventSource(url)

      es.onopen = () => {
        setConnected(true)
        retryDelay = minDelay  // reset backoff on success
      }

      es.onmessage = (e: MessageEvent) => {
        if (!e.data || e.data.startsWith(':')) return
        try {
          const parsed = JSON.parse(e.data) as T
          onEventRef.current(parsed)
        } catch {
          // Ignore parse errors — might be a keepalive comment
        }
      }

      es.onerror = () => {
        if (dead) return
        setConnected(false)
        es?.close()
        es = null

        retryTimer = setTimeout(() => {
          if (dead) return
          retryDelay = Math.min(retryDelay * 2, maxDelay)
          setReconnectCount((n) => n + 1)
          connect()
        }, retryDelay)
      }
    }

    connect()

    return () => {
      dead = true
      if (retryTimer) clearTimeout(retryTimer)
      es?.close()
      setConnected(false)
    }
  }, [url, enabled, minDelay, maxDelay])

  return { connected, reconnectCount }
}
