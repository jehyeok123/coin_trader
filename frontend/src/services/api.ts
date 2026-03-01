import axios from 'axios'
import type { Trade, Position, BotPosition, Signal, Candle, TradingRules, Settings, TargetCoin } from '../types'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

// Trading
export const getTradingStatus = () => api.get('/trading/status')
export const startTrading = () => api.post('/trading/start')
export const stopTrading = () => api.post('/trading/stop')
export const getTradeHistory = (params?: { limit?: number; offset?: number; symbol?: string; side?: string; from_date?: string }) =>
  api.get<{ trades: Trade[]; total: number }>('/trading/history', { params })
export const getPositions = () =>
  api.get<{ krw_balance: number; total_value: number; total_realized_pnl: number; bot_positions: BotPosition[]; bot_realized_pnl: number; positions: Position[]; max_positions: number }>('/trading/positions')
export const getTargetCoins = () =>
  api.get<{ coins: TargetCoin[]; top_n: number; total_symbols: number; cooldown_seconds?: number; refresh_interval_seconds?: number; rsi_min?: number; rsi_max?: number }>('/trading/target-coins')
export const syncTradeHistory = (from_date: string) =>
  api.post<{ success: boolean; synced: number; skipped: number; errors: number; total_from_upbit: number }>(
    '/trading/sync-history', { from_date }
  )

// Rules
export const getRules = () => api.get<{ rules: TradingRules }>('/rules')
export const updateRules = (rules: TradingRules) => api.put('/rules', { rules })
export const resetRules = () => api.post('/rules/reset')

// Charts
export const getSymbols = () => api.get<{ symbols: string[] }>('/charts/symbols')
export const getChartData = (symbol: string, interval = '5m', count = 200) =>
  api.get<{ symbol: string; interval: string; candles: Candle[] }>(`/charts/${symbol}`, {
    params: { interval, count },
  })
export const getTicker = (symbol: string) =>
  api.get(`/charts/${symbol}/ticker`)

// Signals
export const getSignals = (params?: { limit?: number; offset?: number; source?: string }) =>
  api.get<{ signals: Signal[]; total: number }>('/signals', { params })
export const getLatestSignals = () =>
  api.get<{ news: Signal[]; twitter: Signal[] }>('/signals/latest')
export const triggerNewsCheck = () => api.post('/signals/check-news')

// Settings
export const getSettings = () => api.get<Settings>('/settings')
export const testConnection = () => api.get('/settings/test-connection')
export const updateSettings = (data: { news_interval_seconds?: number; twitter_accounts?: string[] }) =>
  api.put('/settings', data)
export const toggleNewsMonitor = (enabled: boolean) =>
  api.post('/settings/toggle-news-monitor', { enabled })
export const toggleTwitterMonitor = (enabled: boolean) =>
  api.post('/settings/toggle-twitter-monitor', { enabled })

export default api
