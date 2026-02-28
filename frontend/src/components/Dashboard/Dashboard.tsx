import { useState, useEffect } from 'react'
import { getTradingStatus, startTrading, stopTrading, getLatestSignals } from '../../services/api'
import PortfolioSummary from './PortfolioSummary'
import RecentTrades from './RecentTrades'
import type { SystemStatus, Signal } from '../../types'

const ACTION_STYLES: Record<string, { color: string; label: string }> = {
  buy: { color: 'text-emerald-400', label: '매수' },
  sell: { color: 'text-red-400', label: '매도' },
  hold: { color: 'text-gray-400', label: '관망' },
}

export default function Dashboard() {
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [latestNews, setLatestNews] = useState<Signal[]>([])
  const [latestTwitter, setLatestTwitter] = useState<Signal[]>([])

  const fetchStatus = async () => {
    try {
      const res = await getTradingStatus()
      setStatus(res.data)
    } catch {
      // API 연결 안 됨
    } finally {
      setLoading(false)
    }
  }

  const fetchSignals = async () => {
    try {
      const res = await getLatestSignals()
      setLatestNews(res.data.news || [])
      setLatestTwitter(res.data.twitter || [])
    } catch {
      // 연결 안 됨
    }
  }

  useEffect(() => {
    fetchStatus()
    fetchSignals()
    const statusInterval = setInterval(fetchStatus, 5000)
    const signalInterval = setInterval(fetchSignals, 15000)
    return () => {
      clearInterval(statusInterval)
      clearInterval(signalInterval)
    }
  }, [])

  const handleToggle = async () => {
    try {
      if (status?.engine?.running) {
        await stopTrading()
      } else {
        await startTrading()
      }
      await fetchStatus()
    } catch {
      // error
    }
  }

  const isRunning = status?.engine?.running ?? false

  return (
    <div className="space-y-6">
      {/* 상태 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">대시보드</h2>
          <p className="text-gray-400 text-sm mt-1">자동 매매 시스템 현황</p>
        </div>
        <button
          onClick={handleToggle}
          className={isRunning ? 'btn-danger' : 'btn-success'}
          disabled={loading}
        >
          {isRunning ? '매매 중지' : '매매 시작'}
        </button>
      </div>

      {/* 시스템 상태 카드 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatusCard
          title="매매 엔진"
          value={isRunning ? '실행 중' : '중지됨'}
          color={isRunning ? 'text-emerald-400' : 'text-red-400'}
          icon={isRunning ? '🟢' : '🔴'}
        />
        <StatusCard
          title="뉴스 모니터"
          value={status?.news_monitor?.running ? '감시 중' : '비활성'}
          color={status?.news_monitor?.running ? 'text-emerald-400' : 'text-gray-400'}
          icon="📰"
          sub={`${status?.news_monitor?.interval_minutes ?? 5}분 간격`}
        />
        <StatusCard
          title="트위터 모니터"
          value={status?.twitter_monitor?.running ? '감시 중' : '비활성'}
          color={status?.twitter_monitor?.running ? 'text-emerald-400' : 'text-gray-400'}
          icon="🐦"
          sub={`${status?.twitter_monitor?.accounts?.length ?? 0}개 계정`}
        />
        <StatusCard
          title="보유 포지션"
          value={`${status?.engine?.positions_count ?? 0}개`}
          color="text-primary-400"
          icon="📊"
        />
      </div>

      {/* 최신 뉴스 / 트위터 시그널 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card">
          <h3 className="text-sm font-semibold text-gray-400 mb-3">📰 최신 뉴스</h3>
          {latestNews.length > 0 ? (
            <div className="space-y-2">
              {latestNews.slice(0, 2).map((s, i) => (
                <SignalItem key={i} signal={s} />
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-sm">뉴스 시그널이 없습니다. 매매를 시작하면 자동 수집됩니다.</p>
          )}
        </div>
        <div className="card">
          <h3 className="text-sm font-semibold text-gray-400 mb-3">🐦 최신 트위터</h3>
          {latestTwitter.length > 0 ? (
            <div className="space-y-2">
              {latestTwitter.slice(0, 2).map((s, i) => (
                <SignalItem key={i} signal={s} />
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-sm">트위터 시그널이 없습니다. 매매를 시작하면 자동 수집됩니다.</p>
          )}
        </div>
      </div>

      {/* 포트폴리오 + 최근 거래 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <PortfolioSummary />
        <RecentTrades />
      </div>
    </div>
  )
}

function StatusCard({ title, value, color, icon, sub }: {
  title: string
  value: string
  color: string
  icon: string
  sub?: string
}) {
  return (
    <div className="card">
      <div className="flex items-center gap-3">
        <span className="text-2xl">{icon}</span>
        <div>
          <p className="text-sm text-gray-400">{title}</p>
          <p className={`text-lg font-semibold ${color}`}>{value}</p>
          {sub && <p className="text-xs text-gray-500">{sub}</p>}
        </div>
      </div>
    </div>
  )
}

function SignalItem({ signal }: { signal: Signal }) {
  const action = ACTION_STYLES[signal.action] || ACTION_STYLES.hold

  return (
    <div className="flex items-start gap-2 py-1.5 border-b border-gray-700/50 last:border-0">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-semibold ${action.color}`}>{action.label}</span>
          {signal.symbol && (
            <span className="font-mono text-xs text-primary-400">{signal.symbol}</span>
          )}
          <span className="text-xs text-gray-500">
            {(signal.confidence * 100).toFixed(0)}%
          </span>
        </div>
        <p className="text-sm text-gray-300 mt-0.5 truncate">{signal.summary}</p>
      </div>
    </div>
  )
}
