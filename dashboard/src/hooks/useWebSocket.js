import { useState, useEffect, useRef, useCallback } from 'react'

const WS_BASE = import.meta.env.VITE_WS_URL || `ws://${window.location.host}`

export function useWebSocket(path = '/ws/live') {
  const [message, setMessage] = useState(null)
  const [connected, setConnected] = useState(false)
  const ws = useRef(null)
  const retryTimer = useRef(null)
  const retryCount = useRef(0)

  const connect = useCallback(() => {
    try {
      const url = `${WS_BASE}${path}`
      ws.current = new WebSocket(url)

      ws.current.onopen = () => {
        setConnected(true)
        retryCount.current = 0
      }

      ws.current.onmessage = (e) => {
        try {
          setMessage(JSON.parse(e.data))
        } catch { /* ignore */ }
      }

      ws.current.onclose = () => {
        setConnected(false)
        // exponential backoff retry สูงสุด 30 วินาที
        const delay = Math.min(1000 * 2 ** retryCount.current, 30000)
        retryCount.current++
        retryTimer.current = setTimeout(connect, delay)
      }

      ws.current.onerror = () => {
        ws.current?.close()
      }
    } catch {
      setConnected(false)
    }
  }, [path])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(retryTimer.current)
      ws.current?.close()
    }
  }, [connect])

  return { message, connected }
}
