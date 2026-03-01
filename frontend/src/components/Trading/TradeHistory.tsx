import { useState, useEffect } from 'react'
import { getTradeHistory, syncTradeHistory } from '../../services/api'
import type { Trade } from '../../types'

function toSeoulTime(isoStr: string): string {
  const s = isoStr.endsWith('Z') || isoStr.includes('+') ? isoStr : isoStr + 'Z'
  return new Date(s).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' })
}

export default function TradeHistory() {
  const [trades, setTrades] = useState<Trade[]>([])
  const [totalPnl, setTotalPnl] = useState(0)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(0)
  const [filterSide, setFilterSide] = useState<string>('')
  const [fromDate, setFromDate] = useState<string>('')
  const [syncing, setSyncing] = useState(false)
  const [syncMsg, setSyncMsg] = useState<string>('')
  const limit = 20

  const fetchTrades = async () => {
    setLoading(true)
    try {
      const res = await getTradeHistory({
        limit,
        offset: page * limit,
        side: filterSide || undefined,
        from_date: fromDate || undefined,
      })
      setTrades(res.data.trades || [])
      setTotalPnl((res.data as any).total_realized_pnl || 0)
    } catch {
      setTrades([])
    } finally {
      setLoading(false)
    }
  }

  const handleSync = async () => {
    if (!fromDate) {
      setPage(0)
      fetchTrades()
      return
    }
    setSyncing(true)
    setSyncMsg('')
    try {
      const res = await syncTradeHistory(fromDate)
      const d = res.data
      setSyncMsg(`동기화 완료: ${d.synced}건 추가, ${d.skipped}건 기존, 업비트 ${d.total_from_upbit}건 조회`)
      setPage(0)
      await fetchTrades()
    } catch {
      setSyncMsg('업비트 동기화 실패')
    } finally {
      setSyncing(false)
      setTimeout(() => setSyncMsg(''), 5000)
    }
  }

  useEffect(() => {
    fetchTrades()
  }, [page, filterSide])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">거래 내역</h2>
          <p className="text-gray-400 text-sm mt-1">자동 매매 거래 기록</p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <input
            type="datetime-local"
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
            className="input-field text-sm"
          />
          <button
            onClick={handleSync}
            disabled={syncing || loading}
            className="btn-primary text-sm whitespace-nowrap"
          >
            {syncing ? '동기화 중...' : fromDate ? '업비트 동기화' : '새로고침'}
          </button>
          <select
            value={filterSide}
            onChange={(e) => { setFilterSide(e.target.value); setPage(0) }}
            className="input-field text-sm"
          >
            <option value="">전체</option>
            <option value="buy">매수</option>
            <option value="sell">매도</option>
          </select>
          {syncMsg && (
            <span className="text-xs text-sky-400">{syncMsg}</span>
          )}
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
                    <th className="text-right py-3 px-2">매수금액</th>
                    <th className="text-right py-3 px-2">매도금액</th>
                    <th className="text-right py-3 px-2">수수료</th>
                    <th className="text-right py-3 px-2">수량</th>
                    <th className="text-left py-3 px-2">사유</th>
                  </tr>
                </thead>
                <tbody>
                  {trades.map((trade) => (
                    <tr key={trade.id} className="border-b border-gray-700/50 hover:bg-gray-700/30">
                      <td className="py-2.5 px-2 text-xs text-gray-400">
                        {toSeoulTime(trade.created_at)}
                      </td>
                      <td className="py-2.5 px-2">
                        <span className={trade.side === 'buy' ? 'badge-buy' : 'badge-sell'}>
                          {trade.side === 'buy' ? '매수' : '매도'}
                        </span>
                      </td>
                      <td className="py-2.5 px-2 font-mono text-primary-400">{trade.symbol}</td>
                      <td className="py-2.5 px-2 text-right">
                        {trade.side === 'buy'
                          ? Math.round(trade.amount_krw).toLocaleString()
                          : <span className="text-gray-500">-</span>
                        }
                      </td>
                      <td className={`py-2.5 px-2 text-right font-semibold ${
                        trade.side === 'sell'
                          ? (trade.pnl != null && trade.pnl >= 0 ? 'text-profit' : 'text-loss')
                          : ''
                      }`}>
                        {trade.side === 'sell'
                          ? Math.round(trade.amount_krw).toLocaleString()
                          : <span className="text-gray-500 font-normal">-</span>
                        }
                      </td>
                      <td className="py-2.5 px-2 text-right text-xs text-gray-400">
                        {trade.fee_krw != null ? `${Math.round(trade.fee_krw).toLocaleString()}` : '-'}
                      </td>
                      <td className="py-2.5 px-2 text-right">{trade.quantity.toFixed(8)}</td>
                      <td className="py-2.5 px-2 text-xs text-gray-400 max-w-[300px] whitespace-normal break-words">
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
            <div className="flex items-center justify-end mt-4 pt-4 border-t border-gray-700">
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
