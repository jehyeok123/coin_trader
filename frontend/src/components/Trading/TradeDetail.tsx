import type { Trade } from '../../types'
import ReactMarkdown from 'react-markdown'

interface Props {
  trade: Trade
  onClose: () => void
}

export default function TradeDetail({ trade, onClose }: Props) {
  const tradeMarkdown = `
## 거래 상세 정보

| 항목 | 내용 |
|------|------|
| **종목** | \`${trade.symbol}\` |
| **종류** | ${trade.side === 'buy' ? '🟢 매수' : '🔴 매도'} |
| **가격** | ${trade.price.toLocaleString()} KRW |
| **수량** | ${trade.quantity.toFixed(8)} |
| **금액** | ${trade.amount_krw.toLocaleString()} KRW |
| **시간** | ${new Date(trade.created_at).toLocaleString('ko-KR')} |
| **상태** | ${trade.status} |
| **시그널 출처** | ${trade.signal_source || '-'} |
${trade.pnl_pct != null ? `| **수익률** | ${trade.pnl_pct >= 0 ? '📈' : '📉'} ${trade.pnl_pct.toFixed(2)}% |` : ''}
${trade.pnl != null ? `| **실현 손익** | ${trade.pnl.toLocaleString()} KRW |` : ''}

### 매매 근거
${trade.reason || '기록된 매매 근거가 없습니다.'}
`

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div className="card max-w-lg w-full mx-4 max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">거래 상세</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-200">✕</button>
        </div>
        <div className="prose prose-invert prose-sm max-w-none">
          <ReactMarkdown>{tradeMarkdown}</ReactMarkdown>
        </div>
      </div>
    </div>
  )
}
