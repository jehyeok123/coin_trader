import { useState, useEffect } from 'react'
import { usePrices } from '../../contexts/PriceContext'

export default function Header() {
  const { connected, latencyMs } = usePrices()
  const [time, setTime] = useState(new Date())

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  const latencyColor = latencyMs < 500
    ? 'text-emerald-400'
    : latencyMs < 2000
      ? 'text-yellow-400'
      : 'text-red-400'

  return (
    <header className="bg-gray-800 border-b border-gray-700 px-6 py-3 flex items-center justify-between">
      <div className="flex items-center gap-4">
        <h1 className="text-xl font-bold text-primary-400">Coin Trader</h1>
        <span className="text-sm text-gray-400">자동 매매 시스템</span>
      </div>
      <div className="flex items-center gap-4">
        {/* 실시간 연결 상태 + Latency */}
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${connected ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`} />
          <span className="text-xs text-gray-400">
            {connected ? '실시간' : '연결 끊김'}
          </span>
          {connected && latencyMs > 0 && (
            <span className={`text-xs font-mono ${latencyColor}`}>
              {latencyMs}ms
            </span>
          )}
        </div>
        <span className="text-sm text-gray-400 font-mono">
          {time.toLocaleString('ko-KR')}
        </span>
      </div>
    </header>
  )
}
