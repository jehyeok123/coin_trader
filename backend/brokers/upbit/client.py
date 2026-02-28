import asyncio
from functools import partial

import pandas as pd
import pyupbit

from backend.brokers.base import BaseBroker, BrokerType, OrderResult, Position
from backend.config import settings
from backend.utils.logger import logger


class UpbitBroker(BaseBroker):
    """
    업비트 API 브로커 구현.
    pyupbit 라이브러리를 래핑하여 비동기 인터페이스로 제공합니다.
    """

    broker_type = BrokerType.UPBIT

    def __init__(self):
        self._upbit = None
        if settings.upbit_access_key and settings.upbit_secret_key:
            self._upbit = pyupbit.Upbit(
                settings.upbit_access_key, settings.upbit_secret_key
            )
            logger.info("업비트 브로커 초기화 완료 (인증됨)")
        else:
            logger.warning("업비트 API 키가 설정되지 않았습니다. 조회만 가능합니다.")

    def _ensure_authenticated(self):
        if self._upbit is None:
            raise RuntimeError("업비트 API 키가 설정되지 않았습니다.")

    async def _run_sync(self, func, *args, **kwargs):
        """동기 pyupbit 함수를 비동기로 실행"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))

    async def get_balance(self) -> dict:
        self._ensure_authenticated()
        balances = await self._run_sync(self._upbit.get_balances)
        result = {"krw": 0.0, "assets": []}

        if balances is None:
            raise RuntimeError("잔고 조회 실패: 응답이 없습니다.")
        if isinstance(balances, dict) and "error" in balances:
            error_msg = balances["error"].get("message", "알 수 없는 오류")
            raise RuntimeError(f"잔고 조회 실패: {error_msg}")
        if not isinstance(balances, list):
            raise RuntimeError(f"잔고 조회 실패: 예상치 못한 응답 형식 ({type(balances).__name__})")

        for b in balances:
            if not isinstance(b, dict):
                continue
            if b.get("currency") == "KRW":
                result["krw"] = float(b.get("balance", 0))
            else:
                result["assets"].append({
                    "currency": b["currency"],
                    "balance": float(b.get("balance", 0)),
                    "locked": float(b.get("locked", 0)),
                    "avg_buy_price": float(b.get("avg_buy_price", 0)),
                })
        return result

    async def get_positions(self) -> list[Position]:
        balance = await self.get_balance()
        positions = []
        for asset in balance["assets"]:
            if asset["balance"] <= 0:
                continue
            symbol = f"KRW-{asset['currency']}"
            try:
                ticker = await self.get_ticker(symbol)
                current_price = ticker.get("trade_price", 0)
            except Exception:
                current_price = 0
            positions.append(Position(
                symbol=symbol,
                quantity=asset["balance"],
                avg_price=asset["avg_buy_price"],
                current_price=current_price,
            ))
        return positions

    async def get_ticker(self, symbol: str) -> dict:
        """단일 종목 현재 시세 조회"""
        try:
            price = await self._run_sync(pyupbit.get_current_price, symbol)
            if price is not None:
                return {"trade_price": float(price)}
        except Exception as e:
            logger.error(f"시세 조회 실패 ({symbol}): {e}")
        return {"trade_price": 0}

    async def get_tickers(self, symbols: list[str] | None = None) -> list[dict]:
        if symbols is None:
            symbols = await self.get_available_symbols()
        prices = await self._run_sync(pyupbit.get_current_price, symbols)
        if isinstance(prices, dict):
            return [
                {"symbol": k, "trade_price": v}
                for k, v in prices.items()
                if v is not None
            ]
        return []

    async def get_orderbook(self, symbol: str) -> dict:
        orderbook = await self._run_sync(pyupbit.get_orderbook, symbol)
        if orderbook and len(orderbook) > 0:
            return orderbook[0] if isinstance(orderbook, list) else orderbook
        return {}

    async def get_ohlcv(
        self, symbol: str, interval: str = "1m", count: int = 200
    ) -> pd.DataFrame:
        interval_map = {
            "1m": "minute1",
            "3m": "minute3",
            "5m": "minute5",
            "10m": "minute10",
            "15m": "minute15",
            "30m": "minute30",
            "1h": "minute60",
            "4h": "minute240",
            "1d": "day",
            "1w": "week",
            "1M": "month",
        }
        upbit_interval = interval_map.get(interval, "minute1")
        df = await self._run_sync(
            pyupbit.get_ohlcv, symbol, interval=upbit_interval, count=count
        )
        if df is None or df.empty:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume", "value"])
        df.index.name = "timestamp"
        return df

    async def get_available_symbols(self) -> list[str]:
        tickers = await self._run_sync(pyupbit.get_tickers, fiat="KRW")
        return tickers if tickers else []

    async def buy_market(self, symbol: str, amount_krw: float) -> OrderResult:
        self._ensure_authenticated()
        logger.trade(symbol, "buy", 0, amount_krw, "시장가 매수 주문")
        result = await self._run_sync(self._upbit.buy_market_order, symbol, amount_krw)
        if result is None or "error" in (result or {}):
            error_msg = result.get("error", {}).get("message", "Unknown") if result else "None"
            logger.error(f"매수 주문 실패: {symbol}", error_msg)
            raise RuntimeError(f"매수 주문 실패: {error_msg}")
        return OrderResult(
            order_id=result.get("uuid", ""),
            symbol=symbol,
            side="buy",
            price=float(result.get("price", 0) or 0),
            quantity=float(result.get("volume", 0) or 0),
            amount=amount_krw,
            status=result.get("state", "wait"),
            raw=result,
        )

    async def sell_market(self, symbol: str, quantity: float) -> OrderResult:
        self._ensure_authenticated()
        logger.trade(symbol, "sell", 0, 0, f"시장가 매도 주문 (수량: {quantity})")
        result = await self._run_sync(
            self._upbit.sell_market_order, symbol, quantity
        )
        if result is None or "error" in (result or {}):
            error_msg = result.get("error", {}).get("message", "Unknown") if result else "None"
            logger.error(f"매도 주문 실패: {symbol}", error_msg)
            raise RuntimeError(f"매도 주문 실패: {error_msg}")
        return OrderResult(
            order_id=result.get("uuid", ""),
            symbol=symbol,
            side="sell",
            price=float(result.get("price", 0) or 0),
            quantity=quantity,
            amount=float(result.get("price", 0) or 0) * quantity,
            status=result.get("state", "wait"),
            raw=result,
        )

    async def get_order(self, order_id: str) -> dict:
        self._ensure_authenticated()
        result = await self._run_sync(self._upbit.get_order, order_id)
        return result if result else {}

    async def cancel_order(self, order_id: str) -> dict:
        self._ensure_authenticated()
        result = await self._run_sync(self._upbit.cancel_order, order_id)
        return result if result else {}
