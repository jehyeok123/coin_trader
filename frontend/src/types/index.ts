export interface Trade {
  id: number
  broker: string
  symbol: string
  side: 'buy' | 'sell'
  price: number
  quantity: number
  amount_krw: number
  order_id: string | null
  status: string
  reason: string | null
  signal_source: string | null
  pnl: number | null
  pnl_pct: number | null
  created_at: string
}

export interface Position {
  symbol: string
  quantity: number
  avg_price: number
  current_price: number
  pnl: number
  pnl_pct: number
}

export interface Signal {
  id?: number
  source: string
  action: 'buy' | 'sell' | 'hold'
  symbol: string | null
  confidence: number
  summary: string
  acted_on?: boolean
  created_at: string
}

export interface Candle {
  time: number
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface TradingRules {
  version: string
  description: string
  trading: {
    stop_loss_pct: number
    take_profit_pct: number
    trailing_stop_pct: number
    max_position_size_pct: number
    max_concurrent_positions: number
    min_order_amount_krw: number
    cooldown_seconds: number
    sell_lock_before_date: string
  }
  indicators: Record<string, Record<string, unknown>>
  filters: {
    min_volume_24h_krw: number
    min_price_krw: number
    blacklist: string[]
    whitelist: string[]
  }
  signal_weights: Record<string, number>
  interrupt: {
    enabled: boolean
    news_confidence_threshold: number
    twitter_confidence_threshold: number
    max_interrupt_position_pct: number
  }
}

export interface SystemStatus {
  engine: {
    running: boolean
    positions_count: number
    positions: Position[]
    rules_version: string
  }
  news_monitor: {
    running: boolean
    interval_minutes: number
    last_signals_count: number
  }
  twitter_monitor: {
    running: boolean
    accounts: string[]
    interval_seconds: number
    last_signals_count: number
  }
}

export interface Settings {
  upbit_connected: boolean
  gemini_connected: boolean
  news_interval_minutes: number
  twitter_accounts: string[]
  twitter_interval_seconds: number
  system_status: SystemStatus
}

export interface WsMessage {
  type: string
  data: Record<string, unknown>
  timestamp: string
}
