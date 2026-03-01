import asyncio
import time
from collections import defaultdict
from datetime import datetime, date

from sqlalchemy import select, func

from backend.brokers.base import BaseBroker, Position
from backend.core.rule_engine import RuleEngine
from backend.core.managed_position import ManagedPosition, EntrySource
from backend.config.settings import load_trading_rules
from backend.models.trade import Trade
from backend.models.signal import SignalLog
from backend.models.database import async_session
from backend.signals.base import Signal
from backend.utils.logger import logger

# 업비트 수수료율 (0.05%)
UPBIT_FEE_RATE = 0.0005

# 먼지(dust) 임계값 — 최소 주문 금액(5000원) 미만은 매도 불가이므로 무시
DUST_THRESHOLD_KRW = 5000


class TradingEngine:
    """
    핵심 매매 엔진.
    - 듀얼 루프: 진입 탐색 (60초) + 포지션 모니터링 (15초)
    - 타겟 코인: 거래대금 상위 15개 (1시간 캐시)
    - 기술적 진입: 15분봉 눌림목 전략 (200EMA + 20EMA + RSI)
    - 이벤트 진입: Gemini 키워드 점수 >= +4
    - 청산: 기술적/이벤트 별도 규칙 (부분매도 지원)
    """

    def __init__(self, broker: BaseBroker):
        self._broker = broker
        self._rule_engine = RuleEngine()
        self._running = False
        self._entry_task: asyncio.Task | None = None
        self._monitor_task: asyncio.Task | None = None
        self._positions: list[Position] = []
        self._managed_positions: dict[str, ManagedPosition] = {}
        self._ws_callbacks: list = []

        # 타겟 코인 캐시
        self._target_symbols: list[str] = []
        self._target_symbols_updated: float = 0.0

        # 킬 스위치: 진입 일시정지 만료 시각 (epoch)
        self._entry_paused_until: float = 0.0

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def rule_engine(self) -> RuleEngine:
        return self._rule_engine

    def on_update(self, callback):
        self._ws_callbacks.append(callback)

    async def _broadcast(self, event_type: str, data: dict):
        message = {"type": event_type, "data": data, "timestamp": datetime.utcnow().isoformat()}
        for cb in self._ws_callbacks:
            try:
                await cb(message)
            except Exception:
                pass

    # ─── 시작/중지 ───

    async def start(self):
        if self._running:
            logger.warning("매매 엔진이 이미 실행 중입니다.")
            return

        # Trade DB에서 봇 포지션 복원 (재시작 대응)
        await self._reconstruct_managed_positions()

        self._running = True
        self._entry_task = asyncio.create_task(self._entry_loop())
        self._monitor_task = asyncio.create_task(self._position_monitor_loop())
        logger.info("매매 엔진 시작 (진입 루프 + 포지션 모니터링)")
        await self._broadcast("engine_status", {"status": "running"})

    async def stop(self):
        self._running = False
        for task in [self._entry_task, self._monitor_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        logger.info("매매 엔진 중지")
        await self._broadcast("engine_status", {"status": "stopped"})

    # ─── 타겟 코인 필터링 (Rule 1) ───

    async def _refresh_target_symbols(self):
        """1시간 거래대금 상위 종목 갱신 (1시간 캐시)"""
        rules = self._rule_engine.rules
        target_config = rules.get("target_coins", {})
        top_n = target_config.get("top_n", 15)
        refresh_sec = target_config.get("refresh_interval_seconds", 3600)

        now = time.time()
        if self._target_symbols and (now - self._target_symbols_updated < refresh_sec):
            return

        try:
            all_symbols = await self._broker.get_available_symbols()
            full_tickers = await self._broker.get_full_tickers(all_symbols)

            # 최소 가격 필터
            min_price = rules.get("filters", {}).get("min_price_krw", 1000)
            price_map = {t["symbol"]: t.get("trade_price", 0) for t in full_tickers}

            # 24h 거래대금 상위 50개를 먼저 추린 후, 1h 거래대금으로 재정렬
            full_tickers.sort(
                key=lambda t: t.get("acc_trade_price_24h", 0), reverse=True
            )
            pre_filter = [t["symbol"] for t in full_tickers[:50]]

            vol_1h = await self._broker.get_1h_volumes(pre_filter)

            ranked = sorted(pre_filter, key=lambda s: vol_1h.get(s, 0), reverse=True)

            self._target_symbols = [
                s for s in ranked
                if self._rule_engine.passes_filters(s)
                and price_map.get(s, 0) >= min_price
                and vol_1h.get(s, 0) > 0
            ][:top_n]
            self._target_symbols_updated = now

            symbols_short = [s.replace("KRW-", "") for s in self._target_symbols]
            logger.info(f"타겟 코인 갱신 (1h Top {top_n}): {', '.join(symbols_short)}")
        except Exception as e:
            logger.error(f"타겟 코인 갱신 실패: {e}")

    # ─── 진입 루프 (Rule 2: 기술적 진입) ───

    async def _entry_loop(self):
        """신규 진입 탐색 (60초 간격), 킬 스위치 발동 시 일시정지"""
        rules = self._rule_engine.rules
        cooldown = rules.get("trading", {}).get("cooldown_seconds", 60)

        while self._running:
            # 킬 스위치 일시정지 체크
            now = time.time()
            if now < self._entry_paused_until:
                remaining = int(self._entry_paused_until - now)
                logger.info(
                    f"진입 일시정지 중 (잔여: {remaining // 60}분 {remaining % 60}초)"
                )
                await asyncio.sleep(cooldown)
                continue

            try:
                await self._evaluate_entries()
            except Exception as e:
                logger.error(f"진입 평가 루프 오류: {e}")
            await asyncio.sleep(cooldown)

    async def _evaluate_entries(self):
        """타겟 코인을 스캔하여 풀백 진입 조건 확인"""
        rules = self._rule_engine.rules
        trading = rules.get("trading", {})
        tech = rules.get("technical_strategy", {})
        max_positions = trading.get("max_concurrent_positions", 5)
        max_pos_pct = trading.get("max_position_size_pct", 10)
        min_order = trading.get("min_order_amount_krw", 5000)
        candle_interval = tech.get("candle_interval", "15m")
        candle_count = tech.get("candle_count", 200)

        # 현재 잔고 조회
        try:
            balance = await self._broker.get_balance()
        except Exception as e:
            logger.error(f"잔고 조회 실패: {e}")
            return

        available_krw = balance.get("krw", 0)

        # 포지션 슬롯 확인
        if len(self._managed_positions) >= max_positions:
            return

        # 타겟 코인 목록 갱신
        await self._refresh_target_symbols()

        for rank, symbol in enumerate(self._target_symbols, start=1):
            # 이미 보유중
            if symbol in self._managed_positions:
                continue

            try:
                df = await self._broker.get_ohlcv(
                    symbol, interval=candle_interval, count=candle_count
                )
                ticker = await self._broker.get_ticker(symbol)
                current_price = ticker.get("trade_price", 0)

                result = self._rule_engine.evaluate(symbol, df, current_price)

                if result["action"] == "buy" and result["confidence"] >= 0.5:
                    position_size = available_krw * (max_pos_pct / 100)
                    if position_size >= min_order:
                        await self._execute_buy(
                            symbol, position_size,
                            f"거래량 {rank}위 풀백 진입",
                            entry_source=EntrySource.TECHNICAL,
                        )
                        available_krw -= position_size

                        if len(self._managed_positions) >= max_positions:
                            break

            except Exception as e:
                logger.error(f"종목 분석 오류 ({symbol}): {e}")

    # ─── 포지션 모니터링 루프 (15초 간격) ───

    async def _position_monitor_loop(self):
        """포지션 청산 조건 체크 (15초 간격)"""
        rules = self._rule_engine.rules
        interval = rules.get("trading", {}).get("position_check_interval_seconds", 15)

        while self._running:
            try:
                self._positions = await self._broker.get_positions()
                await self._check_position_exits()
            except Exception as e:
                logger.error(f"포지션 모니터링 오류: {e}")
            await asyncio.sleep(interval)

    async def _check_position_exits(self):
        """봇이 관리 중인 포지션의 청산 조건 확인"""
        # 브로커에 없는 managed position 정리 (Upbit에서 사라진 심볼)
        broker_symbols = {p.symbol for p in self._positions}
        stale = [s for s in self._managed_positions if s not in broker_symbols]
        for s in stale:
            logger.info(f"봇 포지션 정리: {s} - 브로커에서 사라짐")
            self._managed_positions.pop(s, None)

        for pos in self._positions:
            try:
                managed = self._managed_positions.get(pos.symbol)

                if managed is None:
                    # 먼지 포지션 무시 (매도 불가능한 극소량)
                    if pos.quantity * pos.current_price < DUST_THRESHOLD_KRW:
                        continue

                    # 미추적 포지션: 잠금일 이후 매수분만 분리하여 관리
                    post_lock = await self._calc_post_lock_position(pos.symbol, pos.quantity)
                    if post_lock is None:
                        # 잠금일 미설정 → Upbit 전체 데이터로 등록
                        if await self._is_bought_before_lock(pos.symbol):
                            continue
                        post_lock_qty, post_lock_avg = pos.quantity, pos.avg_price
                    else:
                        post_lock_qty, post_lock_avg = post_lock

                    # 분리된 수량도 먼지인지 재확인
                    if post_lock_qty * pos.current_price < DUST_THRESHOLD_KRW:
                        continue

                    managed = ManagedPosition(
                        position=pos,
                        entry_source=EntrySource.TECHNICAL,
                        original_quantity=post_lock_qty,
                        bot_quantity=post_lock_qty,
                        bot_avg_price=post_lock_avg,
                        current_price=pos.current_price,
                    )
                    self._managed_positions[pos.symbol] = managed
                    logger.info(
                        f"잠금일 이후 포지션 등록: {pos.symbol} | "
                        f"수량={post_lock_qty:.8f} (Upbit 전체={pos.quantity:.8f}) | "
                        f"평균가={post_lock_avg:,.0f}"
                    )

                ticker = await self._broker.get_ticker(pos.symbol)
                current_price = ticker.get("trade_price", 0)

                if current_price <= 0:
                    logger.warning(f"현재가 조회 실패 ({pos.symbol}) - 청산 체크 건너뜀")
                    continue

                # Upbit 실제 보유량이 bot_quantity보다 적으면 조정 (수동 매도 대응)
                if pos.quantity < managed.bot_quantity:
                    if pos.quantity <= 0:
                        logger.info(f"수동 매도 감지: {pos.symbol} - Upbit 잔량 0 → 관리 제거")
                        self._managed_positions.pop(pos.symbol, None)
                        continue
                    logger.info(
                        f"수동 매도 감지: {pos.symbol} - bot_quantity {managed.bot_quantity:.8f} → "
                        f"{pos.quantity:.8f} (Upbit 실제 잔량으로 조정)"
                    )
                    managed.bot_quantity = pos.quantity

                # 먼지 포지션 제거 (매도 후 극소량 잔여)
                if managed.bot_quantity * current_price < DUST_THRESHOLD_KRW:
                    logger.info(f"먼지 포지션 제거: {pos.symbol} - {managed.bot_quantity:.8f}개 (≈{managed.bot_quantity * current_price:.0f}원)")
                    self._managed_positions.pop(pos.symbol, None)
                    continue

                # 현재가만 갱신 (수량/평균가는 봇 자체 데이터 유지)
                managed.update_price(current_price)

                if managed.entry_source == EntrySource.TECHNICAL:
                    await self._check_technical_exit(managed)
                elif managed.entry_source == EntrySource.EVENT:
                    await self._check_event_exit(managed)

            except Exception as e:
                logger.error(f"포지션 평가 오류 ({pos.symbol}): {e}")

        # 포트폴리오 상태 브로드캐스트
        await self._broadcast("portfolio_update", {
            "positions": [
                mp.to_dict() for mp in self._managed_positions.values()
            ],
        })

    # ─── Rule 2 기술적 청산 ───

    async def _check_technical_exit(self, mp: ManagedPosition):
        """기술적 진입 포지션 청산 조건 — 반익반본 + 무제한 트레일링(Moonbag)"""
        rules = self._rule_engine.rules
        exit_cfg = rules.get("technical_strategy", {}).get("exit", {})
        sl = exit_cfg.get("stop_loss_pct", 1.0)
        tp1 = exit_cfg.get("tp1_pct", 1.5)
        tp1_ratio = exit_cfg.get("tp1_sell_ratio", 0.5)
        moonbag_trail = exit_cfg.get("moonbag_trail_pct", 1.0)

        pnl = mp.pnl_pct
        # 왕복 수수료 (매수 0.05% + 매도 0.05% = 0.10%)
        breakeven_fee = UPBIT_FEE_RATE * 2 * 100

        if mp.first_tp_done:
            # ── 1차 익절 완료 후: 본절 로스 + 무제한 트레일링 ──

            # 안전장치: 수수료 포함 본전(+0.10%) 이하 → 전량 매도
            if pnl <= breakeven_fee:
                await self._execute_full_sell(
                    mp, f"본절 탈출 ({pnl:+.2f}% ≤ 수수료 {breakeven_fee:.2f}%, 1차 익절 후)"
                )
                return

            # 무제한 트레일링: 고점 대비 moonbag_trail% 하락 시 전량 매도
            if mp.peak_pnl_pct - pnl >= moonbag_trail:
                await self._execute_full_sell(
                    mp,
                    f"트레일링 스탑 (고점:{mp.peak_pnl_pct:+.2f}% → 현재:{pnl:+.2f}%, "
                    f"하락폭:{mp.peak_pnl_pct - pnl:.2f}%)"
                )
                return
        else:
            # ── 1차 익절 전: 손절 + 1차 익절만 ──

            # 칼손절
            if pnl <= -sl:
                await self._execute_full_sell(mp, f"기술 손절 ({pnl:+.2f}%)")
                return

            # 1차 익절: tp1% 도달 → 50% 매도, 이후 무제한 트레일링 시작
            if pnl >= tp1:
                await self._execute_partial_sell(
                    mp, tp1_ratio, f"기술 1차 익절 {int(tp1_ratio*100)}% ({pnl:+.2f}%)"
                )
                mp.first_tp_done = True
                # peak_pnl_pct는 update_price에서 이미 갱신되므로 별도 설정 불필요
                return

    # ─── Rule 4 이벤트 청산 ───

    async def _check_event_exit(self, mp: ManagedPosition):
        """이벤트 진입 포지션 청산 조건 (Rule 4)"""
        rules = self._rule_engine.rules
        exit_cfg = rules.get("event_strategy", {}).get("exit", {})
        sl = exit_cfg.get("stop_loss_pct", 2.0)
        tp1 = exit_cfg.get("tp1_pct", 3.0)
        tp1_ratio = exit_cfg.get("tp1_sell_ratio", 0.5)
        moonbag_trail = exit_cfg.get("moonbag_trail_pct", 1.0)

        pnl = mp.pnl_pct
        breakeven_fee = UPBIT_FEE_RATE * 2 * 100

        if mp.first_tp_done:
            # ── 1차 익절 후: 본절 로스 + 무제한 트레일링 ──
            if pnl <= breakeven_fee:
                await self._execute_full_sell(
                    mp, f"본절 탈출 ({pnl:+.2f}% ≤ 수수료 {breakeven_fee:.2f}%, 이벤트 1차 익절 후)"
                )
                return

            if mp.peak_pnl_pct - pnl >= moonbag_trail:
                await self._execute_full_sell(
                    mp,
                    f"이벤트 트레일링 (고점:{mp.peak_pnl_pct:+.2f}% → 현재:{pnl:+.2f}%, "
                    f"하락폭:{mp.peak_pnl_pct - pnl:.2f}%)"
                )
                return
        else:
            # ── 1차 익절 전: 손절 + 1차 익절만 ──
            if pnl <= -sl:
                await self._execute_full_sell(mp, f"이벤트 손절 ({pnl:+.2f}%)")
                return

            if pnl >= tp1:
                await self._execute_partial_sell(
                    mp, tp1_ratio, f"이벤트 1차 익절 {int(tp1_ratio*100)}% ({pnl:+.2f}%)"
                )
                mp.first_tp_done = True
                return

    # ─── 이벤트 시그널 처리 (Rule 4 진입) ───

    async def handle_interrupt_signal(self, signal: Signal):
        """뉴스/트위터 이벤트 시그널 처리 (점수 + scope 기반)"""
        # DB에 시그널 기록 (news 소스는 news_monitor에서 직접 저장하므로 건너뜀)
        if signal.source != "news":
            async with async_session() as session:
                sig_log = SignalLog(
                    source=signal.source,
                    action=signal.action,
                    symbol=signal.symbol,
                    confidence=signal.confidence,
                    summary=signal.summary,
                    url=signal.url,
                    raw_data=signal.raw_data,
                )
                session.add(sig_log)
                await session.commit()

        score = signal.score
        rules = self._rule_engine.rules
        min_order = rules.get("trading", {}).get("min_order_amount_krw", 5000)

        logger.info(
            f"시그널 수신: scope={signal.scope}, symbol={signal.symbol}, "
            f"score={score:+d}, 출처={signal.source}"
        )

        try:
            if signal.scope == "macro":
                await self._handle_macro_signal(signal, rules, min_order)
            else:
                await self._handle_ticker_signal(signal, rules, min_order)
        except Exception as e:
            logger.error(f"시그널 실행 오류: {e}")

        await self._broadcast("interrupt_signal", signal.to_dict())

    async def _handle_macro_signal(
        self, signal: Signal, rules: dict, min_order: int
    ):
        """매크로(거시경제) 시그널 처리"""
        score = signal.score
        macro_cfg = rules.get("macro_strategy", {})
        buy_threshold = macro_cfg.get("buy_score_threshold", 4)
        sell_threshold = macro_cfg.get("sell_score_threshold", -4)
        buy_pct = macro_cfg.get("buy_position_size_pct", 20)
        buy_symbol = macro_cfg.get("buy_symbol", "KRW-BTC")

        if score >= buy_threshold:
            # 매크로 호재: BTC 시드 20% 매수
            if buy_symbol in self._managed_positions:
                logger.info(f"매크로 매수 스킵: {buy_symbol} 이미 보유 중")
            else:
                balance = await self._broker.get_balance()
                amount = balance.get("krw", 0) * (buy_pct / 100)
                if amount >= min_order:
                    await self._execute_buy(
                        buy_symbol, amount,
                        f"매크로 호재 매수 (score:{score:+d}, {signal.summary})",
                        entry_source=EntrySource.EVENT,
                    )

        elif score <= sell_threshold:
            # 매크로 악재: 킬 스위치 발동
            await self._execute_kill_switch(
                f"매크로 악재 (score:{score:+d}, {signal.summary})"
            )

    async def _handle_ticker_signal(
        self, signal: Signal, rules: dict, min_order: int
    ):
        """개별 코인 시그널 처리 (기존 이벤트 로직)"""
        if not signal.symbol:
            logger.warning("이벤트 시그널에 심볼이 없습니다.")
            return

        score = signal.score
        event_cfg = rules.get("event_strategy", {})
        buy_pct = event_cfg.get("buy_position_size_pct", 10)

        # 거래대금 상위 N개 코인은 낮은 임계값, 그 외는 높은 임계값
        is_target = signal.symbol in self._target_symbols
        if is_target:
            buy_threshold = event_cfg.get("buy_score_threshold", 5)
            sell_threshold = event_cfg.get("sell_score_threshold", -5)
        else:
            buy_threshold = event_cfg.get("non_target_buy_score_threshold", 25)
            sell_threshold = event_cfg.get("non_target_sell_score_threshold", -25)

        logger.debug(
            f"시그널 임계값: {signal.symbol} "
            f"({'타겟' if is_target else '비타겟'}) "
            f"buy>={buy_threshold}, sell<={sell_threshold}"
        )

        if score >= buy_threshold:
            if signal.symbol in self._managed_positions:
                logger.info(f"이벤트 매수 스킵: {signal.symbol} 이미 보유 중")
            else:
                balance = await self._broker.get_balance()
                amount = balance.get("krw", 0) * (buy_pct / 100)
                if amount >= min_order:
                    await self._execute_buy(
                        signal.symbol, amount,
                        f"이벤트 매수 (score:{score:+d}, {signal.summary})",
                        entry_source=EntrySource.EVENT,
                    )

        elif score <= sell_threshold:
            managed = self._managed_positions.get(signal.symbol)
            if managed:
                if await self._is_sell_locked(signal.symbol):
                    logger.info(f"이벤트 매도 차단: {signal.symbol} - 매도 잠금 기간")
                else:
                    await self._execute_full_sell(
                        managed, f"이벤트 긴급매도 (score:{score:+d})"
                    )

    # ─── 킬 스위치 ───

    async def _execute_kill_switch(self, reason: str):
        """킬 스위치: 모든 포지션 전량 매도 + 진입 2시간 정지"""
        logger.warning(f"킬 스위치 발동: {reason}")

        # 1. 모든 보유 포지션 즉시 전량 매도
        symbols = list(self._managed_positions.keys())
        for symbol in symbols:
            mp = self._managed_positions.get(symbol)
            if mp:
                await self._execute_full_sell(mp, f"킬스위치 강제매도: {reason}")

        # 2. 진입 루프 일시정지
        pause_sec = self._rule_engine.rules.get(
            "macro_strategy", {}
        ).get("pause_duration_seconds", 7200)
        self._entry_paused_until = time.time() + pause_sec

        await self._broadcast("kill_switch", {
            "reason": reason,
            "pause_minutes": pause_sec // 60,
        })
        logger.warning(f"킬 스위치: {pause_sec // 60}분간 진입 일시정지")

    # ─── 매수/매도 실행 ───

    async def _execute_buy(
        self, symbol: str, amount_krw: float, reason: str,
        entry_source: EntrySource = EntrySource.TECHNICAL,
    ):
        """매수 실행 및 ManagedPosition 등록"""
        try:
            result = await self._broker.buy_market(symbol, amount_krw)
            buy_fee = amount_krw * UPBIT_FEE_RATE

            # ManagedPosition 등록 (봇 전용 데이터로 관리)
            buy_price = result.price if result.price else 0
            pos = Position(
                symbol=symbol,
                quantity=result.quantity,
                avg_price=buy_price,
                current_price=buy_price,
            )
            self._managed_positions[symbol] = ManagedPosition(
                position=pos,
                entry_source=entry_source,
                original_quantity=result.quantity,
                bot_quantity=result.quantity,
                bot_avg_price=buy_price,
                current_price=buy_price,
            )

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
                    signal_source=entry_source.value,
                    fee_krw=buy_fee,
                )
                session.add(trade)
                await session.commit()

            logger.trade(symbol, "buy", result.price, amount_krw, reason)
            await self._broadcast("trade", trade.to_dict())

        except Exception as e:
            logger.error(f"매수 실행 실패 ({symbol}): {e}")

    async def _execute_full_sell(self, mp: ManagedPosition, reason: str):
        """봇 보유 수량 전량 매도 + managed position 제거"""
        try:
            # Upbit 실제 보유량 확인하여 초과 방지
            try:
                positions = await self._broker.get_positions()
                upbit_qty = next((p.quantity for p in positions if p.symbol == mp.symbol), 0)
                if upbit_qty < mp.bot_quantity:
                    logger.warning(
                        f"Upbit 잔량({upbit_qty:.8f}) < bot_quantity({mp.bot_quantity:.8f}) "
                        f"→ 실제 잔량으로 매도 ({mp.symbol})"
                    )
                    mp.bot_quantity = upbit_qty
                if mp.bot_quantity <= 0:
                    logger.info(f"매도 스킵: {mp.symbol} - 보유량 0 → 관리 제거")
                    self._managed_positions.pop(mp.symbol, None)
                    return
            except Exception:
                pass  # 조회 실패 시 기존 bot_quantity로 시도

            result = await self._broker.sell_market(mp.symbol, mp.bot_quantity)
            sell_amount = result.amount
            sell_fee = sell_amount * UPBIT_FEE_RATE
            buy_fee_portion = mp.bot_avg_price * mp.bot_quantity * UPBIT_FEE_RATE
            gross_pnl = (mp.current_price - mp.bot_avg_price) * mp.bot_quantity
            net_pnl = gross_pnl - buy_fee_portion - sell_fee
            cost_basis = mp.bot_avg_price * mp.bot_quantity
            net_pnl_pct = (net_pnl / cost_basis * 100) if cost_basis > 0 else 0.0

            async with async_session() as session:
                trade = Trade(
                    broker=self._broker.broker_type.value,
                    symbol=mp.symbol,
                    side="sell",
                    price=result.price or mp.current_price,
                    quantity=mp.bot_quantity,
                    amount_krw=sell_amount,
                    order_id=result.order_id,
                    status=result.status,
                    reason=reason,
                    signal_source=mp.entry_source.value,
                    fee_krw=sell_fee,
                    pnl=net_pnl,
                    pnl_pct=net_pnl_pct,
                )
                session.add(trade)
                await session.commit()

            logger.trade(
                mp.symbol, "sell", mp.current_price, sell_amount,
                f"{reason} (P&L: {net_pnl_pct:+.2f}%, 수수료: {sell_fee + buy_fee_portion:.0f}원)"
            )
            await self._broadcast("trade", trade.to_dict())

            self._managed_positions.pop(mp.symbol, None)

        except Exception as e:
            logger.error(f"전량매도 실패 ({mp.symbol}): {e}")

    async def _execute_partial_sell(
        self, mp: ManagedPosition, sell_pct: float, reason: str
    ):
        """봇 보유 수량의 부분 매도 (sell_pct: 0.0~1.0)"""
        # Upbit 실제 보유량 확인하여 bot_quantity 조정
        try:
            positions = await self._broker.get_positions()
            upbit_qty = next((p.quantity for p in positions if p.symbol == mp.symbol), 0)
            if upbit_qty < mp.bot_quantity:
                logger.warning(
                    f"부분매도: Upbit 잔량({upbit_qty:.8f}) < bot_quantity({mp.bot_quantity:.8f}) "
                    f"→ 조정 ({mp.symbol})"
                )
                mp.bot_quantity = upbit_qty
            if mp.bot_quantity <= 0:
                logger.info(f"부분매도 스킵: {mp.symbol} - 보유량 0 → 관리 제거")
                self._managed_positions.pop(mp.symbol, None)
                return
        except Exception:
            pass

        sell_quantity = mp.bot_quantity * sell_pct

        # 최소주문 미달 시 전량매도로 폴백
        min_order = self._rule_engine.rules.get("trading", {}).get("min_order_amount_krw", 5000)
        sell_value = sell_quantity * mp.current_price
        if sell_value < min_order:
            await self._execute_full_sell(mp, f"{reason} (최소주문 미달 → 전량)")
            return

        try:
            result = await self._broker.sell_market(mp.symbol, sell_quantity)
            sell_amount = result.amount
            sell_fee = sell_amount * UPBIT_FEE_RATE
            buy_fee_portion = mp.bot_avg_price * sell_quantity * UPBIT_FEE_RATE
            gross_pnl = (mp.current_price - mp.bot_avg_price) * sell_quantity
            net_pnl = gross_pnl - buy_fee_portion - sell_fee
            cost_basis = mp.bot_avg_price * sell_quantity
            net_pnl_pct = (net_pnl / cost_basis * 100) if cost_basis > 0 else 0.0

            mp.bot_quantity -= sell_quantity

            # 부분매도 후 잔여 먼지 처리: 극소량 남으면 관리 제거
            remaining_value = mp.bot_quantity * mp.current_price
            if remaining_value < DUST_THRESHOLD_KRW:
                logger.info(
                    f"부분매도 후 먼지 제거: {mp.symbol} - "
                    f"잔여 {mp.bot_quantity:.8f}개 (≈{remaining_value:.0f}원)"
                )
                self._managed_positions.pop(mp.symbol, None)

            async with async_session() as session:
                trade = Trade(
                    broker=self._broker.broker_type.value,
                    symbol=mp.symbol,
                    side="sell",
                    price=result.price or mp.current_price,
                    quantity=sell_quantity,
                    amount_krw=sell_amount,
                    order_id=result.order_id,
                    status=result.status,
                    reason=reason,
                    signal_source=mp.entry_source.value,
                    fee_krw=sell_fee,
                    pnl=net_pnl,
                    pnl_pct=net_pnl_pct,
                )
                session.add(trade)
                await session.commit()

            logger.trade(
                mp.symbol, "sell", mp.current_price, sell_amount,
                f"{reason} (수량:{sell_quantity:.8f}, P&L:{net_pnl_pct:+.2f}%, 수수료:{sell_fee + buy_fee_portion:.0f}원)"
            )
            await self._broadcast("trade", trade.to_dict())

        except Exception as e:
            logger.error(f"부분매도 실패 ({mp.symbol}): {e}")

    # ─── 유틸리티 ───

    def _get_lock_date(self) -> date | None:
        """매도 잠금 날짜 반환 (미설정 시 None)"""
        lock_date_str = self._rule_engine.rules.get("trading", {}).get("sell_lock_before_date")
        if not lock_date_str:
            return None
        try:
            return datetime.strptime(lock_date_str, "%Y-%m-%d").date()
        except ValueError:
            return None

    async def _is_bought_before_lock(self, symbol: str) -> bool:
        """모든 매수 이력(봇+수동) 중 최근 매수가 잠금일 이전인지 확인.
        미추적 포지션의 자동 등록 여부 판단용.
        """
        lock_date = self._get_lock_date()
        if lock_date is None:
            return False  # 잠금일 미설정 → 잠금 아님 → 등록 가능

        async with async_session() as session:
            result = await session.execute(
                select(Trade)
                .where(Trade.symbol == symbol, Trade.side == "buy")
                .order_by(Trade.created_at.desc())
                .limit(1)
            )
            last_buy = result.scalar_one_or_none()

        if last_buy is None:
            return True  # DB에 매수 이력 없음 → 잠금일 이전 보유로 간주

        buy_date = last_buy.created_at.date() if last_buy.created_at else date.today()
        return buy_date <= lock_date

    async def _calc_post_lock_position(self, symbol: str, upbit_qty: float) -> tuple[float, float] | None:
        """잠금일 이후 매수분의 잔량과 평균가를 Trade DB에서 계산.
        Returns (remaining_qty, avg_price) or None if no post-lock buys.
        """
        lock_date = self._get_lock_date()
        if lock_date is None:
            return None  # 잠금일 미설정 → 분리 불필요

        lock_dt = datetime.combine(lock_date, datetime.min.time())

        async with async_session() as session:
            buy_result = await session.execute(
                select(Trade)
                .where(Trade.symbol == symbol, Trade.side == "buy",
                       Trade.created_at > lock_dt)
            )
            post_lock_buys = buy_result.scalars().all()

            if not post_lock_buys:
                return None

            sell_result = await session.execute(
                select(Trade)
                .where(Trade.symbol == symbol, Trade.side == "sell",
                       Trade.created_at > lock_dt)
            )
            post_lock_sells = sell_result.scalars().all()

        total_buy_qty = sum(t.quantity for t in post_lock_buys)
        total_sell_qty = sum(t.quantity for t in post_lock_sells)
        remaining_qty = total_buy_qty - total_sell_qty

        if remaining_qty <= 0:
            return None  # 전량 청산 완료

        # 안전장치: Upbit 실제 보유량 초과 방지
        remaining_qty = min(remaining_qty, upbit_qty)

        # 잠금일 이후 매수의 가중 평균가
        total_cost = sum(t.price * t.quantity for t in post_lock_buys)
        avg_price = total_cost / total_buy_qty if total_buy_qty > 0 else 0

        return (remaining_qty, avg_price)

    async def _is_sell_locked(self, symbol: str) -> bool:
        """봇이 매수한 포지션에 대해 매도 잠금 날짜 확인"""
        lock_date_str = self._rule_engine.rules.get("trading", {}).get("sell_lock_before_date")
        if not lock_date_str:
            return False
        try:
            lock_date = datetime.strptime(lock_date_str, "%Y-%m-%d").date()
        except ValueError:
            return False

        async with async_session() as session:
            result = await session.execute(
                select(Trade)
                .where(
                    Trade.symbol == symbol,
                    Trade.side == "buy",
                    Trade.signal_source.isnot(None),  # 봇 거래만 확인
                )
                .order_by(Trade.created_at.desc())
                .limit(1)
            )
            last_bot_buy = result.scalar_one_or_none()

        if last_bot_buy is None:
            return True  # 봇 매수 이력 없음 → 안전 잠금

        buy_date = last_bot_buy.created_at.date() if last_bot_buy.created_at else date.today()
        if buy_date <= lock_date:
            logger.info(f"매도 잠금: {symbol} - 봇 매수일({buy_date}) <= 잠금일({lock_date})")
            return True
        return False

    async def _reconstruct_managed_positions(self):
        """엔진 재시작 시 Trade DB에서 봇의 ManagedPosition 복원"""
        async with async_session() as session:
            result = await session.execute(
                select(Trade)
                .where(Trade.signal_source.isnot(None))
                .order_by(Trade.created_at.asc())
            )
            all_bot_trades = result.scalars().all()

        if not all_bot_trades:
            logger.info("봇 거래 내역 없음 - ManagedPosition 복원 건너뜀")
            return

        # 심볼별 거래 그룹화
        trades_by_symbol: dict[str, list] = defaultdict(list)
        for trade in all_bot_trades:
            trades_by_symbol[trade.symbol].append(trade)

        # Upbit 현재 포지션 확인
        try:
            upbit_positions = await self._broker.get_positions()
            upbit_qty_map = {p.symbol: p.quantity for p in upbit_positions}
        except Exception:
            upbit_qty_map = {}

        for symbol, trades in trades_by_symbol.items():
            buys = [t for t in trades if t.side == "buy"]
            sells = [t for t in trades if t.side == "sell"]

            total_buy_qty = sum(t.quantity for t in buys)
            total_sell_qty = sum(t.quantity for t in sells)
            remaining_qty = total_buy_qty - total_sell_qty

            if remaining_qty <= 0:
                continue  # 전량 청산 완료

            if symbol not in upbit_qty_map:
                logger.warning(f"봇 포지션 복원 스킵: {symbol} - 업비트에 없음")
                continue

            # 안전 장치: Upbit 보유량보다 많으면 Upbit 보유량으로 제한
            upbit_qty = upbit_qty_map[symbol]
            remaining_qty = min(remaining_qty, upbit_qty)

            # 가중 평균 매수가 계산
            total_cost = sum(t.price * t.quantity for t in buys)
            avg_price = total_cost / total_buy_qty if total_buy_qty > 0 else 0

            # 먼지 포지션 무시 (현재가 조회 전이므로 avg_price 기준)
            if remaining_qty * avg_price < DUST_THRESHOLD_KRW:
                continue

            # 진입 소스 (마지막 매수 기준)
            last_buy = buys[-1]
            try:
                entry_source = EntrySource(last_buy.signal_source)
            except ValueError:
                entry_source = EntrySource.TECHNICAL

            # 1차 익절 완료 감지: 마지막 매수 이후 매도 거래가 있으면 True
            last_buy_time = last_buy.created_at
            sells_after_buy = [
                s for s in sells
                if s.created_at and last_buy_time and s.created_at > last_buy_time
            ]
            first_tp_done = len(sells_after_buy) > 0

            # 현재가 조회
            try:
                ticker = await self._broker.get_ticker(symbol)
                current_price = ticker.get("trade_price", 0)
            except Exception:
                current_price = 0

            pos = Position(
                symbol=symbol,
                quantity=remaining_qty,
                avg_price=avg_price,
                current_price=current_price,
            )
            mp = ManagedPosition(
                position=pos,
                entry_source=entry_source,
                original_quantity=total_buy_qty,
                bot_quantity=remaining_qty,
                bot_avg_price=avg_price,
                current_price=current_price,
                first_tp_done=first_tp_done,
            )
            self._managed_positions[symbol] = mp
            logger.info(
                f"봇 포지션 복원: {symbol} | 수량={remaining_qty:.8f} | "
                f"평균가={avg_price:,.0f} | 소스={entry_source.value} | "
                f"1차익절완료={first_tp_done}"
            )

        logger.info(f"ManagedPosition 복원 완료: {len(self._managed_positions)}개")

    async def get_bot_positions(self) -> list[dict]:
        """봇이 관리 중인 포지션 데이터 반환 (엔진 미실행 시에도 DB에서 복원)"""
        if not self._managed_positions and not self._running:
            await self._reconstruct_managed_positions()
            await self._discover_post_lock_positions()
        return [mp.to_dict() for mp in self._managed_positions.values()]

    async def _discover_post_lock_positions(self):
        """잠금일 이후 매수한 미추적 포지션을 자동 등록 (대시보드 표시용)"""
        try:
            positions = await self._broker.get_positions()
        except Exception:
            return

        for pos in positions:
            if pos.symbol in self._managed_positions:
                continue

            # 먼지 포지션 무시
            if pos.quantity * pos.current_price < DUST_THRESHOLD_KRW:
                continue

            post_lock = await self._calc_post_lock_position(pos.symbol, pos.quantity)
            if post_lock is None:
                if await self._is_bought_before_lock(pos.symbol):
                    continue
                post_lock_qty, post_lock_avg = pos.quantity, pos.avg_price
            else:
                post_lock_qty, post_lock_avg = post_lock

            # 분리된 수량도 먼지인지 확인
            if post_lock_qty * pos.current_price < DUST_THRESHOLD_KRW:
                continue

            try:
                ticker = await self._broker.get_ticker(pos.symbol)
                current_price = ticker.get("trade_price", pos.current_price)
            except Exception:
                current_price = pos.current_price

            managed = ManagedPosition(
                position=pos,
                entry_source=EntrySource.TECHNICAL,
                original_quantity=post_lock_qty,
                bot_quantity=post_lock_qty,
                bot_avg_price=post_lock_avg,
                current_price=current_price,
            )
            self._managed_positions[pos.symbol] = managed
            logger.info(
                f"잠금일 이후 포지션 발견: {pos.symbol} | "
                f"수량={pos.quantity:.8f} | 평균가={pos.avg_price:,.0f}"
            )

    async def get_status(self) -> dict:
        now = time.time()
        entry_paused = now < self._entry_paused_until
        pause_remaining = max(0, int(self._entry_paused_until - now)) if entry_paused else 0

        return {
            "running": self._running,
            "positions_count": len(self._managed_positions),
            "positions": [mp.to_dict() for mp in self._managed_positions.values()],
            "rules_version": self._rule_engine.rules.get("version", "unknown"),
            "target_symbols": self._target_symbols,
            "entry_paused": entry_paused,
            "entry_pause_remaining_seconds": pause_remaining,
        }
