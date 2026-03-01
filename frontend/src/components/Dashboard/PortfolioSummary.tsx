import { useState, useEffect, useMemo } from 'react'
import { getPositions } from '../../services/api'
import { usePrices } from '../../contexts/PriceContext'
import type { Position, BotPosition } from '../../types'

const STORAGE_KEY = 'bot_start_amount'

export default function PortfolioSummary() {
  const [positions, setPositions] = useState<Position[]>([])
  const [botPositions, setBotPositions] = useState<BotPosition[]>([])
  const [krwBalance, setKrwBalance] = useState(0)
  const [maxPositions, setMaxPositions] = useState(5)
  const [loading, setLoading] = useState(true)
  const [startAmount, setStartAmount] = useState<string>(() => localStorage.getItem(STORAGE_KEY) || '')
  const { prices } = usePrices()

  useEffect(() => {
    const fetchPositions = async () => {
      try {
        const res = await getPositions()
        setPositions(res.data.positions || [])
        setKrwBalance(res.data.krw_balance || 0)
        setBotPositions(res.data.bot_positions || [])
        setMaxPositions(res.data.max_positions || 5)
      } catch {
        // 연결 안 됨
      } finally {
        setLoading(false)
      }
    }
    fetchPositions()
    const interval = setInterval(fetchPositions, 30000)
    return () => clearInterval(interval)
  }, [])

  // WebSocket 실시간 가격을 반영한 전체 포지션
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

  // WebSocket 실시간 가격을 반영한 봇 포지션 (봇 매수가 기준 PnL)
  const liveBotPositions = useMemo(() => {
    return botPositions.map((bp) => {
      const livePrice = prices[bp.symbol]
      if (livePrice && livePrice > 0) {
        const bot_pnl_pct = bp.bot_avg_price > 0
          ? ((livePrice - bp.bot_avg_price) / bp.bot_avg_price) * 100
          : 0
        return {
          ...bp,
          current_price: livePrice,
          bot_pnl_pct,
          bot_value: livePrice * bp.bot_quantity,
          bot_pnl: (livePrice - bp.bot_avg_price) * bp.bot_quantity,
        }
      }
      return bp
    })
  }, [botPositions, prices])

  const botPositionValue = useMemo(
    () => liveBotPositions.reduce((sum, bp) => sum + bp.bot_value, 0),
    [liveBotPositions]
  )

  const startAmountNum = parseFloat(startAmount) || 0

  const handleStartAmountChange = (val: string) => {
    setStartAmount(val)
    localStorage.setItem(STORAGE_KEY, val)
  }

  const realizedPnl = (krwBalance + botPositionValue) - startAmountNum

  const totalValue = useMemo(() => {
    const posValue = livePositions.reduce(
      (sum, p) => sum + p.current_price * p.quantity, 0
    )
    return krwBalance + posValue
  }, [livePositions, krwBalance])

  return (
    <div className="space-y-4">
      {/* 상단: 봇 매매 포트폴리오 */}
      <div className="card">
        <div className="flex items-center gap-2 mb-4">
          <h3 className="text-lg font-semibold">매매 포트폴리오</h3>
          <span className="text-sm text-gray-400">
            ({liveBotPositions.length}/{maxPositions})
          </span>
        </div>
        {loading ? (
          <p className="text-gray-500">로딩 중...</p>
        ) : (
          <>
            <div className="grid grid-cols-3 gap-4 mb-4">
              <div>
                <p className="text-sm text-gray-400">현금 잔고</p>
                <p className="text-xl font-bold">{krwBalance.toLocaleString(undefined, { maximumFractionDigits: 0 })} KRW</p>
              </div>
              <div>
                <p className="text-sm text-gray-400 mb-1">시작 금액</p>
                <input
                  type="text"
                  inputMode="numeric"
                  value={startAmount}
                  onChange={(e) => {
                    const v = e.target.value.replace(/[^0-9]/g, '')
                    handleStartAmountChange(v)
                  }}
                  placeholder="시작 금액 입력"
                  className="input-field text-sm w-full"
                />
              </div>
              <div>
                <p className="text-sm text-gray-400">실현 수익</p>
                <p className={`text-xl font-bold ${startAmountNum === 0 ? 'text-gray-500' : realizedPnl >= 0 ? 'text-profit' : 'text-loss'}`}>
                  {startAmountNum === 0
                    ? '-'
                    : `${realizedPnl >= 0 ? '+' : ''}${Math.round(realizedPnl).toLocaleString()} KRW`
                  }
                </p>
              </div>
            </div>
            {liveBotPositions.length > 0 ? (
              <BotPositionTable positions={liveBotPositions} />
            ) : (
              <p className="text-gray-500 text-sm">매매 중인 코인이 없습니다.</p>
            )}
          </>
        )}
      </div>

      {/* 하단: 전체 자산 */}
      <div className="card">
        <h3 className="text-lg font-semibold mb-4">전체 자산</h3>
        {loading ? (
          <p className="text-gray-500">로딩 중...</p>
        ) : (
          <>
            <div className="mb-4">
              <p className="text-sm text-gray-400">총 자산</p>
              <p className="text-xl font-bold">{totalValue.toLocaleString(undefined, { maximumFractionDigits: 0 })} KRW</p>
            </div>
            {livePositions.length > 0 ? (
              <PositionTable positions={livePositions} />
            ) : (
              <p className="text-gray-500 text-sm">보유 중인 포지션이 없습니다.</p>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function BotPositionTable({ positions }: { positions: BotPosition[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-gray-400 border-b border-gray-700">
            <th className="text-left py-2">종목</th>
            <th className="text-right py-2">평가금액</th>
            <th className="text-right py-2">수량</th>
            <th className="text-right py-2">매수가</th>
            <th className="text-right py-2">현재가</th>
            <th className="text-right py-2">수익률</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((bp) => (
            <tr key={bp.symbol} className="border-b border-gray-700/50">
              <td className="py-2 font-mono text-primary-400">{bp.symbol}</td>
              <td className="text-right py-2">{Math.round(bp.bot_value).toLocaleString()}</td>
              <td className="text-right py-2">{bp.bot_quantity.toFixed(8)}</td>
              <td className="text-right py-2">{bp.bot_avg_price.toLocaleString()}</td>
              <td className="text-right py-2">{bp.current_price.toLocaleString()}</td>
              <td className={`text-right py-2 font-semibold ${bp.bot_pnl_pct >= 0 ? 'text-profit' : 'text-loss'}`}>
                {bp.bot_pnl_pct >= 0 ? '+' : ''}{bp.bot_pnl_pct.toFixed(2)}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function PositionTable({ positions }: { positions: Position[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-gray-400 border-b border-gray-700">
            <th className="text-left py-2">종목</th>
            <th className="text-right py-2">평가금액</th>
            <th className="text-right py-2">수량</th>
            <th className="text-right py-2">평균가</th>
            <th className="text-right py-2">현재가</th>
            <th className="text-right py-2">수익률</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((pos) => (
            <tr key={pos.symbol} className="border-b border-gray-700/50">
              <td className="py-2 font-mono text-primary-400">{pos.symbol}</td>
              <td className="text-right py-2">{Math.round(pos.current_price * pos.quantity).toLocaleString()}</td>
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
  )
}
