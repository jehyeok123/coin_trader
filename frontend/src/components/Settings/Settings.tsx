import { useState, useEffect } from 'react'
import { getSettings, updateSettings, testConnection } from '../../services/api'
import type { Settings } from '../../types'

interface ConnectionResult {
  upbit: {
    key_exists: boolean
    public_api: boolean
    authenticated: boolean
    error: string | null
    latency_ms: number | null
    auth_latency_ms?: number | null
  }
  gemini: {
    key_exists: boolean
    connected: boolean
    model: string | null
    error: string | null
    latency_ms: number | null
  }
  twitter: {
    reachable: boolean
    error: string | null
    latency_ms: number | null
    entries_count?: number
  }
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null)
  const [newsInterval, setNewsInterval] = useState(5)
  const [twitterAccounts, setTwitterAccounts] = useState('')
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [connectionResult, setConnectionResult] = useState<ConnectionResult | null>(null)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  useEffect(() => {
    getSettings().then((res) => {
      setSettings(res.data)
      setNewsInterval(res.data.news_interval_minutes || 5)
      setTwitterAccounts((res.data.twitter_accounts || []).join(', '))
    }).catch(() => {})
  }, [])

  const handleTestConnection = async () => {
    setTesting(true)
    setConnectionResult(null)
    try {
      const res = await testConnection()
      setConnectionResult(res.data)
    } catch {
      setMessage({ type: 'error', text: 'API 연결 테스트 실패 - 백엔드 서버에 연결할 수 없습니다.' })
    } finally {
      setTesting(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    setMessage(null)
    try {
      const accounts = twitterAccounts
        .split(',')
        .map((a) => a.trim())
        .filter(Boolean)
      await updateSettings({
        news_interval_minutes: newsInterval,
        twitter_accounts: accounts,
      })
      setMessage({ type: 'success', text: '설정이 저장되었습니다.' })
    } catch {
      setMessage({ type: 'error', text: '설정 저장 실패' })
    } finally {
      setSaving(false)
    }
  }

  if (!settings) return <p className="text-gray-500">로딩 중...</p>

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h2 className="text-2xl font-bold">설정</h2>
        <p className="text-gray-400 text-sm mt-1">시스템 설정 및 API 연결 상태</p>
      </div>

      {message && (
        <div className={`p-3 rounded-lg text-sm ${
          message.type === 'success' ? 'bg-emerald-900/50 text-emerald-300' : 'bg-red-900/50 text-red-300'
        }`}>
          {message.text}
        </div>
      )}

      {/* API 연결 상태 */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">API 연결 상태</h3>
          <button
            onClick={handleTestConnection}
            disabled={testing}
            className="btn-primary text-sm"
          >
            {testing ? '테스트 중...' : '연결 테스트'}
          </button>
        </div>

        {/* 기본 상태 (키 존재 여부) */}
        <div className="space-y-3">
          <div className="flex items-center justify-between py-2">
            <div className="flex items-center gap-3">
              <div className={`w-3 h-3 rounded-full ${settings.upbit_connected ? 'bg-emerald-400' : 'bg-red-400'}`} />
              <span>업비트 API 키</span>
            </div>
            <span className={`text-sm ${settings.upbit_connected ? 'text-emerald-400' : 'text-red-400'}`}>
              {settings.upbit_connected ? '설정됨' : '미설정'}
            </span>
          </div>
          <div className="flex items-center justify-between py-2">
            <div className="flex items-center gap-3">
              <div className={`w-3 h-3 rounded-full ${settings.gemini_connected ? 'bg-emerald-400' : 'bg-red-400'}`} />
              <span>Google Gemini API 키</span>
              {(settings as any).gemini_model && (
                <span className="text-xs bg-gray-700 text-gray-300 px-2 py-0.5 rounded">
                  {(settings as any).gemini_model}
                </span>
              )}
            </div>
            <span className={`text-sm ${settings.gemini_connected ? 'text-emerald-400' : 'text-red-400'}`}>
              {settings.gemini_connected ? '설정됨' : '미설정'}
            </span>
          </div>
        </div>

        {/* 실제 연결 테스트 결과 */}
        {connectionResult && (
          <div className="mt-4 pt-4 border-t border-gray-700 space-y-4">
            <h4 className="text-sm font-semibold text-gray-300">연결 테스트 결과</h4>

            {/* 업비트 */}
            <div className="bg-gray-900/50 rounded-lg p-3 space-y-2">
              <div className="flex items-center justify-between">
                <p className="font-medium text-sm">업비트</p>
                {connectionResult.upbit.latency_ms != null && (
                  <LatencyBadge ms={connectionResult.upbit.latency_ms} />
                )}
              </div>
              <div className="space-y-1 text-sm">
                <StatusRow label="공개 API (시세 조회)" ok={connectionResult.upbit.public_api} />
                <StatusRow label="API 키 설정" ok={connectionResult.upbit.key_exists} />
                <StatusRow label="인증 API (잔고 조회)" ok={connectionResult.upbit.authenticated} />
              </div>
              {connectionResult.upbit.auth_latency_ms != null && (
                <p className="text-xs text-gray-400">인증 API 응답: {connectionResult.upbit.auth_latency_ms}ms</p>
              )}
              {connectionResult.upbit.error && (
                <p className="text-xs text-red-400 mt-1">{connectionResult.upbit.error}</p>
              )}
            </div>

            {/* 트위터 RSS */}
            <div className="bg-gray-900/50 rounded-lg p-3 space-y-2">
              <div className="flex items-center justify-between">
                <p className="font-medium text-sm">트위터 (RSS/Nitter)</p>
                {connectionResult.twitter.latency_ms != null && (
                  <LatencyBadge ms={connectionResult.twitter.latency_ms} />
                )}
              </div>
              <div className="space-y-1 text-sm">
                <StatusRow label="RSS 피드 연결" ok={connectionResult.twitter.reachable} />
              </div>
              {connectionResult.twitter.entries_count != null && connectionResult.twitter.reachable && (
                <p className="text-xs text-gray-400">피드 항목: {connectionResult.twitter.entries_count}개</p>
              )}
              {connectionResult.twitter.error && (
                <p className="text-xs text-red-400 mt-1">{connectionResult.twitter.error}</p>
              )}
            </div>

            {/* Gemini */}
            <div className="bg-gray-900/50 rounded-lg p-3 space-y-2">
              <div className="flex items-center justify-between">
                <p className="font-medium text-sm">Google Gemini</p>
                {connectionResult.gemini.latency_ms != null && (
                  <LatencyBadge ms={connectionResult.gemini.latency_ms} />
                )}
              </div>
              <div className="space-y-1 text-sm">
                <StatusRow label="API 키 설정" ok={connectionResult.gemini.key_exists} />
                <StatusRow label="API 연결" ok={connectionResult.gemini.connected} />
              </div>
              {connectionResult.gemini.model && (
                <p className="text-xs text-emerald-400 mt-1">
                  활성 모델: <span className="font-mono">{connectionResult.gemini.model}</span>
                </p>
              )}
              {connectionResult.gemini.error && (
                <p className="text-xs text-red-400 mt-1">{connectionResult.gemini.error}</p>
              )}
            </div>
          </div>
        )}

        <p className="text-xs text-gray-500 mt-3">
          API 키는 프로젝트 루트의 <code className="text-primary-400">.env</code> 파일에서 설정합니다.
        </p>
      </div>

      {/* 뉴스 모니터링 설정 */}
      <div className="card">
        <h3 className="text-lg font-semibold mb-4">뉴스 모니터링</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">검색 간격 (분)</label>
            <input
              type="number"
              value={newsInterval}
              onChange={(e) => setNewsInterval(parseInt(e.target.value) || 5)}
              min={1}
              max={60}
              className="input-field w-full"
            />
            <p className="text-xs text-gray-500 mt-1">
              Gemini API를 통해 뉴스를 검색하는 간격입니다. (기본: 5분)
            </p>
          </div>
        </div>
      </div>

      {/* 트위터 모니터링 설정 */}
      <div className="card">
        <h3 className="text-lg font-semibold mb-4">트위터(X) 모니터링</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">감시 계정 (쉼표로 구분)</label>
            <input
              type="text"
              value={twitterAccounts}
              onChange={(e) => setTwitterAccounts(e.target.value)}
              placeholder="elonmusk, VitalikButerin"
              className="input-field w-full"
            />
            <p className="text-xs text-gray-500 mt-1">
              RSS/Nitter를 통해 폴링합니다. @ 기호 없이 입력하세요.
            </p>
          </div>
        </div>
      </div>

      {/* 저장 버튼 */}
      <div className="flex justify-end">
        <button onClick={handleSave} disabled={saving} className="btn-primary">
          {saving ? '저장 중...' : '설정 저장'}
        </button>
      </div>
    </div>
  )
}

function StatusRow({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <span className={ok ? 'text-emerald-400' : 'text-red-400'}>
        {ok ? '✓' : '✗'}
      </span>
      <span className="text-gray-300">{label}</span>
      <span className={`ml-auto text-xs ${ok ? 'text-emerald-400' : 'text-red-400'}`}>
        {ok ? '정상' : '실패'}
      </span>
    </div>
  )
}

function LatencyBadge({ ms }: { ms: number }) {
  const color = ms < 500 ? 'text-emerald-400' : ms < 2000 ? 'text-yellow-400' : 'text-red-400'
  return (
    <span className={`text-xs font-mono ${color}`}>
      {ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`}
    </span>
  )
}
