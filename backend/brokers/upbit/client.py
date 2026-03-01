import asyncio
from functools import partial

import httpx
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

    async def get_full_tickers(self, symbols: list[str] | None = None) -> list[dict]:
        """Upbit REST API를 통해 전체 티커 데이터 조회 (거래대금 포함)"""
        if symbols is None:
            symbols = await self.get_available_symbols()
        if not symbols:
            return []

        markets = ",".join(symbols)
        url = f"https://api.upbit.com/v1/ticker?markets={markets}"

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        results = []
        for item in data:
            results.append({
                "symbol": item.get("market", ""),
                "trade_price": float(item.get("trade_price", 0)),
                "acc_trade_price_24h": float(item.get("acc_trade_price_24h", 0)),
                "acc_trade_volume_24h": float(item.get("acc_trade_volume_24h", 0)),
                "signed_change_rate": float(item.get("signed_change_rate", 0)),
            })
        return results

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

    async def get_1h_volumes(self, symbols: list[str]) -> dict[str, float]:
        """여러 심볼의 최근 1시간 거래대금(KRW)을 조회.
        Upbit REST API 직접 호출. 실패한 심볼은 최대 10회 재시도.
        """
        result: dict[str, float] = {}

        async def _fetch_one(client: httpx.AsyncClient, symbol: str) -> tuple[str, float]:
            try:
                resp = await client.get(
                    "https://api.upbit.com/v1/candles/minutes/60",
                    params={"market": symbol, "count": 1},
                )
                resp.raise_for_status()
                data = resp.json()
                if data and len(data) > 0:
                    return symbol, float(data[0].get("candle_acc_trade_price", 0))
            except Exception:
                pass
            return symbol, 0.0

        async with httpx.AsyncClient(timeout=10) as client:
            remaining = list(symbols)
            for attempt in range(10):
                batch_size = 3
                failed: list[str] = []
                for i in range(0, len(remaining), batch_size):
                    if i > 0 or attempt > 0:
                        await asyncio.sleep(1.0)
                    batch = remaining[i:i + batch_size]
                    tasks = [_fetch_one(client, s) for s in batch]
                    for sym, vol in await asyncio.gather(*tasks):
                        if vol > 0:
                            result[sym] = vol
                        else:
                            failed.append(sym)
                if not failed:
                    break
                remaining = failed
                await asyncio.sleep(2.0)

            # 최종 실패 심볼은 0으로 기록
            for sym in symbols:
                if sym not in result:
                    result[sym] = 0.0
        return result

    async def get_ohlcv_batch(
        self, symbols: list[str], interval: str = "15m", count: int = 200
    ) -> dict[str, pd.DataFrame]:
        """여러 심볼의 OHLCV를 httpx로 배치 조회 (rate limit 대응, 재시도 포함)."""
        interval_map = {
            "1m": 1, "3m": 3, "5m": 5, "10m": 10,
            "15m": 15, "30m": 30, "1h": 60, "4h": 240,
        }
        minutes = interval_map.get(interval, 15)
        url = f"https://api.upbit.com/v1/candles/minutes/{minutes}"
        result: dict[str, pd.DataFrame] = {}
        empty = pd.DataFrame(columns=["open", "high", "low", "close", "volume", "value"])

        async def _fetch(client: httpx.AsyncClient, symbol: str) -> tuple[str, pd.DataFrame]:
            try:
                resp = await client.get(url, params={"market": symbol, "count": count})
                resp.raise_for_status()
                data = resp.json()
                if not data:
                    return symbol, empty.copy()
                rows = []
                for c in data:
                    rows.append({
                        "open": float(c.get("opening_price", 0)),
                        "high": float(c.get("high_price", 0)),
                        "low": float(c.get("low_price", 0)),
                        "close": float(c.get("trade_price", 0)),
                        "volume": float(c.get("candle_acc_trade_volume", 0)),
                        "value": float(c.get("candle_acc_trade_price", 0)),
                    })
                df = pd.DataFrame(rows[::-1])  # 시간순 정렬 (API는 최신→과거)
                return symbol, df
            except Exception:
                return symbol, empty.copy()

        async with httpx.AsyncClient(timeout=15) as client:
            remaining = list(symbols)
            for attempt in range(3):
                failed: list[str] = []
                batch_size = 3
                for i in range(0, len(remaining), batch_size):
                    if i > 0 or attempt > 0:
                        await asyncio.sleep(0.5)
                    batch = remaining[i:i + batch_size]
                    tasks = [_fetch(client, s) for s in batch]
                    for sym, df in await asyncio.gather(*tasks):
                        if not df.empty:
                            result[sym] = df
                        else:
                            failed.append(sym)
                if not failed:
                    break
                remaining = failed
                await asyncio.sleep(1.0)

            for sym in symbols:
                if sym not in result:
                    result[sym] = empty.copy()
        return result

    async def get_available_symbols(self) -> list[str]:
        tickers = await self._run_sync(pyupbit.get_tickers, fiat="KRW")
        return tickers if tickers else []

    async def _wait_order_done(self, order_id: str, max_retries: int = 10, delay: float = 0.5) -> dict:
        """주문 체결 완료 대기 후 상세 정보 반환"""
        for _ in range(max_retries):
            await asyncio.sleep(delay)
            detail = await self._run_sync(self._upbit.get_order, order_id)
            if detail and detail.get("state") in ("done", "cancel"):
                return detail
        return {}

    async def buy_market(self, symbol: str, amount_krw: float) -> OrderResult:
        self._ensure_authenticated()
        logger.trade(symbol, "buy", 0, amount_krw, "시장가 매수 주문")
        result = await self._run_sync(self._upbit.buy_market_order, symbol, amount_krw)
        if result is None or "error" in (result or {}):
            error_msg = result.get("error", {}).get("message", "Unknown") if result else "None"
            logger.error(f"매수 주문 실패: {symbol}", error_msg)
            raise RuntimeError(f"매수 주문 실패: {error_msg}")

        order_id = result.get("uuid", "")

        # 체결 대기 후 실제 체결 가격/수량 조회
        filled_price = 0.0
        filled_quantity = 0.0
        detail = await self._wait_order_done(order_id)
        if detail:
            filled_quantity = float(detail.get("executed_volume", 0) or 0)
            trades = detail.get("trades", [])
            if trades:
                total_funds = sum(float(t.get("funds", 0) or 0) for t in trades)
                if filled_quantity > 0:
                    filled_price = total_funds / filled_quantity
            elif filled_quantity > 0:
                filled_price = amount_krw / filled_quantity

        return OrderResult(
            order_id=order_id,
            symbol=symbol,
            side="buy",
            price=filled_price,
            quantity=filled_quantity,
            amount=amount_krw,
            status="done" if filled_quantity > 0 else result.get("state", "wait"),
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

        order_id = result.get("uuid", "")

        # 체결 대기 후 실제 체결 금액 조회
        filled_price = 0.0
        filled_amount = 0.0
        detail = await self._wait_order_done(order_id)
        if detail:
            executed_vol = float(detail.get("executed_volume", 0) or 0)
            trades = detail.get("trades", [])
            if trades:
                filled_amount = sum(float(t.get("funds", 0) or 0) for t in trades)
                if executed_vol > 0:
                    filled_price = filled_amount / executed_vol
            elif executed_vol > 0:
                # trades 정보 없으면 현재가로 추정
                try:
                    ticker = await self.get_ticker(symbol)
                    filled_price = ticker.get("trade_price", 0)
                    filled_amount = filled_price * executed_vol
                except Exception:
                    pass

        return OrderResult(
            order_id=order_id,
            symbol=symbol,
            side="sell",
            price=filled_price,
            quantity=quantity,
            amount=filled_amount,
            status="done" if filled_amount > 0 else result.get("state", "wait"),
            raw=result,
        )

    async def get_order(self, order_id: str) -> dict:
        self._ensure_authenticated()
        result = await self._run_sync(self._upbit.get_order, order_id)
        return result if result else {}

    async def get_closed_orders(self, from_date: str | None = None) -> list[dict]:
        """업비트 API에서 체결 완료된 주문 내역 조회 (페이지네이션 포함)"""
        self._ensure_authenticated()
        import jwt as pyjwt
        import hashlib
        import uuid as uuid_mod
        from urllib.parse import urlencode, unquote

        all_orders = []
        seen_uuids: set[str] = set()
        current_start = from_date

        for _ in range(20):  # max 2000 orders
            params: dict = {"state": "done", "limit": 100, "order_by": "asc"}
            if current_start:
                params["start_time"] = current_start

            query_string = unquote(urlencode(params, doseq=True)).encode("utf-8")
            m = hashlib.sha512()
            m.update(query_string)

            payload = {
                "access_key": settings.upbit_access_key,
                "nonce": str(uuid_mod.uuid4()),
                "query_hash": m.hexdigest(),
                "query_hash_alg": "SHA512",
            }
            token = pyjwt.encode(payload, settings.upbit_secret_key)

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.upbit.com/v1/orders/closed",
                    params=params,
                    headers={"Authorization": f"Bearer {token}"},
                )
                resp.raise_for_status()
                data = resp.json()

            if not isinstance(data, list) or not data:
                break

            new_count = 0
            for o in data:
                uid = o.get("uuid", "")
                if uid and uid not in seen_uuids:
                    seen_uuids.add(uid)
                    all_orders.append(o)
                    new_count += 1

            if len(data) < 100 or new_count == 0:
                break

            current_start = data[-1].get("created_at", "")
            if not current_start:
                break

        return all_orders

    async def cancel_order(self, order_id: str) -> dict:
        self._ensure_authenticated()
        result = await self._run_sync(self._upbit.cancel_order, order_id)
        return result if result else {}
