import { useState, useEffect } from 'react'
import { getTradeHistory } from '../../services/api'
import type { Trade } from '../../types'

export default function RecentTrades() {
  const [trades, setTrades] = useState<Trade[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetch = async () => {
      try {
        const res = await getTradeHistory({ limit: 10 })
        setTrades(res.data.trades || [])
      } catch {
        // 연결 안 됨
      } finally {
        setLoading(false)
      }
    }
    fetch()
    const interval = setInterval(fetch, 10000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="card">
      <h3 className="text-lg font-semibold mb-4">최근 거래</h3>
      {loading ? (
        <p className="text-gray-500">로딩 중...</p>
      ) : trades.length > 0 ? (
        <div className="space-y-2">
          {trades.map((trade) => (
            <div
              key={trade.id}
              className="flex items-center justify-between py-2 border-b border-gray-700/50 last:border-0"
            >
              <div className="flex items-center gap-3">
                <span className={trade.side === 'buy' ? 'badge-buy' : 'badge-sell'}>
                  {trade.side === 'buy' ? '매수' : '매도'}
                </span>
                <div>
                  <p className="font-mono text-sm">{trade.symbol}</p>
                  <p className="text-xs text-gray-500">
                    {new Date(trade.created_at).toLocaleString('ko-KR')}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-sm font-medium">
                  {trade.amount_krw.toLocaleString()} KRW
                </p>
                {trade.pnl_pct != null && (
                  <p className={`text-xs font-semibold ${trade.pnl_pct >= 0 ? 'text-profit' : 'text-loss'}`}>
                    {trade.pnl_pct >= 0 ? '+' : ''}{trade.pnl_pct.toFixed(2)}%
                  </p>
                )}
                {trade.reason && (
                  <p className="text-xs text-gray-500 max-w-[200px] truncate">
                    {trade.reason}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-gray-500 text-sm">거래 내역이 없습니다.</p>
      )}
    </div>
  )
}
