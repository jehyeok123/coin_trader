import type { TradingRules } from '../../types'

interface Props {
  rules: TradingRules
}

export default function RuleList({ rules }: Props) {
  return (
    <div className="card">
      <h3 className="text-lg font-semibold mb-4">현재 적용 규칙 요약</h3>
      <div className="space-y-3 text-sm">
        <Row label="기술 손절" value={`-${rules.technical_strategy.exit.stop_loss_pct}%`} color="text-loss" />
        <Row label="기술 1차 익절" value={`+${rules.technical_strategy.exit.tp1_pct}% (${Math.round(rules.technical_strategy.exit.tp1_sell_ratio * 100)}% 매도)`} color="text-profit" />
        <Row label="Moonbag 트레일링" value={`고점 대비 -${rules.technical_strategy.exit.moonbag_trail_pct}% 하락 시 전량 매도`} />
        <Row label="이벤트 손절" value={`-${rules.event_strategy.exit.stop_loss_pct}%`} color="text-loss" />
        <Row label="이벤트 1차 익절" value={`+${rules.event_strategy.exit.tp1_pct}% (${Math.round(rules.event_strategy.exit.tp1_sell_ratio * 100)}% 매도)`} color="text-profit" />
        <Row label="이벤트 Moonbag" value={`고점 대비 -${rules.event_strategy.exit.moonbag_trail_pct}% 하락 시 전량 매도`} />
        <Row label="최대 포지션" value={`${rules.trading.max_concurrent_positions}개`} />
        <Row label="포지션 크기" value={`${rules.trading.max_position_size_pct}%`} />
        <Row label="킬스위치 정지" value={`${Math.floor(rules.macro_strategy.pause_duration_seconds / 60)}분`} />
        <div className="mt-3">
          <p className="text-gray-400 mb-2">전략:</p>
          <div className="flex flex-wrap gap-2">
            <span className="badge bg-primary-900 text-primary-300">
              {rules.technical_strategy.candle_interval} 풀백
            </span>
            <span className="badge bg-purple-900 text-purple-300">
              이벤트 (score &ge; {rules.event_strategy.buy_score_threshold})
            </span>
            <span className="badge bg-red-900 text-red-300">
              매크로 킬스위치
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

function Row({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex justify-between py-1 border-b border-gray-700/50">
      <span className="text-gray-400">{label}</span>
      <span className={`font-semibold ${color || ''}`}>{value}</span>
    </div>
  )
}
