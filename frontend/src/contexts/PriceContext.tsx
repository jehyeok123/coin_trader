import { createContext, useContext, useEffect, useRef, useState, useCallback, type ReactNode } from 'react'

interface PriceState {
  /** 전체 코인 가격 맵 (KRW-BTC → 가격) */
  prices: Record<string, number>
  /** 업비트 API 응답 latency (ms) */
  latencyMs: number
  /** WebSocket 연결 상태 */
  connected: boolean
  /** 마지막 업데이트 시각 */
  lastUpdate: Date | null
}

const PriceContext = createContext<PriceState>({
  prices: {},
  latencyMs: 0,
  connected: false,
  lastUpdate: null,
})

export function usePrices() {
  return useContext(PriceContext)
}

export function PriceProvider({ children }: { children: ReactNode }) {
  const [prices, setPrices] = useState<Record<string, number>>({})
  const [latencyMs, setLatencyMs] = useState(0)
  const [connected, setConnected] = useState(false)
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>()

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws`)

    ws.onopen = () => {
      setConnected(true)
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.type === 'price_update' && msg.data) {
          setPrices(msg.data.prices || {})
          setLatencyMs(msg.data.latency_ms || 0)
          setLastUpdate(new Date())
        }
      } catch {
        // ignore
      }
    }

    ws.onclose = () => {
      setConnected(false)
      reconnectTimer.current = setTimeout(connect, 3000)
    }

    ws.onerror = () => {
      ws.close()
    }

    wsRef.current = ws
  }, [])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  return (
    <PriceContext.Provider value={{ prices, latencyMs, connected, lastUpdate }}>
      {children}
    </PriceContext.Provider>
  )
}
