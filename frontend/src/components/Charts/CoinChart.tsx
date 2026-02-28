import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { createChart, type IChartApi, type ISeriesApi, ColorType } from 'lightweight-charts'
import { getSymbols, getChartData } from '../../services/api'
import { usePrices } from '../../contexts/PriceContext'
import type { Candle } from '../../types'

const INTERVALS = [
  { value: '1m', label: '1분' },
  { value: '5m', label: '5분' },
  { value: '15m', label: '15분' },
  { value: '1h', label: '1시간' },
  { value: '4h', label: '4시간' },
  { value: '1d', label: '1일' },
]

export default function CoinChart() {
  const { symbol: paramSymbol } = useParams()
  const [symbols, setSymbols] = useState<string[]>([])
  const [selectedSymbol, setSelectedSymbol] = useState(paramSymbol || 'KRW-BTC')
  const [interval, setInterval] = useState('5m')
  const [candles, setCandles] = useState<Candle[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const { prices, latencyMs } = usePrices()

  const chartContainerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null)

  // 심볼 목록 로드
  useEffect(() => {
    getSymbols().then((res) => {
      if (res.data.symbols?.length) {
        setSymbols(res.data.symbols)
      }
    }).catch(() => {
      setError('심볼 목록을 불러올 수 없습니다. 백엔드 서버가 실행 중인지 확인하세요.')
    })
  }, [])

  // 차트 데이터 로드
  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const res = await getChartData(selectedSymbol, interval, 200)
      const data = res.data as Record<string, unknown>
      if (data.error) {
        setError(`차트 데이터 오류: ${data.error}`)
        setCandles([])
      } else {
        setError(null)
        setCandles(res.data.candles || [])
      }
    } catch {
      setError('차트 데이터를 불러올 수 없습니다. 백엔드 서버를 확인하세요.')
      setCandles([])
    } finally {
      setLoading(false)
    }
  }, [selectedSymbol, interval])

  useEffect(() => {
    fetchData()
    const timer = window.setInterval(fetchData, 30000)
    return () => window.clearInterval(timer)
  }, [fetchData])

  // 차트 생성 - 컨테이너가 마운트된 후 한 번만
  useEffect(() => {
    if (!chartContainerRef.current) return

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#1f2937' },
        textColor: '#9ca3af',
      },
      grid: {
        vertLines: { color: '#374151' },
        horzLines: { color: '#374151' },
      },
      width: chartContainerRef.current.clientWidth,
      height: 500,
      crosshair: {
        mode: 0,
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
      },
    })

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#10b981',
      downColor: '#ef4444',
      borderDownColor: '#ef4444',
      borderUpColor: '#10b981',
      wickDownColor: '#ef4444',
      wickUpColor: '#10b981',
    })

    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: '',
    })
    volumeSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    })

    chartRef.current = chart
    candleSeriesRef.current = candleSeries
    volumeSeriesRef.current = volumeSeries

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth })
      }
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
      chartRef.current = null
      candleSeriesRef.current = null
      volumeSeriesRef.current = null
    }
  }, [])

  // 데이터 업데이트
  useEffect(() => {
    if (!candleSeriesRef.current || !volumeSeriesRef.current || !candles.length) return

    const candleData = candles.map((c) => ({
      time: c.time as any,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }))

    const volumeData = candles.map((c) => ({
      time: c.time as any,
      value: c.volume,
      color: c.close >= c.open ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)',
    }))

    candleSeriesRef.current.setData(candleData)
    volumeSeriesRef.current.setData(volumeData)

    if (chartRef.current) {
      chartRef.current.timeScale().fitContent()
    }
  }, [candles])

  // WebSocket 실시간 가격으로 마지막 캔들 업데이트
  const livePrice = prices[selectedSymbol] || 0
  useEffect(() => {
    if (!candleSeriesRef.current || !candles.length || !livePrice) return
    const last = candles[candles.length - 1]
    candleSeriesRef.current.update({
      time: last.time as any,
      open: last.open,
      high: Math.max(last.high, livePrice),
      low: Math.min(last.low, livePrice),
      close: livePrice,
    })
  }, [livePrice, candles, selectedSymbol])

  const lastCandle = candles[candles.length - 1]
  const displayPrice = livePrice || lastCandle?.close || 0
  const prevCandle = candles[candles.length - 2]
  const changeRate = prevCandle && displayPrice
    ? ((displayPrice - prevCandle.close) / prevCandle.close) * 100
    : 0

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-4">
          <select
            value={selectedSymbol}
            onChange={(e) => setSelectedSymbol(e.target.value)}
            className="input-field"
          >
            {symbols.length > 0
              ? symbols.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))
              : <option value={selectedSymbol}>{selectedSymbol}</option>
            }
          </select>

          {displayPrice > 0 && (
            <div className="flex items-center gap-3">
              <span className="text-2xl font-bold">
                {displayPrice.toLocaleString()} KRW
              </span>
              <span className={`text-sm font-semibold ${changeRate >= 0 ? 'text-profit' : 'text-loss'}`}>
                {changeRate >= 0 ? '+' : ''}{changeRate.toFixed(2)}%
              </span>
              {latencyMs > 0 && (
                <span className={`text-xs font-mono ${
                  latencyMs < 500 ? 'text-emerald-400' : latencyMs < 2000 ? 'text-yellow-400' : 'text-red-400'
                }`}>
                  {latencyMs}ms
                </span>
              )}
            </div>
          )}
        </div>

        <div className="flex gap-1">
          {INTERVALS.map((iv) => (
            <button
              key={iv.value}
              onClick={() => setInterval(iv.value)}
              className={`px-3 py-1.5 rounded text-sm transition-colors ${
                interval === iv.value
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              {iv.label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="bg-red-900/30 border border-red-700 text-red-300 p-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      {/* 차트 컨테이너 - 항상 DOM에 존재 (로딩/에러 오버레이를 위에 표시) */}
      <div className="card p-0 overflow-hidden relative">
        <div ref={chartContainerRef} className="w-full" />

        {/* 로딩 오버레이 */}
        {loading && candles.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-800/80 text-gray-400">
            차트 데이터 로딩 중...
          </div>
        )}
      </div>
    </div>
  )
}
