import type { TradingRules } from '../../types'

interface Props {
  rules: TradingRules
}

export default function RuleList({ rules }: Props) {
  return (
    <div className="card">
      <h3 className="text-lg font-semibold mb-4">현재 적용 규칙 요약</h3>
      <div className="space-y-3 text-sm">
        <div className="flex justify-between py-1 border-b border-gray-700/50">
          <span className="text-gray-400">손절</span>
          <span className="text-loss font-semibold">-{rules.trading.stop_loss_pct}%</span>
        </div>
        <div className="flex justify-between py-1 border-b border-gray-700/50">
          <span className="text-gray-400">익절</span>
          <span className="text-profit font-semibold">+{rules.trading.take_profit_pct}%</span>
        </div>
        <div className="flex justify-between py-1 border-b border-gray-700/50">
          <span className="text-gray-400">최대 포지션</span>
          <span>{rules.trading.max_concurrent_positions}개</span>
        </div>
        <div className="flex justify-between py-1 border-b border-gray-700/50">
          <span className="text-gray-400">포지션 크기</span>
          <span>{rules.trading.max_position_size_pct}%</span>
        </div>
        <div className="mt-3">
          <p className="text-gray-400 mb-2">활성 지표:</p>
          <div className="flex flex-wrap gap-2">
            {Object.entries(rules.indicators)
              .filter(([, v]) => (v as Record<string, unknown>).enabled)
              .map(([key]) => (
                <span key={key} className="badge bg-primary-900 text-primary-300">
                  {key.replace(/_/g, ' ')}
                </span>
              ))}
          </div>
        </div>
      </div>
    </div>
  )
}
