import asyncio
from datetime import datetime, date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.brokers.base import BaseBroker, Position
from backend.core.rule_engine import RuleEngine
from backend.config.settings import load_trading_rules
from backend.models.trade import Trade
from backend.models.signal import SignalLog
from backend.models.database import async_session
from backend.signals.base import Signal
from backend.utils.logger import logger


class TradingEngine:
    """
    핵심 매매 엔진.
    24시간 동작하며 규칙 엔진의 시그널에 따라 자동 매매를 수행합니다.
    뉴스/트위터 인터럽트 시그널도 처리합니다.
    """

    def __init__(self, broker: BaseBroker):
        self._broker = broker
        self._rule_engine = RuleEngine()
        self._running = False
        self._task: asyncio.Task | None = None
        self._positions: list[Position] = []
        self._ws_callbacks: list = []  # WebSocket 브로드캐스트 콜백

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def rule_engine(self) -> RuleEngine:
        return self._rule_engine

    def on_update(self, callback):
        """실시간 업데이트 콜백 등록 (WebSocket용)"""
        self._ws_callbacks.append(callback)

    async def _broadcast(self, event_type: str, data: dict):
        """WebSocket으로 이벤트 브로드캐스트"""
        message = {"type": event_type, "data": data, "timestamp": datetime.utcnow().isoformat()}
        for cb in self._ws_callbacks:
            try:
                await cb(message)
            except Exception:
                pass

    async def start(self):
        """매매 엔진 시작"""
        if self._running:
            logger.warning("매매 엔진이 이미 실행 중입니다.")
            return
        self._running = True
        self._task = asyncio.create_task(self._trading_loop())
        logger.info("매매 엔진 시작")
        await self._broadcast("engine_status", {"status": "running"})

    async def stop(self):
        """매매 엔진 중지"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("매매 엔진 중지")
        await self._broadcast("engine_status", {"status": "stopped"})

    async def _trading_loop(self):
        """메인 트레이딩 루프"""
        rules = self._rule_engine.rules
        cooldown = rules.get("trading", {}).get("cooldown_seconds", 60)

        while self._running:
            try:
                await self._evaluate_and_trade()
            except Exception as e:
                logger.error(f"트레이딩 루프 오류: {e}")
            await asyncio.sleep(cooldown)

    async def _evaluate_and_trade(self):
        """시장 데이터를 평가하고 매매 실행"""
        rules = self._rule_engine.rules
        trading_config = rules.get("trading", {})
        max_positions = trading_config.get("max_concurrent_positions", 5)

        # 현재 잔고 및 포지션 조회
        try:
            balance = await self._broker.get_balance()
            self._positions = await self._broker.get_positions()
        except Exception as e:
            logger.error(f"잔고 조회 실패: {e}")
            return

        available_krw = balance.get("krw", 0)

        # 기존 포지션 손절/익절 확인
        for pos in self._positions:
            try:
                ticker = await self._broker.get_ticker(pos.symbol)
                current_price = ticker.get("trade_price", 0)
                pos.current_price = current_price

                # 매도 잠금 날짜 체크
                if await self._is_sell_locked(pos.symbol):
                    continue

                if self._rule_engine.check_stop_loss(pos.avg_price, current_price):
                    logger.trade(
                        pos.symbol, "sell", current_price, 0,
                        f"손절 ({pos.pnl_pct:.2f}%)"
                    )
                    await self._execute_sell(pos, "손절")
                elif self._rule_engine.check_take_profit(pos.avg_price, current_price):
                    logger.trade(
                        pos.symbol, "sell", current_price, 0,
                        f"익절 ({pos.pnl_pct:.2f}%)"
                    )
                    await self._execute_sell(pos, "익절")
            except Exception as e:
                logger.error(f"포지션 평가 오류 ({pos.symbol}): {e}")

        # 새 매수 기회 탐색
        if len(self._positions) >= max_positions:
            return

        try:
            symbols = await self._broker.get_available_symbols()
        except Exception as e:
            logger.error(f"심볼 목록 조회 실패: {e}")
            return

        # 상위 거래량 종목 필터링
        tickers = await self._broker.get_tickers(symbols[:50])
        for ticker in tickers:
            symbol = ticker.get("symbol", "")
            volume_24h = ticker.get("acc_trade_price_24h", 0)

            if not self._rule_engine.passes_filters(symbol, volume_24h):
                continue

            # 이미 보유중인 종목 스킵
            if any(p.symbol == symbol for p in self._positions):
                continue

            try:
                df = await self._broker.get_ohlcv(symbol, interval="5m", count=200)
                current_price = ticker.get("trade_price", 0)
                result = self._rule_engine.evaluate(symbol, df, current_price)

                if result["action"] == "buy" and result["confidence"] >= 0.5:
                    position_size = available_krw * (
                        trading_config.get("max_position_size_pct", 10) / 100
                    )
                    min_order = trading_config.get("min_order_amount_krw", 5000)
                    if position_size >= min_order:
                        reason = " / ".join(result["reasons"])
                        await self._execute_buy(symbol, position_size, reason)
                        available_krw -= position_size

                        if len(self._positions) >= max_positions:
                            break
            except Exception as e:
                logger.error(f"종목 분석 오류 ({symbol}): {e}")

        # 포트폴리오 상태 브로드캐스트
        await self._broadcast("portfolio_update", {
            "krw": available_krw,
            "positions": [p.to_dict() for p in self._positions],
        })

    async def handle_interrupt_signal(self, signal: Signal):
        """뉴스/트위터 인터럽트 시그널 처리"""
        rules = self._rule_engine.rules
        interrupt_config = rules.get("interrupt", {})

        if not interrupt_config.get("enabled", True):
            return

        threshold_map = {
            "news": interrupt_config.get("news_confidence_threshold", 0.8),
            "twitter": interrupt_config.get("twitter_confidence_threshold", 0.9),
        }
        threshold = threshold_map.get(signal.source, 0.8)

        if signal.confidence < threshold:
            logger.info(
                f"인터럽트 시그널 무시 (신뢰도 부족: {signal.confidence:.0%} < {threshold:.0%})"
            )
            return

        # DB에 시그널 기록
        async with async_session() as session:
            sig_log = SignalLog(
                source=signal.source,
                action=signal.action,
                symbol=signal.symbol,
                confidence=signal.confidence,
                summary=signal.summary,
                raw_data=signal.raw_data,
            )
            session.add(sig_log)
            await session.commit()

        if not signal.symbol:
            logger.warning("인터럽트 시그널에 심볼이 없습니다.")
            return

        logger.info(
            f"인터럽트 시그널 처리: {signal.action} {signal.symbol} "
            f"(신뢰도: {signal.confidence:.0%}, 출처: {signal.source})"
        )

        try:
            if signal.action == "buy":
                balance = await self._broker.get_balance()
                max_pct = interrupt_config.get("max_interrupt_position_pct", 5)
                amount = balance.get("krw", 0) * (max_pct / 100)
                min_order = rules.get("trading", {}).get("min_order_amount_krw", 5000)
                if amount >= min_order:
                    await self._execute_buy(
                        signal.symbol, amount,
                        f"인터럽트({signal.source}): {signal.summary}"
                    )

            elif signal.action == "sell":
                pos = next(
                    (p for p in self._positions if p.symbol == signal.symbol),
                    None
                )
                if pos:
                    if await self._is_sell_locked(pos.symbol):
                        logger.info(f"인터럽트 매도 차단: {pos.symbol} - 매도 잠금 기간")
                    else:
                        await self._execute_sell(
                            pos,
                            f"인터럽트({signal.source}): {signal.summary}"
                        )
        except Exception as e:
            logger.error(f"인터럽트 시그널 실행 오류: {e}")

        await self._broadcast("interrupt_signal", signal.to_dict())

    async def _execute_buy(self, symbol: str, amount_krw: float, reason: str):
        """매수 실행 및 기록"""
        try:
            result = await self._broker.buy_market(symbol, amount_krw)
            async with async_session() as session:
                trade = Trade(
                    broker=self._broker.broker_type.value,
                    symbol=symbol,
                    side="buy",
                    price=result.price,
                    quantity=result.quantity,
                    amount_krw=amount_krw,
                    order_id=result.order_id,
                    status=result.status,
                    reason=reason,
                    signal_source="technical",
                )
                session.add(trade)
                await session.commit()
            logger.trade(symbol, "buy", result.price, amount_krw, reason)
            await self._broadcast("trade", trade.to_dict())
        except Exception as e:
            logger.error(f"매수 실행 실패 ({symbol}): {e}")

    async def _is_sell_locked(self, symbol: str) -> bool:
        """매도 잠금 날짜 이전에 매수한 포지션인지 확인"""
        lock_date_str = self._rule_engine.rules.get("trading", {}).get("sell_lock_before_date")
        if not lock_date_str:
            return False
        try:
            lock_date = datetime.strptime(lock_date_str, "%Y-%m-%d").date()
        except ValueError:
            return False

        # DB에서 해당 종목의 가장 최근 매수 기록 조회
        async with async_session() as session:
            result = await session.execute(
                select(Trade)
                .where(Trade.symbol == symbol, Trade.side == "buy")
                .order_by(Trade.created_at.desc())
                .limit(1)
            )
            last_buy = result.scalar_one_or_none()

        # DB에 매수 기록이 없으면 잠금 날짜 이전에 산 것으로 간주 (보호)
        if last_buy is None:
            logger.info(f"매도 잠금: {symbol} - DB에 매수 기록 없음 (잠금 날짜 이전 매수로 간주)")
            return True

        buy_date = last_buy.created_at.date() if last_buy.created_at else date.today()
        if buy_date <= lock_date:
            logger.info(
                f"매도 잠금: {symbol} - 매수일({buy_date}) <= 잠금일({lock_date})"
            )
            return True
        return False

    async def _execute_sell(self, position: Position, reason: str):
        """매도 실행 및 기록"""
        try:
            result = await self._broker.sell_market(position.symbol, position.quantity)
            pnl_pct = position.pnl_pct
            pnl = position.pnl

            async with async_session() as session:
                trade = Trade(
                    broker=self._broker.broker_type.value,
                    symbol=position.symbol,
                    side="sell",
                    price=result.price or position.current_price,
                    quantity=position.quantity,
                    amount_krw=result.amount,
                    order_id=result.order_id,
                    status=result.status,
                    reason=reason,
                    signal_source="technical",
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                )
                session.add(trade)
                await session.commit()
            logger.trade(
                position.symbol, "sell",
                position.current_price, result.amount,
                f"{reason} (P&L: {pnl_pct:+.2f}%)"
            )
            await self._broadcast("trade", trade.to_dict())
        except Exception as e:
            logger.error(f"매도 실행 실패 ({position.symbol}): {e}")

    async def get_status(self) -> dict:
        """엔진 상태 조회"""
        return {
            "running": self._running,
            "positions_count": len(self._positions),
            "positions": [p.to_dict() for p in self._positions],
            "rules_version": self._rule_engine.rules.get("version", "unknown"),
        }
