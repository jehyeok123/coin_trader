import { useState, useEffect } from 'react'
import { getRules, updateRules, resetRules } from '../../services/api'
import type { TradingRules } from '../../types'

export default function RuleEditor() {
  const [rules, setRules] = useState<TradingRules | null>(null)
  const [jsonText, setJsonText] = useState('')
  const [editMode, setEditMode] = useState<'form' | 'json' | 'help'>('form')
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
          <p className="text-gray-400 text-sm mt-1">v{rules.version} - {rules.description}</p>
        </div>
        <div className="flex gap-2">
          {(['form', 'json', 'help'] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => setEditMode(mode)}
              className={editMode === mode ? 'btn-primary text-sm' : 'btn-outline text-sm'}
            >
              {{ form: '폼 편집', json: 'JSON 편집', help: '도움말' }[mode]}
            </button>
          ))}
          <button onClick={handleReset} className="btn-outline text-sm">초기화</button>
          {editMode !== 'help' && (
            <button onClick={handleSave} disabled={saving} className="btn-primary text-sm">
              {saving ? '저장 중...' : '저장'}
            </button>
          )}
        </div>
      </div>

      {message && (
        <div className={`p-3 rounded-lg text-sm ${
          message.type === 'success' ? 'bg-emerald-900/50 text-emerald-300' : 'bg-red-900/50 text-red-300'
        }`}>
          {message.text}
        </div>
      )}

      {editMode === 'help' ? (
        <HelpPanel />
      ) : editMode === 'json' ? (
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
          <Section title="매매 기본 설정">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <NumberField label="최대 포지션 크기 (%)" value={rules.trading.max_position_size_pct}
                onChange={(v) => updateField('trading.max_position_size_pct', v)} />
              <NumberField label="최대 동시 포지션 수" value={rules.trading.max_concurrent_positions}
                onChange={(v) => updateField('trading.max_concurrent_positions', Math.floor(v))} />
              <NumberField label="최소 주문 금액 (KRW)" value={rules.trading.min_order_amount_krw}
                onChange={(v) => updateField('trading.min_order_amount_krw', v)} />
              <NumberField label="진입 스캔 간격 (초)" value={rules.trading.cooldown_seconds}
                onChange={(v) => updateField('trading.cooldown_seconds', Math.floor(v))} />
              <NumberField label="포지션 체크 간격 (초)" value={rules.trading.position_check_interval_seconds}
                onChange={(v) => updateField('trading.position_check_interval_seconds', Math.floor(v))} />
              <div>
                <label className="block text-xs text-gray-400 mb-1">매도 잠금 날짜</label>
                <input
                  type="date"
                  value={rules.trading.sell_lock_before_date || ''}
                  onChange={(e) => updateField('trading.sell_lock_before_date', e.target.value)}
                  className="input-field w-full text-sm"
                />
                <p className="text-xs text-gray-500 mt-1">이 날짜 이전 매수 코인은 자동 매도 제외</p>
              </div>
            </div>
          </Section>

          {/* 타겟 코인 */}
          <Section title="타겟 코인 필터링">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <NumberField label="상위 N개 (거래대금 순)" value={rules.target_coins.top_n}
                onChange={(v) => updateField('target_coins.top_n', Math.floor(v))} />
              <NumberField label="갱신 주기 (초)" value={rules.target_coins.refresh_interval_seconds}
                onChange={(v) => updateField('target_coins.refresh_interval_seconds', Math.floor(v))} />
            </div>
          </Section>

          {/* 기술적 전략 - 진입 */}
          <Section title="기술적 전략 (15분봉 눌림목)" badge="진입">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs text-gray-400 mb-1">캔들 간격</label>
                <select
                  value={rules.technical_strategy.candle_interval}
                  onChange={(e) => updateField('technical_strategy.candle_interval', e.target.value)}
                  className="input-field w-full text-sm"
                >
                  <option value="1m">1분</option>
                  <option value="5m">5분</option>
                  <option value="15m">15분</option>
                  <option value="1h">1시간</option>
                  <option value="4h">4시간</option>
                  <option value="1d">1일</option>
                </select>
              </div>
              <NumberField label="캔들 수" value={rules.technical_strategy.candle_count}
                onChange={(v) => updateField('technical_strategy.candle_count', Math.floor(v))} />
              <NumberField label="장기 EMA" value={rules.technical_strategy.entry.ema_long}
                onChange={(v) => updateField('technical_strategy.entry.ema_long', Math.floor(v))} />
              <NumberField label="단기 EMA" value={rules.technical_strategy.entry.ema_short}
                onChange={(v) => updateField('technical_strategy.entry.ema_short', Math.floor(v))} />
              <NumberField label="RSI 기간" value={rules.technical_strategy.entry.rsi_period}
                onChange={(v) => updateField('technical_strategy.entry.rsi_period', Math.floor(v))} />
              <NumberField label="RSI 하한 (0=비활성)" value={rules.technical_strategy.entry.rsi_min}
                onChange={(v) => updateField('technical_strategy.entry.rsi_min', v)} />
              <NumberField label="RSI 상한 (0=비활성)" value={rules.technical_strategy.entry.rsi_max}
                onChange={(v) => updateField('technical_strategy.entry.rsi_max', v)} />
            </div>
          </Section>

          {/* 기술적 전략 - 청산 */}
          <Section title="기술적 전략" badge="청산">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <NumberField label="손절 (%)" value={rules.technical_strategy.exit.stop_loss_pct}
                onChange={(v) => updateField('technical_strategy.exit.stop_loss_pct', v)} />
              <NumberField label="1차 익절 (%)" value={rules.technical_strategy.exit.tp1_pct}
                onChange={(v) => updateField('technical_strategy.exit.tp1_pct', v)} />
              <NumberField label="1차 익절 매도 비율" value={rules.technical_strategy.exit.tp1_sell_ratio}
                onChange={(v) => updateField('technical_strategy.exit.tp1_sell_ratio', v)} />
              <NumberField label="Moonbag 트레일링 (%)" value={rules.technical_strategy.exit.moonbag_trail_pct}
                onChange={(v) => updateField('technical_strategy.exit.moonbag_trail_pct', v)} />
            </div>
            <p className="text-xs text-gray-500 mt-3">
              진입 조건: 현재가 &gt; E{rules.technical_strategy.entry.ema_short} &gt; E{rules.technical_strategy.entry.ema_long} (정배열)
              {rules.technical_strategy.entry.rsi_min > 0 && <> AND RSI &ge; {rules.technical_strategy.entry.rsi_min}</>}
              {rules.technical_strategy.entry.rsi_max > 0 && <> AND RSI &le; {rules.technical_strategy.entry.rsi_max}</>}
            </p>
          </Section>

          {/* 이벤트 전략 */}
          <Section title="이벤트 전략 (개별 코인 뉴스)">
            <p className="text-xs text-gray-500 mb-3">
              거래대금 상위 N개(타겟) 코인은 낮은 임계값, 그 외(비타겟) 코인은 높은 임계값이 적용됩니다.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-3">
              <div className="bg-emerald-900/20 border border-emerald-800/30 rounded-lg p-3">
                <h4 className="text-xs font-medium text-emerald-400 mb-2">타겟 코인 (상위 {rules.target_coins.top_n}개)</h4>
                <div className="grid grid-cols-2 gap-3">
                  <NumberField label="매수 임계값" value={rules.event_strategy.buy_score_threshold}
                    onChange={(v) => updateField('event_strategy.buy_score_threshold', Math.floor(v))} />
                  <NumberField label="매도 임계값" value={rules.event_strategy.sell_score_threshold}
                    onChange={(v) => updateField('event_strategy.sell_score_threshold', Math.floor(v))} />
                </div>
              </div>
              <div className="bg-gray-800/50 border border-gray-700/30 rounded-lg p-3">
                <h4 className="text-xs font-medium text-gray-400 mb-2">비타겟 코인</h4>
                <div className="grid grid-cols-2 gap-3">
                  <NumberField label="매수 임계값" value={rules.event_strategy.non_target_buy_score_threshold}
                    onChange={(v) => updateField('event_strategy.non_target_buy_score_threshold', Math.floor(v))} />
                  <NumberField label="매도 임계값" value={rules.event_strategy.non_target_sell_score_threshold}
                    onChange={(v) => updateField('event_strategy.non_target_sell_score_threshold', Math.floor(v))} />
                </div>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <NumberField label="매수 비중 (%)" value={rules.event_strategy.buy_position_size_pct}
                onChange={(v) => updateField('event_strategy.buy_position_size_pct', v)} />
            </div>
            <h4 className="text-sm font-medium text-gray-300 mt-4 mb-2">이벤트 청산 규칙</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <NumberField label="손절 (%)" value={rules.event_strategy.exit.stop_loss_pct}
                onChange={(v) => updateField('event_strategy.exit.stop_loss_pct', v)} />
              <NumberField label="1차 익절 (%)" value={rules.event_strategy.exit.tp1_pct}
                onChange={(v) => updateField('event_strategy.exit.tp1_pct', v)} />
              <NumberField label="1차 매도 비율" value={rules.event_strategy.exit.tp1_sell_ratio}
                onChange={(v) => updateField('event_strategy.exit.tp1_sell_ratio', v)} />
              <NumberField label="Moonbag 트레일링 (%)" value={rules.event_strategy.exit.moonbag_trail_pct}
                onChange={(v) => updateField('event_strategy.exit.moonbag_trail_pct', v)} />
            </div>
          </Section>

          {/* 매크로 전략 */}
          <Section title="매크로 전략 (거시경제 킬스위치)">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <NumberField label="매수 점수 임계값" value={rules.macro_strategy.buy_score_threshold}
                onChange={(v) => updateField('macro_strategy.buy_score_threshold', Math.floor(v))} />
              <NumberField label="매도 점수 임계값 (킬스위치)" value={rules.macro_strategy.sell_score_threshold}
                onChange={(v) => updateField('macro_strategy.sell_score_threshold', Math.floor(v))} />
              <NumberField label="호재 매수 비중 (%)" value={rules.macro_strategy.buy_position_size_pct}
                onChange={(v) => updateField('macro_strategy.buy_position_size_pct', v)} />
              <div>
                <label className="block text-xs text-gray-400 mb-1">호재 매수 종목</label>
                <input
                  type="text"
                  value={rules.macro_strategy.buy_symbol}
                  onChange={(e) => updateField('macro_strategy.buy_symbol', e.target.value)}
                  className="input-field w-full text-sm"
                />
              </div>
              <NumberField label="킬스위치 정지 시간 (초)" value={rules.macro_strategy.pause_duration_seconds}
                onChange={(v) => updateField('macro_strategy.pause_duration_seconds', Math.floor(v))} />
            </div>
            <p className="text-xs text-gray-500 mt-3">
              악재 감지 시: 전 포지션 전량 매도 + {Math.floor(rules.macro_strategy.pause_duration_seconds / 60)}분간 진입 정지
            </p>
          </Section>

          {/* 필터 */}
          <Section title="필터">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <NumberField label="최소 가격 (KRW)" value={rules.filters.min_price_krw}
                onChange={(v) => updateField('filters.min_price_krw', v)} />
              <div>
                <label className="block text-xs text-gray-400 mb-1">블랙리스트 (쉼표 구분)</label>
                <input
                  type="text"
                  value={rules.filters.blacklist.join(', ')}
                  onChange={(e) => updateField('filters.blacklist',
                    e.target.value ? e.target.value.split(',').map(s => s.trim()).filter(Boolean) : []
                  )}
                  placeholder="KRW-DOGE, KRW-SHIB"
                  className="input-field w-full text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">화이트리스트 (쉼표 구분, 비우면 전체 허용)</label>
                <input
                  type="text"
                  value={rules.filters.whitelist.join(', ')}
                  onChange={(e) => updateField('filters.whitelist',
                    e.target.value ? e.target.value.split(',').map(s => s.trim()).filter(Boolean) : []
                  )}
                  placeholder="비우면 전체 코인 허용"
                  className="input-field w-full text-sm"
                />
              </div>
            </div>
          </Section>
        </div>
      )}
    </div>
  )
}

/* ─── 도움말 패널 ─── */
function HelpPanel() {
  const [openSection, setOpenSection] = useState<string | null>('rules')

  const toggle = (key: string) => setOpenSection(openSection === key ? null : key)

  return (
    <div className="space-y-3">
      {/* 규칙 설명 */}
      <HelpAccordion
        id="rules"
        title="매매 규칙 설명"
        open={openSection === 'rules'}
        onToggle={() => toggle('rules')}
      >
        <HelpGroup title="매매 기본 설정">
          <HelpItem term="최대 포지션 크기 (%)" desc="총 자산 대비 한 종목에 투입할 수 있는 최대 비율입니다. 10%이면 1,000만 원 자산 기준 한 종목에 최대 100만 원까지 매수합니다." />
          <HelpItem term="최대 동시 포지션 수" desc="동시에 보유할 수 있는 코인의 종류 수입니다. 5이면 최대 5개 코인을 동시에 보유합니다." />
          <HelpItem term="최소 주문 금액 (KRW)" desc="업비트 최소 주문 기준입니다. 이 금액 이하의 주문은 실행되지 않습니다." />
          <HelpItem term="진입 스캔 간격 (초)" desc="새로운 매수 기회를 탐색하는 주기입니다. 60초이면 1분마다 전체 타겟 코인을 스캔합니다." />
          <HelpItem term="포지션 체크 간격 (초)" desc="이미 보유 중인 포지션의 손익을 확인하는 주기입니다. 15초이면 15초마다 익절/손절 조건을 체크합니다." />
          <HelpItem term="매도 잠금 날짜" desc="이 날짜 이전에 매수한 코인은 자동 매도에서 제외됩니다. 장기 보유 목적의 코인을 보호합니다." />
        </HelpGroup>

        <HelpGroup title="타겟 코인 필터링">
          <HelpItem term="상위 N개" desc="업비트 KRW 마켓에서 24시간 거래대금 기준 상위 N개 코인만 매매 대상으로 삼습니다. 거래량이 충분해야 슬리피지가 적습니다." />
          <HelpItem term="갱신 주기" desc="타겟 코인 목록을 업데이트하는 간격입니다. 시장 상황에 따라 거래대금 순위가 변하므로 주기적으로 갱신합니다." />
        </HelpGroup>

        <HelpGroup title="기술적 전략 (눌림목)">
          <HelpItem term="캔들 간격 / 캔들 수" desc="분석에 사용할 차트 봉의 시간 단위와 개수입니다. 15분봉 200개 = 약 50시간 분량의 차트 데이터를 분석합니다." />
          <HelpItem term="장기 EMA / 단기 EMA" desc="현재가 > 단기 EMA(20) > 장기 EMA(200) 정배열 조건이 충족되어야 매수합니다." />
          <HelpItem term="RSI 하한 / 상한" desc="RSI가 하한~상한 범위 안에 있을 때만 매수합니다. 0으로 설정하면 해당 바운드를 비활성화합니다." />
          <HelpItem term="손절 / 1차 익절 / 2차 익절" desc="매수가 대비 하락 시 손절, 상승 시 분할 익절합니다. 1차 익절 시 보유량의 일정 비율만 매도하고 나머지는 2차 목표까지 홀딩합니다." />
          <HelpItem term="트레일링 활성화 / 스탑" desc="수익이 활성화 %에 도달하면 트레일링 스탑이 켜집니다. 최고점 대비 스탑 %만큼 하락하면 자동 매도합니다." />
        </HelpGroup>

        <HelpGroup title="이벤트 전략 (뉴스/트위터)">
          <HelpItem term="타겟 코인 임계값" desc="거래대금 상위 N개 코인에 적용됩니다. 유동성이 높으므로 낮은 점수(기본 5/-5)에도 반응합니다." />
          <HelpItem term="비타겟 코인 임계값" desc="상위 N개 밖의 코인에 적용됩니다. 신뢰도가 높아야 하므로 높은 점수(기본 25/-25)를 요구합니다." />
          <HelpItem term="매수 비중 (%)" desc="이벤트 매수 시 투입할 자산 비율입니다. 기술적 전략과 별개로 적용됩니다." />
          <HelpItem term="이벤트 청산 규칙" desc="이벤트 기반으로 매수한 포지션에 적용되는 손절/익절 규칙입니다. 기술적 전략과 다른 값을 설정할 수 있습니다." />
        </HelpGroup>

        <HelpGroup title="매크로 전략 (킬스위치)">
          <HelpItem term="매수 점수 임계값" desc="거시경제 호재(금리 인하, 양적완화 등) 감지 시, 점수가 이 값 이상이면 지정 종목(기본 BTC)을 매수합니다." />
          <HelpItem term="매도 점수 임계값 (킬스위치)" desc="거시경제 악재(전쟁, 경기침체 등) 감지 시, 점수가 이 값 이하이면 전 포지션을 즉시 매도하고 진입을 정지합니다." />
          <HelpItem term="킬스위치 정지 시간" desc="킬스위치 발동 후 신규 매수를 정지하는 시간(초)입니다. 7200초 = 2시간. 기존 포지션 모니터링은 계속 작동합니다." />
        </HelpGroup>

        <HelpGroup title="필터">
          <HelpItem term="최소 가격 (KRW)" desc="이 가격 이하의 코인은 매매 대상에서 제외합니다. 너무 저가의 잡코인을 걸러냅니다." />
          <HelpItem term="블랙리스트" desc="절대 매매하지 않을 코인 목록입니다. 여기 등록된 코인은 타겟 코인에서 제외됩니다." />
          <HelpItem term="화이트리스트" desc="비어 있으면 모든 코인이 허용됩니다. 값이 있으면 여기 등록된 코인만 매매합니다." />
        </HelpGroup>

        <HelpGroup title="소스 티어 리스트">
          <HelpItem term="Tier 1 (즉시 대응)" desc="속보성 높은 소스입니다. 짧은 간격(30초)으로 체크합니다. 주요 인플루언서(elonmusk 등)가 포함됩니다." />
          <HelpItem term="Tier 2 (주요 동향)" desc="시장 동향을 추적하는 소스입니다. 비교적 긴 간격(120초)으로 체크합니다. CoinDesk, WatcherGuru 등이 포함됩니다." />
          <HelpItem term="소스 검증" desc="티어 리스트에 등록되지 않은 출처의 정보는 Gemini 분석으로 전달되지 않습니다. 신뢰 소스만 분석하여 노이즈를 차단합니다." />
        </HelpGroup>
      </HelpAccordion>

      {/* 용어 사전 */}
      <HelpAccordion
        id="glossary"
        title="용어 사전"
        open={openSection === 'glossary'}
        onToggle={() => toggle('glossary')}
      >
        <div className="space-y-4">
          <GlossaryItem
            term="포지션 (Position)"
            desc="현재 보유 중인 코인을 말합니다."
            detail="예: BTC를 100만 원어치 매수했다면 'BTC 포지션을 잡았다'고 표현합니다. 포지션 크기는 투입 금액, 포지션 수는 보유 중인 종목 개수를 의미합니다."
          />
          <GlossaryItem
            term="캔들 (Candle / 봉)"
            desc="일정 시간 동안의 가격 변동을 나타내는 차트 요소입니다."
            detail="각 캔들에는 시가(Open), 고가(High), 저가(Low), 종가(Close), 거래량(Volume)이 포함됩니다. 15분봉이면 15분 동안의 가격 움직임을 하나의 봉으로 표시합니다."
          />
          <GlossaryItem
            term="EMA (지수이동평균)"
            desc="최근 가격에 더 큰 가중치를 주는 이동평균선입니다."
            detail={
              'EMA 200 = 최근 200개 캔들의 가중 평균. 장기 추세를 보여줍니다.\n'
              + 'EMA 20 = 최근 20개 캔들의 가중 평균. 단기 흐름을 보여줍니다.\n\n'
              + '눌림목 전략: 가격이 EMA 200 위에 있으면 "상승 추세", EMA 20 아래로 내려오면 "눌림"으로 판단하여 매수합니다. 상승 추세에서 일시적으로 빠졌을 때 저점 매수를 노리는 전략입니다.'
            }
          />
          <GlossaryItem
            term="RSI (상대강도지수)"
            desc="가격의 과매수/과매도 상태를 0~100 사이 값으로 나타내는 지표입니다."
            detail={
              'RSI 70 이상 = 과매수 (가격이 너무 올랐음, 하락 가능성)\n'
              + 'RSI 30 이하 = 과매도 (가격이 너무 빠졌음, 반등 가능성)\n\n'
              + '이 시스템에서는 RSI가 설정된 범위(하한~상한) 안에 있을 때만 매수합니다. 하한 또는 상한을 0으로 설정하면 해당 조건을 비활성화합니다.'
            }
          />
          <GlossaryItem
            term="트레일링 스탑 (Trailing Stop)"
            desc="수익이 발생하면 매도 기준선이 가격을 따라 올라가는 자동 매도 방식입니다."
            detail={
              '1. 수익률이 "활성화 %" (예: 1.0%)에 도달하면 트레일링 스탑이 켜집니다.\n'
              + '2. 이후 가격이 오르면 최고점을 계속 갱신합니다.\n'
              + '3. 최고점 대비 "스탑 %" (예: 0.2%)만큼 하락하면 자동 매도합니다.\n\n'
              + '효과: 상승장에서 수익을 최대한 끌어올리면서, 하락 전환 시 자동으로 빠져나옵니다.'
            }
          />
          <GlossaryItem
            term="킬 스위치 (Kill Switch)"
            desc="거시경제 악재 감지 시 모든 포지션을 즉시 청산하고 신규 매수를 정지하는 비상 장치입니다."
            detail={
              '발동 조건: Gemini AI가 뉴스에서 전쟁, 경기침체, 금리 인상 등 매크로 악재를 감지하고 점수가 임계값 이하일 때\n\n'
              + '동작:\n'
              + '1. 보유 중인 모든 포지션을 시장가로 전량 매도\n'
              + '2. 설정된 시간(기본 2시간) 동안 신규 매수 진입을 차단\n'
              + '3. 기존 포지션 모니터링(손절/익절)은 계속 정상 작동\n\n'
              + '대시보드에 빨간 경고 배너로 잔여 정지 시간이 표시됩니다.'
            }
          />
          <GlossaryItem
            term="손절 / 익절 (Stop Loss / Take Profit)"
            desc="미리 정한 가격에 도달하면 자동으로 매도하는 규칙입니다."
            detail={
              '손절 (SL): 매수가 대비 일정 % 하락하면 손실을 확정하고 매도합니다.\n'
              + '   예: 손절 1.0% → 100만 원에 매수한 코인이 99만 원이 되면 매도\n\n'
              + '1차 익절 (TP1): 매수가 대비 일정 % 상승하면 보유량의 일부를 매도합니다.\n'
              + '   예: 1차 익절 1.5%, 매도 비율 50% → 1.5% 오르면 절반 매도\n\n'
              + '2차 익절 (TP2): 더 높은 목표에 도달하면 나머지를 전량 매도합니다.\n'
              + '   예: 2차 익절 2.5% → 2.5% 오르면 남은 전량 매도'
            }
          />
          <GlossaryItem
            term="키워드 점수 (Sentiment Score)"
            desc="Gemini AI가 뉴스/트윗에서 핵심 키워드를 찾아 -5 ~ +5 점수로 변환한 값입니다."
            detail={
              '코인별 양성: Listing(+5), Approved(+4), Partnership(+3), Burn(+2)\n'
              + '코인별 음성: Hack(-5), SEC(-4), Delay(-2)\n\n'
              + '매크로 양성: Rate Cut(+5), Lower CPI(+5), QE(+5), Stimulus(+5)\n'
              + '매크로 음성: Rate Hike(-5), War(-5), Recession(-5)\n\n'
              + '점수가 +4 이상이면 매수, -4 이하이면 매도/킬스위치 시그널이 됩니다.'
            }
          />
        </div>
      </HelpAccordion>

      {/* 시스템 작동 흐름 */}
      <HelpAccordion
        id="flow"
        title="시스템 작동 흐름"
        open={openSection === 'flow'}
        onToggle={() => toggle('flow')}
      >
        <div className="space-y-3 text-sm text-gray-300">
          <FlowStep step={1} title="소스 수집" desc="Gemini 뉴스 검색, 트위터 등에서 최신 뉴스/게시물을 수집합니다." />
          <FlowStep step={2} title="Gemini 분석" desc="수집된 텍스트를 Gemini AI에 전달합니다. AI가 키워드 점수 사전에 따라 점수(-5~+5)를 매기고 관련 코인(ticker)과 범위(scope)를 판별합니다." />
          <FlowStep step={3} title="시그널 생성" desc="점수가 0이 아니면 시그널(buy/sell/hold)을 생성합니다. scope가 ticker면 개별 코인, macro면 전체 시장에 영향을 줍니다." />
          <FlowStep step={4} title="매매 엔진 처리" desc="시그널이 매매 엔진에 전달됩니다. 이벤트 전략(개별 코인) 또는 매크로 전략(킬스위치/BTC 매수)이 실행됩니다." />
          <FlowStep step={5} title="기술적 분석 스캔" desc="시그널과 별개로, 진입 스캔 루프가 타겟 코인들의 차트(EMA/RSI)를 분석하여 눌림목 매수 기회를 찾습니다." />
          <FlowStep step={6} title="포지션 모니터링" desc="보유 중인 포지션은 15초마다 손절/익절/트레일링 스탑 조건을 체크하여 자동 청산합니다." />
        </div>
      </HelpAccordion>
    </div>
  )
}

/* ─── 도움말 하위 컴포넌트 ─── */

function HelpAccordion({ id, title, open, onToggle, children }: {
  id: string; title: string; open: boolean; onToggle: () => void; children: React.ReactNode
}) {
  return (
    <div className="card">
      <button onClick={onToggle} className="w-full flex items-center justify-between text-left">
        <h3 className="text-lg font-semibold">{title}</h3>
        <span className="text-gray-500 text-sm">{open ? '접기' : '펼치기'}</span>
      </button>
      {open && <div className="mt-4">{children}</div>}
    </div>
  )
}

function HelpGroup({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-5 last:mb-0">
      <h4 className="text-sm font-semibold text-primary-400 mb-2 pb-1 border-b border-gray-700">{title}</h4>
      <div className="space-y-1.5">{children}</div>
    </div>
  )
}

function HelpItem({ term, desc }: { term: string; desc: string }) {
  return (
    <div className="flex gap-2 text-sm">
      <span className="text-gray-400 font-medium shrink-0 w-44">{term}</span>
      <span className="text-gray-300">{desc}</span>
    </div>
  )
}

function GlossaryItem({ term, desc, detail }: { term: string; desc: string; detail: string }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="border border-gray-700/50 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-3 text-left hover:bg-gray-800/30"
      >
        <div>
          <span className="font-semibold text-white">{term}</span>
          <p className="text-sm text-gray-400 mt-0.5">{desc}</p>
        </div>
        <span className="text-gray-500 text-xs shrink-0 ml-2">{open ? '접기' : '자세히'}</span>
      </button>
      {open && (
        <div className="px-3 pb-3 pt-0">
          <div className="bg-gray-900/50 rounded p-3 text-sm text-gray-300 whitespace-pre-line leading-relaxed">
            {detail}
          </div>
        </div>
      )}
    </div>
  )
}

function FlowStep({ step, title, desc }: { step: number; title: string; desc: string }) {
  return (
    <div className="flex gap-3">
      <div className="shrink-0 w-7 h-7 rounded-full bg-primary-900 text-primary-300 flex items-center justify-center text-xs font-bold">
        {step}
      </div>
      <div>
        <p className="font-medium text-white">{title}</p>
        <p className="text-gray-400 text-sm mt-0.5">{desc}</p>
      </div>
    </div>
  )
}

/* ─── 공통 UI 컴포넌트 ─── */

function Section({ title, badge, children }: { title: string; badge?: string; children: React.ReactNode }) {
  return (
    <div className="card">
      <div className="flex items-center gap-2 mb-4">
        <h3 className="text-lg font-semibold">{title}</h3>
        {badge && (
          <span className="text-xs px-2 py-0.5 rounded bg-primary-900 text-primary-300">{badge}</span>
        )}
      </div>
      {children}
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
