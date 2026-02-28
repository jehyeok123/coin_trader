import { useState, useEffect } from 'react'
import { getRules, updateRules, resetRules } from '../../services/api'
import type { TradingRules } from '../../types'

export default function RuleEditor() {
  const [rules, setRules] = useState<TradingRules | null>(null)
  const [jsonText, setJsonText] = useState('')
  const [editMode, setEditMode] = useState<'form' | 'json'>('form')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  useEffect(() => {
    getRules().then((res) => {
      setRules(res.data.rules)
      setJsonText(JSON.stringify(res.data.rules, null, 2))
    }).catch(() => {})
  }, [])

  const handleSave = async () => {
    setSaving(true)
    setMessage(null)
    try {
      let rulesData: TradingRules
      if (editMode === 'json') {
        rulesData = JSON.parse(jsonText)
      } else {
        rulesData = rules!
      }
      await updateRules(rulesData)
      setRules(rulesData)
      setJsonText(JSON.stringify(rulesData, null, 2))
      setMessage({ type: 'success', text: '매매 규칙이 저장되었습니다.' })
    } catch (err) {
      setMessage({ type: 'error', text: '저장 실패: JSON 형식을 확인해주세요.' })
    } finally {
      setSaving(false)
    }
  }

  const handleReset = async () => {
    if (!confirm('기본 규칙으로 초기화하시겠습니까?')) return
    try {
      const res = await resetRules()
      setRules(res.data.rules)
      setJsonText(JSON.stringify(res.data.rules, null, 2))
      setMessage({ type: 'success', text: '기본 규칙으로 초기화되었습니다.' })
    } catch {
      setMessage({ type: 'error', text: '초기화 실패' })
    }
  }

  const updateField = (path: string, value: unknown) => {
    if (!rules) return
    const newRules = JSON.parse(JSON.stringify(rules))
    const keys = path.split('.')
    let obj = newRules
    for (let i = 0; i < keys.length - 1; i++) {
      obj = obj[keys[i]]
    }
    obj[keys[keys.length - 1]] = value
    setRules(newRules)
    setJsonText(JSON.stringify(newRules, null, 2))
  }

  if (!rules) return <p className="text-gray-500">로딩 중...</p>

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">매매 규칙</h2>
          <p className="text-gray-400 text-sm mt-1">자동 매매 조건을 설정합니다</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setEditMode(editMode === 'form' ? 'json' : 'form')} className="btn-outline text-sm">
            {editMode === 'form' ? 'JSON 편집' : '폼 편집'}
          </button>
          <button onClick={handleReset} className="btn-outline text-sm">초기화</button>
          <button onClick={handleSave} disabled={saving} className="btn-primary text-sm">
            {saving ? '저장 중...' : '저장'}
          </button>
        </div>
      </div>

      {message && (
        <div className={`p-3 rounded-lg text-sm ${
          message.type === 'success' ? 'bg-emerald-900/50 text-emerald-300' : 'bg-red-900/50 text-red-300'
        }`}>
          {message.text}
        </div>
      )}

      {editMode === 'json' ? (
        <div className="card">
          <textarea
            value={jsonText}
            onChange={(e) => setJsonText(e.target.value)}
            className="w-full h-[600px] bg-gray-900 text-gray-100 font-mono text-sm p-4 rounded-lg border border-gray-700 focus:border-primary-500 focus:outline-none resize-none"
            spellCheck={false}
          />
        </div>
      ) : (
        <div className="space-y-4">
          {/* 매매 기본 설정 */}
          <div className="card">
            <h3 className="text-lg font-semibold mb-4">매매 기본 설정</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <NumberField label="손절 (%)" value={rules.trading.stop_loss_pct}
                onChange={(v) => updateField('trading.stop_loss_pct', v)} />
              <NumberField label="익절 (%)" value={rules.trading.take_profit_pct}
                onChange={(v) => updateField('trading.take_profit_pct', v)} />
              <NumberField label="트레일링 스톱 (%)" value={rules.trading.trailing_stop_pct}
                onChange={(v) => updateField('trading.trailing_stop_pct', v)} />
              <NumberField label="최대 포지션 크기 (%)" value={rules.trading.max_position_size_pct}
                onChange={(v) => updateField('trading.max_position_size_pct', v)} />
              <NumberField label="최대 동시 포지션 수" value={rules.trading.max_concurrent_positions}
                onChange={(v) => updateField('trading.max_concurrent_positions', Math.floor(v))} />
              <NumberField label="최소 주문 금액 (KRW)" value={rules.trading.min_order_amount_krw}
                onChange={(v) => updateField('trading.min_order_amount_krw', v)} />
              <NumberField label="쿨다운 (초)" value={rules.trading.cooldown_seconds}
                onChange={(v) => updateField('trading.cooldown_seconds', Math.floor(v))} />
              <div>
                <label className="block text-xs text-gray-400 mb-1">매도 잠금 날짜</label>
                <input
                  type="date"
                  value={rules.trading.sell_lock_before_date || ''}
                  onChange={(e) => updateField('trading.sell_lock_before_date', e.target.value)}
                  className="input-field w-full text-sm"
                />
                <p className="text-xs text-gray-500 mt-1">이 날짜 이전에 매수한 코인은 자동 매도하지 않습니다</p>
              </div>
            </div>
          </div>

          {/* 지표 설정 */}
          <div className="card">
            <h3 className="text-lg font-semibold mb-4">기술적 지표</h3>
            {Object.entries(rules.indicators).map(([key, config]) => (
              <div key={key} className="mb-4 p-3 bg-gray-900/50 rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium capitalize">{key.replace(/_/g, ' ')}</span>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={(config as Record<string, unknown>).enabled as boolean}
                      onChange={(e) => updateField(`indicators.${key}.enabled`, e.target.checked)}
                      className="rounded"
                    />
                    <span className="text-sm text-gray-400">활성화</span>
                  </label>
                </div>
                {Boolean((config as Record<string, unknown>).enabled) && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-2">
                    {Object.entries(config as Record<string, unknown>)
                      .filter(([k]) => k !== 'enabled')
                      .map(([k, v]) => (
                        <NumberField
                          key={k}
                          label={k.replace(/_/g, ' ')}
                          value={v as number}
                          onChange={(val) => updateField(`indicators.${key}.${k}`, val)}
                        />
                      ))}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* 인터럽트 설정 */}
          <div className="card">
            <h3 className="text-lg font-semibold mb-4">인터럽트 시그널</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={rules.interrupt.enabled}
                  onChange={(e) => updateField('interrupt.enabled', e.target.checked)}
                />
                <span className="text-sm">인터럽트 활성화</span>
              </div>
              <NumberField label="뉴스 신뢰도 임계값" value={rules.interrupt.news_confidence_threshold}
                onChange={(v) => updateField('interrupt.news_confidence_threshold', v)} />
              <NumberField label="트위터 신뢰도 임계값" value={rules.interrupt.twitter_confidence_threshold}
                onChange={(v) => updateField('interrupt.twitter_confidence_threshold', v)} />
              <NumberField label="인터럽트 최대 포지션 (%)" value={rules.interrupt.max_interrupt_position_pct}
                onChange={(v) => updateField('interrupt.max_interrupt_position_pct', v)} />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function NumberField({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <div>
      <label className="block text-xs text-gray-400 mb-1">{label}</label>
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
        step="any"
        className="input-field w-full text-sm"
      />
    </div>
  )
}
