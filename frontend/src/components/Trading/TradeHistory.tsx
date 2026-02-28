import { useState, useEffect } from 'react'
import { getTradeHistory } from '../../services/api'
import type { Trade } from '../../types'

export default function TradeHistory() {
  const [trades, setTrades] = useState<Trade[]>([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(0)
  const [filterSide, setFilterSide] = useState<string>('')
  const limit = 20

  const fetchTrades = async () => {
    setLoading(true)
    try {
      const res = await getTradeHistory({
        limit,
        offset: page * limit,
        side: filterSide || undefined,
      })
      setTrades(res.data.trades || [])
    } catch {
      setTrades([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchTrades()
  }, [page, filterSide])

  const totalPnl = trades
    .filter((t) => t.pnl != null)
    .reduce((sum, t) => sum + (t.pnl || 0), 0)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">거래 내역</h2>
          <p className="text-gray-400 text-sm mt-1">자동 매매 거래 기록</p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={filterSide}
            onChange={(e) => { setFilterSide(e.target.value); setPage(0) }}
            className="input-field text-sm"
          >
            <option value="">전체</option>
            <option value="buy">매수</option>
            <option value="sell">매도</option>
          </select>
        </div>
      </div>

      <div className="card">
        {loading ? (
          <p className="text-gray-500">로딩 중...</p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-400 border-b border-gray-700">
                    <th className="text-left py-3 px-2">시간</th>
                    <th className="text-left py-3 px-2">종류</th>
                    <th className="text-left py-3 px-2">종목</th>
                    <th className="text-right py-3 px-2">가격</th>
                    <th className="text-right py-3 px-2">수량</th>
                    <th className="text-right py-3 px-2">금액</th>
                    <th className="text-right py-3 px-2">수익률</th>
                    <th className="text-left py-3 px-2">사유</th>
                  </tr>
                </thead>
                <tbody>
                  {trades.map((trade) => (
                    <tr key={trade.id} className="border-b border-gray-700/50 hover:bg-gray-700/30">
                      <td className="py-2.5 px-2 text-xs text-gray-400">
                        {new Date(trade.created_at).toLocaleString('ko-KR')}
                      </td>
                      <td className="py-2.5 px-2">
                        <span className={trade.side === 'buy' ? 'badge-buy' : 'badge-sell'}>
                          {trade.side === 'buy' ? '매수' : '매도'}
                        </span>
                      </td>
                      <td className="py-2.5 px-2 font-mono text-primary-400">{trade.symbol}</td>
                      <td className="py-2.5 px-2 text-right">{trade.price.toLocaleString()}</td>
                      <td className="py-2.5 px-2 text-right">{trade.quantity.toFixed(8)}</td>
                      <td className="py-2.5 px-2 text-right">{trade.amount_krw.toLocaleString()}</td>
                      <td className={`py-2.5 px-2 text-right font-semibold ${
                        trade.pnl_pct != null
                          ? trade.pnl_pct >= 0 ? 'text-profit' : 'text-loss'
                          : 'text-gray-500'
                      }`}>
                        {trade.pnl_pct != null ? `${trade.pnl_pct >= 0 ? '+' : ''}${trade.pnl_pct.toFixed(2)}%` : '-'}
                      </td>
                      <td className="py-2.5 px-2 text-xs text-gray-400 max-w-[200px] truncate">
                        {trade.reason || '-'}
                      </td>
                    </tr>
                  ))}
                  {trades.length === 0 && (
                    <tr>
                      <td colSpan={8} className="py-8 text-center text-gray-500">
                        거래 내역이 없습니다.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* 페이지네이션 */}
            <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-700">
              <div className="text-sm text-gray-400">
                총 실현 손익: <span className={`font-semibold ${totalPnl >= 0 ? 'text-profit' : 'text-loss'}`}>
                  {totalPnl >= 0 ? '+' : ''}{totalPnl.toLocaleString()} KRW
                </span>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage(Math.max(0, page - 1))}
                  disabled={page === 0}
                  className="btn-outline text-sm disabled:opacity-50"
                >
                  이전
                </button>
                <span className="px-3 py-2 text-sm text-gray-400">
                  {page + 1} 페이지
                </span>
                <button
                  onClick={() => setPage(page + 1)}
                  disabled={trades.length < limit}
                  className="btn-outline text-sm disabled:opacity-50"
                >
                  다음
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
