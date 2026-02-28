import type { Signal } from '../../types'
import ReactMarkdown from 'react-markdown'

interface Props {
  signal: Signal
  onClose: () => void
}

export default function SignalDetail({ signal, onClose }: Props) {
  const md = `
## 시그널 상세 정보

| 항목 | 내용 |
|------|------|
| **출처** | ${signal.source === 'news' ? '📰 뉴스' : signal.source === 'twitter' ? '🐦 트위터' : '📊 기술적'} |
| **액션** | ${signal.action === 'buy' ? '🟢 매수' : signal.action === 'sell' ? '🔴 매도' : '⚪ 관망'} |
| **종목** | \`${signal.symbol || 'N/A'}\` |
| **신뢰도** | ${(signal.confidence * 100).toFixed(0)}% |
| **시간** | ${new Date(signal.created_at).toLocaleString('ko-KR')} |
| **실행 여부** | ${signal.acted_on ? '✅ 실행됨' : '⬜ 미실행'} |

### 요약
${signal.summary || '요약 없음'}
`

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div className="card max-w-lg w-full mx-4" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">시그널 상세</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-200">✕</button>
        </div>
        <div className="prose prose-invert prose-sm max-w-none">
          <ReactMarkdown>{md}</ReactMarkdown>
        </div>
      </div>
    </div>
  )
}
