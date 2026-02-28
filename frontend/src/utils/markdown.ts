/**
 * Markdown 관련 유틸리티
 */

export function formatTradeMarkdown(trade: {
  symbol: string
  side: string
  price: number
  amount_krw: number
  reason?: string
  pnl_pct?: number | null
}): string {
  const emoji = trade.side === 'buy' ? '🟢' : '🔴'
  const pnl = trade.pnl_pct != null ? ` (P&L: ${trade.pnl_pct >= 0 ? '+' : ''}${trade.pnl_pct.toFixed(2)}%)` : ''
  return `${emoji} **${trade.side.toUpperCase()}** \`${trade.symbol}\` @ ${trade.price.toLocaleString()} KRW (${trade.amount_krw.toLocaleString()} KRW)${pnl} - ${trade.reason || ''}`.trim()
}

export function formatSignalMarkdown(signal: {
  source: string
  action: string
  symbol?: string | null
  confidence: number
  summary: string
}): string {
  const icons: Record<string, string> = { news: '📰', twitter: '🐦', technical: '📊' }
  const actionIcons: Record<string, string> = { buy: '🟢', sell: '🔴', hold: '⚪' }
  return `${icons[signal.source] || '❓'} **[${signal.source.toUpperCase()}]** ${actionIcons[signal.action] || '❓'} ${signal.action.toUpperCase()} \`${signal.symbol || 'N/A'}\` (신뢰도: ${(signal.confidence * 100).toFixed(0)}%) - ${signal.summary}`
}
