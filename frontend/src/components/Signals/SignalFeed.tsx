import { useState, useEffect } from 'react'
import { getSignals, getLatestSignals, triggerNewsCheck } from '../../services/api'
import type { Signal } from '../../types'

const SOURCE_ICONS: Record<string, string> = {
  news: '📰',
  twitter: '🐦',
  technical: '📊',
}

const ACTION_STYLES: Record<string, { color: string; label: string }> = {
  buy: { color: 'text-profit', label: '매수' },
  sell: { color: 'text-loss', label: '매도' },
  hold: { color: 'text-gray-400', label: '관망' },
}

export default function SignalFeed() {
  const [signals, setSignals] = useState<Signal[]>([])
  const [latestNews, setLatestNews] = useState<Signal[]>([])
  const [latestTwitter, setLatestTwitter] = useState<Signal[]>([])
  const [loading, setLoading] = useState(true)
  const [checking, setChecking] = useState(false)
  const [filterSource, setFilterSource] = useState<string>('')

  useEffect(() => {
    const fetch = async () => {
      try {
        const [sigRes, latestRes] = await Promise.all([
          getSignals({ limit: 50, source: filterSource || undefined }),
          getLatestSignals(),
        ])
        setSignals(sigRes.data.signals || [])
        setLatestNews(latestRes.data.news || [])
        setLatestTwitter(latestRes.data.twitter || [])
      } catch {
        // 연결 안 됨
      } finally {
        setLoading(false)
      }
    }
    fetch()
    const interval = setInterval(fetch, 15000)
    return () => clearInterval(interval)
  }, [filterSource])

  const handleManualCheck = async () => {
    setChecking(true)
    try {
      await triggerNewsCheck()
      // 리프레시
      const res = await getLatestSignals()
      setLatestNews(res.data.news || [])
    } catch {
      // error
    } finally {
      setChecking(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">시그널 피드</h2>
          <p className="text-gray-400 text-sm mt-1">뉴스/트위터 모니터링 시그널</p>
        </div>
        <div className="flex gap-2">
          <select
            value={filterSource}
            onChange={(e) => setFilterSource(e.target.value)}
            className="input-field text-sm"
          >
            <option value="">전체</option>
            <option value="news">뉴스</option>
            <option value="twitter">트위터</option>
            <option value="technical">기술적</option>
          </select>
          <button onClick={handleManualCheck} disabled={checking} className="btn-primary text-sm">
            {checking ? '확인 중...' : '뉴스 수동 확인'}
          </button>
        </div>
      </div>

      {/* 최신 시그널 요약 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card">
          <h3 className="text-sm font-semibold text-gray-400 mb-3">📰 최신 뉴스 시그널</h3>
          {latestNews.length > 0 ? (
            <div className="space-y-2">
              {latestNews.slice(0, 5).map((s, i) => (
                <SignalItem key={i} signal={s} />
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-sm">최근 뉴스 시그널이 없습니다.</p>
          )}
        </div>
        <div className="card">
          <h3 className="text-sm font-semibold text-gray-400 mb-3">🐦 최신 트위터 시그널</h3>
          {latestTwitter.length > 0 ? (
            <div className="space-y-2">
              {latestTwitter.slice(0, 5).map((s, i) => (
                <SignalItem key={i} signal={s} />
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-sm">최근 트위터 시그널이 없습니다.</p>
          )}
        </div>
      </div>

      {/* 시그널 히스토리 */}
      <div className="card">
        <h3 className="text-lg font-semibold mb-4">시그널 기록</h3>
        {loading ? (
          <p className="text-gray-500">로딩 중...</p>
        ) : signals.length > 0 ? (
          <div className="space-y-2">
            {signals.map((s) => (
              <SignalItem key={s.id} signal={s} showTime />
            ))}
          </div>
        ) : (
          <p className="text-gray-500 text-sm">시그널 기록이 없습니다.</p>
        )}
      </div>
    </div>
  )
}

function SignalItem({ signal, showTime = false }: { signal: Signal; showTime?: boolean }) {
  const icon = SOURCE_ICONS[signal.source] || '❓'
  const action = ACTION_STYLES[signal.action] || ACTION_STYLES.hold

  return (
    <div className="flex items-start gap-3 py-2 border-b border-gray-700/50 last:border-0">
      <span className="text-lg">{icon}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className={`text-sm font-semibold ${action.color}`}>
            {action.label}
          </span>
          {signal.symbol && (
            <span className="font-mono text-xs text-primary-400">{signal.symbol}</span>
          )}
          <span className="text-xs text-gray-500">
            신뢰도: {(signal.confidence * 100).toFixed(0)}%
          </span>
          {signal.acted_on && (
            <span className="badge bg-yellow-900 text-yellow-300">실행됨</span>
          )}
        </div>
        <p className="text-sm text-gray-300 mt-0.5 truncate">{signal.summary}</p>
        {showTime && signal.created_at && (
          <p className="text-xs text-gray-500 mt-0.5">
            {new Date(signal.created_at).toLocaleString('ko-KR')}
          </p>
        )}
      </div>
    </div>
  )
}
