import { useState, useEffect } from 'react'
import { getTradingStatus, startTrading, stopTrading, getLatestSignals, getTargetCoins } from '../../services/api'
import PortfolioSummary from './PortfolioSummary'
import RecentTrades from './RecentTrades'
import type { SystemStatus, Signal, TargetCoin, EntryStatus } from '../../types'

const ACTION_STYLES: Record<string, { color: string; label: string }> = {
  buy: { color: 'text-emerald-400', label: '매수' },
  sell: { color: 'text-red-400', label: '매도' },
  hold: { color: 'text-gray-400', label: '관망' },
}

// 키워드 점수 사전 (gemini_analyzer.py SYSTEM_PROMPT 동일)
const COIN_KEYWORDS = {
  positive: [
    { keyword: 'Listing / List', score: '+5', note: '바이낸스/업비트/코인베이스 언급 시 +5 추가' },
    { keyword: 'Approved / Acquisition', score: '+4', note: '' },
    { keyword: 'Partnership / Mainnet Launch', score: '+3', note: '' },
    { keyword: 'Burn', score: '+2', note: '' },
  ],
  negative: [
    { keyword: 'Hack / Exploit / Delist / Bankrupt', score: '-5', note: '' },
    { keyword: 'SEC / Lawsuit / Sued', score: '-4', note: '' },
    { keyword: 'Delay / Halted', score: '-2', note: '' },
  ],
}

const MACRO_KEYWORDS = {
  positive: [
    { keyword: 'Rate Cut', score: '+5' },
    { keyword: 'Lower CPI', score: '+5' },
    { keyword: 'QE (Quantitative Easing)', score: '+5' },
    { keyword: 'Stimulus', score: '+5' },
  ],
  negative: [
    { keyword: 'Rate Hike', score: '-5' },
    { keyword: 'Higher CPI', score: '-5' },
    { keyword: 'War / Invasion / Missile', score: '-5' },
    { keyword: 'Recession / Emergency', score: '-5' },
  ],
}

function formatKRW(value: number): string {
  if (value >= 1_0000_0000_0000) return `${(value / 1_0000_0000_0000).toFixed(1)}조`
  if (value >= 1_0000_0000) return `${(value / 1_0000_0000).toFixed(0)}억`
  if (value >= 1_0000) return `${(value / 1_0000).toFixed(0)}만`
  return value.toLocaleString()
}

function formatPrice(value: number): string {
  if (value >= 1_000_000) return `${(value / 10000).toFixed(0)}만`
  return value.toLocaleString()
}

function formatKoTime(isoStr: string): string {
  const d = new Date(isoStr)
  // UTC → KST (+9h)
  const kst = new Date(d.getTime() + 9 * 60 * 60 * 1000)
  const m = kst.getUTCMonth() + 1
  const day = kst.getUTCDate()
  const h = kst.getUTCHours().toString().padStart(2, '0')
  const min = kst.getUTCMinutes().toString().padStart(2, '0')
  return `${m}월 ${day}일 ${h}:${min}`
}

export default function Dashboard() {
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [latestNews, setLatestNews] = useState<Signal[]>([])
  const [latestTwitter, setLatestTwitter] = useState<Signal[]>([])
  const [targetCoins, setTargetCoins] = useState<TargetCoin[]>([])
  const [showKeywords, setShowKeywords] = useState(false)
  const [cooldownSeconds, setCooldownSeconds] = useState(60)
  const [refreshIntervalSeconds, setRefreshIntervalSeconds] = useState(3600)
  const [rsiMin, setRsiMin] = useState(0)
  const [rsiMax, setRsiMax] = useState(0)

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

  const fetchTargetCoins = async () => {
    try {
      const res = await getTargetCoins()
      const coins = res.data.coins || []
      if (res.data.cooldown_seconds != null) setCooldownSeconds(res.data.cooldown_seconds)
      if (res.data.refresh_interval_seconds != null) setRefreshIntervalSeconds(res.data.refresh_interval_seconds)
      if (res.data.rsi_min != null) setRsiMin(res.data.rsi_min)
      if (res.data.rsi_max != null) setRsiMax(res.data.rsi_max)
      // 모든 코인의 거래대금이 계산 완료된 경우에만 업데이트 (첫 로딩은 예외)
      const allVolReady = coins.length > 0 && coins.every((c: TargetCoin) => c.acc_trade_price_1h > 0)
      if (allVolReady || targetCoins.length === 0) {
        setTargetCoins(coins)
      }
    } catch {
      // 연결 안 됨
    }
  }

  useEffect(() => {
    fetchStatus()
    fetchSignals()
    fetchTargetCoins()
    const statusInterval = setInterval(fetchStatus, 5000)
    const signalInterval = setInterval(fetchSignals, 15000)
    // 진입 스캔 간격으로 갱신 (최소 30초)
    const targetRefreshMs = Math.max(cooldownSeconds, 30) * 1000
    const targetInterval = setInterval(fetchTargetCoins, targetRefreshMs)
    return () => {
      clearInterval(statusInterval)
      clearInterval(signalInterval)
      clearInterval(targetInterval)
    }
  }, [cooldownSeconds])

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
  const entryPaused = status?.engine?.entry_paused ?? false
  const pauseRemaining = status?.engine?.entry_pause_remaining_seconds ?? 0

  return (
    <div className="space-y-6">
      {/* 킬스위치 경고 배너 */}
      {entryPaused && (
        <div className="bg-red-900/60 border border-red-500/50 rounded-lg p-4 flex items-center gap-3">
          <span className="text-2xl">&#x26A0;</span>
          <div>
            <p className="font-semibold text-red-300">킬 스위치 활성 - 진입 일시정지 중</p>
            <p className="text-sm text-red-400">
              잔여 시간: {Math.floor(pauseRemaining / 60)}분 {pauseRemaining % 60}초
              (포지션 모니터링은 정상 작동 중)
            </p>
          </div>
        </div>
      )}

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
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <StatusCard
          title="매매 엔진"
          value={isRunning ? '실행 중' : '중지됨'}
          color={isRunning ? 'text-emerald-400' : 'text-red-400'}
          icon={isRunning ? '&#x1F7E2;' : '&#x1F534;'}
        />
        <StatusCard
          title="뉴스 모니터"
          value={status?.news_monitor?.running ? '감시 중' : '비활성'}
          color={status?.news_monitor?.running ? 'text-emerald-400' : 'text-gray-400'}
          icon="&#x1F4F0;"
          sub={`${status?.news_monitor?.interval_seconds ?? 30}초 간격`}
        />
        <StatusCard
          title="보유 포지션"
          value={`${status?.engine?.positions_count ?? 0}개`}
          color="text-primary-400"
          icon="&#x1F4CA;"
        />
      </div>

      {/* 키워드 점수 사전 */}
      <div className="card">
        <button
          onClick={() => setShowKeywords(!showKeywords)}
          className="w-full flex items-center justify-between text-left"
        >
          <h3 className="text-sm font-semibold text-gray-400">Gemini 키워드 점수 사전</h3>
          <span className="text-gray-500 text-xs">{showKeywords ? '접기' : '펼치기'}</span>
        </button>

        {showKeywords && (
          <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* 코인 키워드 */}
            <div>
              <h4 className="text-xs font-medium text-gray-400 mb-2">코인별 키워드</h4>
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-gray-500">
                    <th className="text-left pb-1">키워드</th>
                    <th className="text-right pb-1">점수</th>
                  </tr>
                </thead>
                <tbody>
                  {COIN_KEYWORDS.positive.map((k) => (
                    <tr key={k.keyword} className="border-t border-gray-800">
                      <td className="py-1">
                        {k.keyword}
                        {k.note && <span className="text-gray-600 ml-1">({k.note})</span>}
                      </td>
                      <td className="text-right text-emerald-400 font-mono">{k.score}</td>
                    </tr>
                  ))}
                  {COIN_KEYWORDS.negative.map((k) => (
                    <tr key={k.keyword} className="border-t border-gray-800">
                      <td className="py-1">{k.keyword}</td>
                      <td className="text-right text-red-400 font-mono">{k.score}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* 매크로 키워드 */}
            <div>
              <h4 className="text-xs font-medium text-gray-400 mb-2">매크로(거시경제) 키워드</h4>
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-gray-500">
                    <th className="text-left pb-1">키워드</th>
                    <th className="text-right pb-1">점수</th>
                  </tr>
                </thead>
                <tbody>
                  {MACRO_KEYWORDS.positive.map((k) => (
                    <tr key={k.keyword} className="border-t border-gray-800">
                      <td className="py-1">{k.keyword}</td>
                      <td className="text-right text-emerald-400 font-mono">{k.score}</td>
                    </tr>
                  ))}
                  {MACRO_KEYWORDS.negative.map((k) => (
                    <tr key={k.keyword} className="border-t border-gray-800">
                      <td className="py-1">{k.keyword}</td>
                      <td className="text-right text-red-400 font-mono">{k.score}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-xs text-gray-600 mt-2">
                score &ge; 4: 매수 / score &le; -4: 매도(킬스위치)
              </p>
            </div>
          </div>
        )}
      </div>

      {/* 최신 뉴스 / 트위터 시그널 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-400">최신 뉴스</h3>
            {status?.news_monitor?.last_check_time && (
              <span className="text-xs text-gray-500">
                마지막 확인: {formatKoTime(status.news_monitor.last_check_time)}
              </span>
            )}
          </div>
          {latestNews.length > 0 ? (
            <div className="space-y-2">
              {latestNews.slice(0, 5).map((s, i) => (
                <SignalItem key={i} signal={s} />
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-sm">뉴스 시그널이 없습니다. 매매를 시작하면 자동 수집됩니다.</p>
          )}
        </div>
        <div className="card">
          <h3 className="text-sm font-semibold text-gray-400 mb-3">최신 트위터</h3>
          {latestTwitter.length > 0 ? (
            <div className="space-y-2">
              {latestTwitter.slice(0, 5).map((s, i) => (
                <SignalItem key={i} signal={s} />
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-sm">트위터 시그널이 없습니다. 매매를 시작하면 자동 수집됩니다.</p>
          )}
        </div>
      </div>

      {/* 매수 후보 코인 (타겟) 테이블 */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-gray-400">매수 후보 코인 (거래대금 Top {targetCoins.length})</h3>
          <div className="flex items-center gap-3 text-xs text-gray-600">
            <span>진입 스캔: {cooldownSeconds}초</span>
            <span>타겟 갱신: {refreshIntervalSeconds >= 3600 ? `${refreshIntervalSeconds / 3600}시간` : `${refreshIntervalSeconds}초`}</span>
          </div>
        </div>

        {targetCoins.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 text-xs border-b border-gray-700">
                  <th className="text-left py-2 w-10">#</th>
                  <th className="text-left py-2">코인</th>
                  <th className="text-right py-2">현재가</th>
                  <th className="text-right py-2">1h 거래대금</th>
                  <th className="text-right py-2">24h 등락</th>
                  <th className="text-center py-2">타겟</th>
                  <th className="text-left py-2 whitespace-nowrap">진입 조건 <span className="text-gray-600 font-normal">(P&gt;E20&gt;E200{rsiMin > 0 || rsiMax > 0 ? ` / ${rsiMin > 0 ? rsiMin : ''}\u2264RSI\u2264${rsiMax > 0 ? rsiMax : ''}` : ''})</span></th>
                </tr>
              </thead>
              <tbody>
                {targetCoins.map((coin) => {
                  const changeColor = coin.signed_change_rate > 0
                    ? 'text-emerald-400'
                    : coin.signed_change_rate < 0
                      ? 'text-red-400'
                      : 'text-gray-400'
                  return (
                    <tr key={coin.symbol} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                      <td className="py-2 text-gray-500">{coin.rank}</td>
                      <td className="py-2 font-mono font-medium text-white">
                        {coin.symbol.replace('KRW-', '')}
                      </td>
                      <td className="py-2 text-right font-mono">
                        {formatPrice(coin.trade_price)}
                      </td>
                      <td className="py-2 text-right font-mono text-yellow-400">
                        {formatKRW(coin.acc_trade_price_1h)}
                      </td>
                      <td className={`py-2 text-right font-mono ${changeColor}`}>
                        {coin.signed_change_rate > 0 ? '+' : ''}
                        {(coin.signed_change_rate * 100).toFixed(2)}%
                      </td>
                      <td className="py-2 text-center">
                        {coin.is_target ? (
                          <span className="text-xs px-1.5 py-0.5 rounded bg-emerald-900/50 text-emerald-300">ON</span>
                        ) : (
                          <span className="text-xs text-gray-600">-</span>
                        )}
                      </td>
                      <td className="py-2">
                        <EntryStatusDisplay status={coin.entry_status} rsiMin={rsiMin} rsiMax={rsiMax} />
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-gray-500 text-sm">타겟 코인 데이터를 불러오는 중...</p>
        )}
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
        <span className="text-2xl" dangerouslySetInnerHTML={{ __html: icon }} />
        <div>
          <p className="text-sm text-gray-400">{title}</p>
          <p className={`text-lg font-semibold ${color}`}>{value}</p>
          {sub && <p className="text-xs text-gray-500">{sub}</p>}
        </div>
      </div>
    </div>
  )
}

function EntryStatusDisplay({ status, rsiMin, rsiMax }: { status?: EntryStatus | null; rsiMin: number; rsiMax: number }) {
  if (!status) {
    return <span className="text-xs text-gray-600">-</span>
  }

  const price = status.current_price
  const ema200 = status.ema_200
  const ema20 = status.ema_20
  const rsi = status.rsi

  // indicators가 없으면 reasons 표시 (데이터 부족 등)
  if (ema200 == null && ema20 == null && rsi == null) {
    const reason = status.reasons?.[0] || '데이터 없음'
    return <span className="text-xs text-gray-500">{reason}</span>
  }

  // 조건 1: price > EMA20
  const priceAboveE20 = (price != null && ema20 != null) ? price > ema20 : null
  const ema20Gap = (ema20 && price) ? ((price - ema20) / ema20) * 100 : null

  // 조건 2: EMA20 > EMA200
  const e20AboveE200 = (ema20 != null && ema200 != null) ? ema20 > ema200 : null
  const ema200Gap = (ema200 && ema20) ? ((ema20 - ema200) / ema200) * 100 : null

  // 조건 3: RSI 범위 (rsiMin/rsiMax가 0이면 해당 바운드 비활성화)
  let rsiMet = true
  if (rsi != null) {
    if (rsiMin > 0 && rsi < rsiMin) rsiMet = false
    if (rsiMax > 0 && rsi > rsiMax) rsiMet = false
    // 둘 다 0이면 RSI 조건 없음 → 항상 충족
  }

  return (
    <div className="flex items-center gap-2 text-xs font-mono whitespace-nowrap">
      {ema20Gap != null && (
        <span className={priceAboveE20 ? 'text-emerald-400' : 'text-red-400'}>
          P&gt;E20 {ema20Gap >= 0 ? '+' : ''}{ema20Gap.toFixed(1)}%
        </span>
      )}
      {ema200Gap != null && (
        <span className={e20AboveE200 ? 'text-emerald-400' : 'text-red-400'}>
          E20&gt;E200 {ema200Gap >= 0 ? '+' : ''}{ema200Gap.toFixed(1)}%
        </span>
      )}
      {rsi != null && (
        <span className={rsiMet ? 'text-emerald-400' : 'text-red-400'}>
          RSI {rsi.toFixed(0)}
        </span>
      )}
    </div>
  )
}

function SignalItem({ signal }: { signal: Signal }) {
  const action = ACTION_STYLES[signal.action] || ACTION_STYLES.hold
  const timeStr = signal.created_at ? formatKoTime(signal.created_at) : ''

  return (
    <div className="flex items-start gap-2 py-1.5 border-b border-gray-700/50 last:border-0">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          {timeStr && <span className="text-xs text-gray-500">{timeStr}</span>}
          <span className={`text-xs font-semibold ${action.color}`}>{action.label}</span>
          {signal.symbol && (
            <span className="font-mono text-xs text-primary-400">{signal.symbol}</span>
          )}
          <span className="text-xs text-gray-500">
            {(signal.confidence * 100).toFixed(0)}%
          </span>
        </div>
        <p className="text-sm text-gray-300 mt-0.5">{signal.summary}</p>
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
      </div>
    </div>
  )
}
