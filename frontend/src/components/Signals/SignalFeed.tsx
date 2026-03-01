import { useState, useEffect } from 'react'
import { getSignals, getLatestSignals, triggerNewsCheck, getTradingStatus } from '../../services/api'
import type { Signal, SystemStatus } from '../../types'

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

function formatKoTime(isoStr: string): string {
  // DB는 UTC naive datetime 저장 - Z 추가하여 UTC로 해석 후 KST 변환
  const s = isoStr.endsWith('Z') || isoStr.includes('+') ? isoStr : isoStr + 'Z'
  const d = new Date(s)
  const kst = new Date(d.getTime() + 9 * 60 * 60 * 1000)
  const m = kst.getUTCMonth() + 1
  const day = kst.getUTCDate()
  const h = kst.getUTCHours().toString().padStart(2, '0')
  const min = kst.getUTCMinutes().toString().padStart(2, '0')
  return `${m}월 ${day}일 ${h}:${min}`
}

export default function SignalFeed() {
  const [signals, setSignals] = useState<Signal[]>([])
  const [latestNews, setLatestNews] = useState<Signal[]>([])
  const [latestTwitter, setLatestTwitter] = useState<Signal[]>([])
  const [loading, setLoading] = useState(true)
  const [checking, setChecking] = useState(false)
  const [filterSource, setFilterSource] = useState<string>('')
  const [status, setStatus] = useState<SystemStatus | null>(null)

  useEffect(() => {
    const fetchAll = async () => {
      // 각 API를 개별 호출 - 하나 실패해도 나머지는 정상 작동
      try {
        const statusRes = await getTradingStatus()
        setStatus(statusRes.data)
      } catch { /* 연결 안 됨 */ }

      try {
        const latestRes = await getLatestSignals()
        setLatestNews(latestRes.data.news || [])
        setLatestTwitter(latestRes.data.twitter || [])
      } catch { /* 연결 안 됨 */ }

      try {
        const sigRes = await getSignals({ limit: 50, source: filterSource || undefined })
        setSignals(sigRes.data.signals || [])
      } catch { /* 연결 안 됨 */ }

      setLoading(false)
    }
    fetchAll()
    const interval = setInterval(fetchAll, 15000)
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
          <div className="flex gap-4 mt-1 text-xs text-gray-500">
            <span>뉴스 마지막 확인: <span className="text-gray-300">
              {status?.news_monitor?.last_check_time
                ? formatKoTime(status.news_monitor.last_check_time)
                : '대기중'}
            </span></span>
          </div>
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

      {/* 시그널 히스토리 (테이블) */}
      <div className="card">
        <h3 className="text-lg font-semibold mb-4">시그널 기록</h3>
        {loading ? (
          <p className="text-gray-500">로딩 중...</p>
        ) : signals.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-400 border-b border-gray-700">
                  <th className="text-left py-3 px-2">시간</th>
                  <th className="text-left py-3 px-2">소스</th>
                  <th className="text-left py-3 px-2">판단</th>
                  <th className="text-left py-3 px-2">종목</th>
                  <th className="text-right py-3 px-2">신뢰도</th>
                  <th className="text-left py-3 px-2">요약</th>
                </tr>
              </thead>
              <tbody>
                {signals.map((s) => {
                  const action = ACTION_STYLES[s.action] || ACTION_STYLES.hold
                  const icon = SOURCE_ICONS[s.source] || '❓'
                  return (
                    <tr key={s.id} className="border-b border-gray-700/50 hover:bg-gray-700/30">
                      <td className="py-2.5 px-2 text-xs text-gray-400 whitespace-nowrap">
                        {s.created_at ? formatKoTime(s.created_at) : '-'}
                      </td>
                      <td className="py-2.5 px-2 whitespace-nowrap">
                        <span>{icon} {s.source}</span>
                      </td>
                      <td className="py-2.5 px-2">
                        <span className={`font-semibold ${action.color}`}>{action.label}</span>
                      </td>
                      <td className="py-2.5 px-2 font-mono text-primary-400">
                        {s.symbol || '-'}
                      </td>
                      <td className="py-2.5 px-2 text-right">
                        {(s.confidence * 100).toFixed(0)}%
                      </td>
                      <td className="py-2.5 px-2 text-gray-300 max-w-[400px] whitespace-normal break-words">
                        {s.summary}
                        {s.url && (
                          <a
                            href={s.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="ml-2 text-xs text-sky-400 hover:text-sky-300 hover:underline"
                          >
                            원문 &#x2197;
                          </a>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
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
        <p className="text-sm text-gray-300 mt-0.5">{signal.summary}</p>
        <div className="flex items-center gap-2 mt-0.5">
          {signal.url && (
            <a
              href={signal.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-sky-400 hover:text-sky-300 hover:underline"
            >
              원문 보기 &#x2197;
            </a>
          )}
          {showTime && signal.created_at && (
            <span className="text-xs text-gray-500">
              {new Date(signal.created_at).toLocaleString('ko-KR')}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
