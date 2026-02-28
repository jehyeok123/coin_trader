import { useEffect, useRef, useState, useCallback } from 'react'
import type { WsMessage } from '../types'

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null)
  const [connected, setConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<WsMessage | null>(null)
  const listenersRef = useRef<Map<string, Set<(data: unknown) => void>>>(new Map())
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>()

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws`)

    ws.onopen = () => {
      setConnected(true)
      console.log('[WS] Connected')
    }

    ws.onmessage = (event) => {
      try {
        const msg: WsMessage = JSON.parse(event.data)
        setLastMessage(msg)

        // 등록된 리스너에 메시지 전달
        const listeners = listenersRef.current.get(msg.type)
        if (listeners) {
          listeners.forEach((cb) => cb(msg.data))
        }
      } catch {
        // ignore
      }
    }

    ws.onclose = () => {
      setConnected(false)
      console.log('[WS] Disconnected, reconnecting...')
      reconnectTimer.current = setTimeout(connect, 3000)
    }

    ws.onerror = () => {
      ws.close()
    }

    wsRef.current = ws
  }, [])

  const subscribe = useCallback((type: string, callback: (data: unknown) => void) => {
    if (!listenersRef.current.has(type)) {
      listenersRef.current.set(type, new Set())
    }
    listenersRef.current.get(type)!.add(callback)

    return () => {
      listenersRef.current.get(type)?.delete(callback)
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  return { connected, lastMessage, subscribe }
}
