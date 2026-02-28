import { useState, useEffect, useMemo } from 'react'
import { getPositions } from '../../services/api'
import { usePrices } from '../../contexts/PriceContext'
import type { Position } from '../../types'

export default function PortfolioSummary() {
  const [positions, setPositions] = useState<Position[]>([])
  const [krwBalance, setKrwBalance] = useState(0)
  const [loading, setLoading] = useState(true)
  const { prices } = usePrices()

  useEffect(() => {
    const fetchPositions = async () => {
      try {
        const res = await getPositions()
        setPositions(res.data.positions || [])
        setKrwBalance(res.data.krw_balance || 0)
      } catch {
        // 연결 안 됨
      } finally {
        setLoading(false)
      }
    }
    fetchPositions()
    // 잔고/포지션 목록은 30초마다 갱신 (가격은 WebSocket으로 실시간)
    const interval = setInterval(fetchPositions, 30000)
    return () => clearInterval(interval)
  }, [])

  // WebSocket 실시간 가격을 반영한 포지션
  const livePositions = useMemo(() => {
    return positions.map((pos) => {
      const livePrice = prices[pos.symbol]
      if (livePrice && livePrice > 0) {
        const pnl_pct = pos.avg_price > 0
          ? ((livePrice - pos.avg_price) / pos.avg_price) * 100
          : 0
        return { ...pos, current_price: livePrice, pnl_pct }
      }
      return pos
    })
  }, [positions, prices])

  const totalValue = useMemo(() => {
    const posValue = livePositions.reduce(
      (sum, p) => sum + p.current_price * p.quantity, 0
    )
    return krwBalance + posValue
  }, [livePositions, krwBalance])

  return (
    <div className="card">
      <h3 className="text-lg font-semibold mb-4">포트폴리오</h3>
      {loading ? (
        <p className="text-gray-500">로딩 중...</p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <p className="text-sm text-gray-400">총 자산</p>
              <p className="text-xl font-bold">{totalValue.toLocaleString(undefined, { maximumFractionDigits: 0 })} KRW</p>
            </div>
            <div>
              <p className="text-sm text-gray-400">현금 잔고</p>
              <p className="text-xl font-bold">{krwBalance.toLocaleString(undefined, { maximumFractionDigits: 0 })} KRW</p>
            </div>
          </div>
          {livePositions.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-400 border-b border-gray-700">
                    <th className="text-left py-2">종목</th>
                    <th className="text-right py-2">수량</th>
                    <th className="text-right py-2">평균가</th>
                    <th className="text-right py-2">현재가</th>
                    <th className="text-right py-2">수익률</th>
                  </tr>
                </thead>
                <tbody>
                  {livePositions.map((pos) => (
                    <tr key={pos.symbol} className="border-b border-gray-700/50">
                      <td className="py-2 font-mono text-primary-400">{pos.symbol}</td>
                      <td className="text-right py-2">{pos.quantity.toFixed(8)}</td>
                      <td className="text-right py-2">{pos.avg_price.toLocaleString()}</td>
                      <td className="text-right py-2">{pos.current_price.toLocaleString()}</td>
                      <td className={`text-right py-2 font-semibold ${pos.pnl_pct >= 0 ? 'text-profit' : 'text-loss'}`}>
                        {pos.pnl_pct >= 0 ? '+' : ''}{pos.pnl_pct.toFixed(2)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-gray-500 text-sm">보유 중인 포지션이 없습니다.</p>
          )}
        </>
      )}
    </div>
  )
}
