from fastapi import APIRouter, Query

router = APIRouter(prefix="/charts", tags=["Charts"])


@router.get("/symbols")
async def get_symbols():
    """거래 가능한 심볼 목록 조회"""
    from backend.main import get_broker
    broker = get_broker()
    if broker is None:
        return {"symbols": []}
    try:
        symbols = await broker.get_available_symbols()
        return {"symbols": symbols}
    except Exception as e:
        return {"symbols": [], "error": str(e)}


@router.get("/{symbol}")
async def get_chart_data(
    symbol: str,
    interval: str = Query("5m", description="캔들 간격 (1m, 5m, 15m, 1h, 4h, 1d)"),
    count: int = Query(200, ge=1, le=500),
):
    """차트 데이터 (OHLCV) 조회"""
    from backend.main import get_broker
    broker = get_broker()
    if broker is None:
        return {"candles": [], "message": "브로커가 초기화되지 않았습니다."}
    try:
        df = await broker.get_ohlcv(symbol, interval=interval, count=count)
        if df.empty:
            return {"symbol": symbol, "interval": interval, "candles": []}

        # pyupbit은 최신→과거 순서로 반환하므로 오름차순 정렬 필요
        df = df.sort_index(ascending=True)

        candles = []
        for idx, row in df.iterrows():
            candle = {
                "time": int(idx.timestamp()) if hasattr(idx, "timestamp") else 0,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            }
            candles.append(candle)

        return {
            "symbol": symbol,
            "interval": interval,
            "candles": candles,
        }
    except Exception as e:
        return {"symbol": symbol, "candles": [], "error": str(e)}


@router.get("/{symbol}/ticker")
async def get_ticker(symbol: str):
    """특정 종목 현재 시세 조회"""
    from backend.main import get_broker
    broker = get_broker()
    if broker is None:
        return {"error": "브로커가 초기화되지 않았습니다."}
    try:
        ticker = await broker.get_ticker(symbol)
        return {"symbol": symbol, "ticker": ticker}
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}
