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
  fee_krw: number | null
  pnl: number | null
  pnl_pct: number | null
  current_price?: number
  sell_price?: number
  sell_amount?: number
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

export interface BotPosition {
  symbol: string
  bot_quantity: number
  bot_avg_price: number
  current_price: number
  bot_pnl: number
  bot_pnl_pct: number
  bot_value: number
  entry_source: string
  original_quantity: number
  first_tp_done: boolean
  peak_pnl_pct: number
}

export interface Signal {
  id?: number
  source: string
  action: 'buy' | 'sell' | 'hold'
  symbol: string | null
  confidence: number
  summary: string
  url?: string
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
    max_position_size_pct: number
    max_concurrent_positions: number
    min_order_amount_krw: number
    cooldown_seconds: number
    position_check_interval_seconds: number
    sell_lock_before_date: string
  }
  target_coins: {
    top_n: number
    refresh_interval_seconds: number
  }
  technical_strategy: {
    candle_interval: string
    candle_count: number
    entry: {
      ema_long: number
      ema_short: number
      rsi_period: number
      rsi_min: number
      rsi_max: number
    }
    exit: {
      stop_loss_pct: number
      tp1_pct: number
      tp1_sell_ratio: number
      moonbag_trail_pct: number
    }
  }
  event_strategy: {
    buy_score_threshold: number
    sell_score_threshold: number
    non_target_buy_score_threshold: number
    non_target_sell_score_threshold: number
    buy_position_size_pct: number
    exit: {
      stop_loss_pct: number
      tp1_pct: number
      tp1_sell_ratio: number
      moonbag_trail_pct: number
    }
  }
  macro_strategy: {
    buy_score_threshold: number
    sell_score_threshold: number
    buy_position_size_pct: number
    buy_symbol: string
    pause_duration_seconds: number
  }
  filters: {
    min_price_krw: number
    blacklist: string[]
    whitelist: string[]
  }
  source_list: {
    tier1: SourceTier
    tier2: SourceTier
  }
}

export interface SourceConfig {
  name: string
  type: 'influencer'
  domain?: string
  crypto_only?: boolean
}

export interface SourceTier {
  label: string
  check_interval_seconds: number
  sources: SourceConfig[]
}

export interface EntryStatus {
  ema_200?: number
  ema_20?: number
  rsi?: number
  current_price?: number
  reasons?: string[]
  action?: string
}

export interface TargetCoin {
  rank: number
  symbol: string
  trade_price: number
  acc_trade_price_1h: number
  acc_trade_price_24h: number
  signed_change_rate: number
  is_target: boolean
  entry_status?: EntryStatus | null
}

export interface SystemStatus {
  engine: {
    running: boolean
    positions_count: number
    positions: Position[]
    rules_version: string
    target_symbols: string[]
    entry_paused: boolean
    entry_pause_remaining_seconds: number
  }
  news_monitor: {
    running: boolean
    interval_seconds: number
    last_signals_count: number
    last_check_time: string | null
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
  news_interval_seconds: number
  twitter_accounts: string[]
  twitter_interval_seconds: number
  news_monitor_running: boolean
  twitter_monitor_running: boolean
  system_status: SystemStatus
}

export interface WsMessage {
  type: string
  data: Record<string, unknown>
  timestamp: string
}
