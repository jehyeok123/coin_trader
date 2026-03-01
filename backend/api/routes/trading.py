from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database import get_db
from backend.models.trade import Trade
from backend.utils.logger import logger

router = APIRouter(prefix="/trading", tags=["Trading"])


@router.get("/status")
async def get_trading_status():
    """매매 엔진 상태 조회"""
    from backend.main import get_scheduler
    scheduler = get_scheduler()
    if scheduler is None:
        return {"running": False, "message": "스케줄러가 초기화되지 않았습니다."}
    return await scheduler.get_status()


@router.post("/start")
async def start_trading():
    """매매 엔진 시작"""
    from backend.main import get_scheduler
    scheduler = get_scheduler()
    if scheduler is None:
        return {"success": False, "message": "스케줄러가 초기화되지 않았습니다."}
    await scheduler.start_all()
    return {"success": True, "message": "트레이딩 시스템이 시작되었습니다."}


@router.post("/stop")
async def stop_trading():
    """매매 엔진 중지"""
    from backend.main import get_scheduler
    scheduler = get_scheduler()
    if scheduler is None:
        return {"success": False, "message": "스케줄러가 초기화되지 않았습니다."}
    await scheduler.stop_all()
    return {"success": True, "message": "트레이딩 시스템이 중지되었습니다."}


@router.get("/history")
async def get_trade_history(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    symbol: str | None = None,
    side: str | None = None,
    from_date: str | None = Query(None, description="조회 시작 날짜시간 (ISO format, e.g. 2025-01-01T00:00:00)"),
    db: AsyncSession = Depends(get_db),
):
    """거래 내역 조회"""
    query = select(Trade).order_by(desc(Trade.created_at))
    if symbol:
        query = query.where(Trade.symbol == symbol)
    if side:
        query = query.where(Trade.side == side)
    if from_date:
        try:
            dt = datetime.fromisoformat(from_date)
            query = query.where(Trade.created_at >= dt)
        except ValueError:
            pass
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    trades = result.scalars().all()

    trade_dicts = [t.to_dict() for t in trades]
    buy_trades = [t for t in trades if t.side == "buy"]
    buy_symbols = list({t.symbol for t in buy_trades})

    if buy_symbols:
        # 현재 시세 조회 (평가금액 계산용)
        try:
            from backend.main import get_broker
            broker = get_broker()
            if broker:
                tickers = await broker.get_full_tickers(buy_symbols)
                price_map = {t["symbol"]: t.get("trade_price", 0) for t in tickers}
                for td in trade_dicts:
                    if td["side"] == "buy" and td["symbol"] in price_map:
                        td["current_price"] = price_map[td["symbol"]]
        except Exception:
            pass

        # 매수 거래에 대응하는 매도가 매칭
        try:
            from collections import defaultdict
            sell_query = select(Trade).where(
                Trade.side == "sell",
                Trade.symbol.in_(buy_symbols),
            ).order_by(Trade.created_at)
            sell_result = await db.execute(sell_query)
            all_sells = sell_result.scalars().all()

            sells_by_symbol = defaultdict(list)
            for s in all_sells:
                sells_by_symbol[s.symbol].append(s)

            for td in trade_dicts:
                if td["side"] == "buy":
                    buy_time = td["created_at"]
                    for sell in sells_by_symbol.get(td["symbol"], []):
                        sell_time = sell.created_at.isoformat() if sell.created_at else ""
                        if sell_time > buy_time:
                            td["sell_price"] = sell.price
                            td["sell_amount"] = sell.amount_krw
                            break
        except Exception:
            pass

    # 전체 총 실현 손익 (페이지 무관)
    total_realized_pnl = 0.0
    try:
        pnl_result = await db.execute(
            select(func.coalesce(func.sum(Trade.pnl), 0.0)).where(
                Trade.side == "sell", Trade.pnl.isnot(None)
            )
        )
        total_realized_pnl = float(pnl_result.scalar() or 0.0)
    except Exception:
        pass

    return {
        "trades": trade_dicts,
        "total": len(trades),
        "total_realized_pnl": total_realized_pnl,
        "offset": offset,
        "limit": limit,
    }


class SyncRequest(BaseModel):
    from_date: str


@router.post("/sync-history")
async def sync_trade_history(body: SyncRequest, db: AsyncSession = Depends(get_db)):
    """업비트 API에서 체결 내역을 가져와 DB에 동기화"""
    from backend.main import get_broker

    broker = get_broker()
    if broker is None:
        return {"success": False, "message": "브로커가 초기화되지 않았습니다."}

    # datetime-local 형식(2025-01-01T10:00)에 KST 타임존 추가
    from_date_str = body.from_date
    if "+" not in from_date_str and "Z" not in from_date_str:
        from_date_str += "+09:00"

    try:
        orders = await broker.get_closed_orders(from_date_str)
    except Exception as e:
        logger.error(f"업비트 주문 조회 실패: {e}")
        return {"success": False, "message": f"업비트 주문 조회 실패: {str(e)}"}

    synced = 0
    skipped = 0
    errors = 0

    for order in orders:
        order_uuid = order.get("uuid", "")
        if not order_uuid:
            continue

        # DB에 이미 존재하는지 확인
        existing = await db.execute(
            select(Trade).where(Trade.order_id == order_uuid)
        )
        if existing.scalar_one_or_none() is not None:
            skipped += 1
            continue

        try:
            side_map = {"bid": "buy", "ask": "sell"}
            side = side_map.get(order.get("side", ""), order.get("side", ""))
            market = order.get("market", "")
            executed_volume = float(order.get("executed_volume", 0) or 0)
            paid_fee = float(order.get("paid_fee", 0) or 0)

            if executed_volume <= 0:
                continue

            ord_type = order.get("ord_type", "")

            if ord_type == "price":  # 시장가 매수
                total_krw = float(order.get("price", 0) or 0)
                avg_price = total_krw / executed_volume if executed_volume > 0 else 0
                amount_krw = total_krw
            elif ord_type == "market":  # 시장가 매도
                # 체결 상세에서 실제 체결 금액 조회
                detail = await broker.get_order(order_uuid)
                trades_info = detail.get("trades", [])
                if trades_info:
                    total_funds = sum(float(t.get("funds", 0) or 0) for t in trades_info)
                else:
                    total_funds = 0
                avg_price = total_funds / executed_volume if executed_volume > 0 else 0
                amount_krw = total_funds
            elif ord_type == "limit":  # 지정가
                limit_price = float(order.get("price", 0) or 0)
                avg_price = limit_price
                amount_krw = limit_price * executed_volume
            else:
                continue

            # 시간 변환 (KST → UTC naive)
            created_at_str = order.get("created_at", "")
            try:
                created_at = datetime.fromisoformat(created_at_str)
                if created_at.tzinfo is not None:
                    created_at = created_at.astimezone(timezone.utc).replace(tzinfo=None)
            except Exception:
                created_at = datetime.utcnow()

            trade = Trade(
                broker="upbit",
                symbol=market,
                side=side,
                price=avg_price,
                quantity=executed_volume,
                amount_krw=amount_krw,
                order_id=order_uuid,
                status="completed",
                reason="업비트 동기화",
                fee_krw=paid_fee,
                created_at=created_at,
            )
            db.add(trade)
            synced += 1
        except Exception as e:
            logger.error(f"주문 동기화 실패 ({order_uuid}): {e}")
            errors += 1

    if synced > 0:
        await db.commit()

    return {
        "success": True,
        "synced": synced,
        "skipped": skipped,
        "errors": errors,
        "total_from_upbit": len(orders),
    }


@router.get("/target-coins")
async def get_target_coins():
    """매수 후보 코인 목록 (거래대금 상위) 조회"""
    from backend.main import get_broker, get_scheduler
    from backend.config.settings import load_trading_rules

    broker = get_broker()
    if broker is None:
        return {"coins": [], "message": "브로커가 초기화되지 않았습니다."}

    rules = load_trading_rules()
    top_n = rules.get("target_coins", {}).get("top_n", 15)
    min_price = rules.get("filters", {}).get("min_price_krw", 1000)

    # 현재 엔진의 활성 타겟 심볼
    active_targets: list[str] = []
    scheduler = get_scheduler()
    if scheduler:
        engine_status = await scheduler._engine.get_status()
        active_targets = engine_status.get("target_symbols", [])

    try:
        from backend.core.rule_engine import RuleEngine
        rule_engine = RuleEngine()

        all_symbols = await broker.get_available_symbols()
        full_tickers = await broker.get_full_tickers(all_symbols)

        # 24h 상위 50개 추린 후 1h 거래대금으로 재정렬
        full_tickers.sort(
            key=lambda t: t.get("acc_trade_price_24h", 0), reverse=True
        )
        pre_filter = [t["symbol"] for t in full_tickers[:50]]
        ticker_map = {t["symbol"]: t for t in full_tickers}

        vol_1h = await broker.get_1h_volumes(pre_filter)
        ranked = sorted(pre_filter, key=lambda s: vol_1h.get(s, 0), reverse=True)

        # 기술적 분석 설정
        tech = rules.get("technical_strategy", {})
        candle_interval = tech.get("candle_interval", "15m")
        candle_count = tech.get("candle_count", 200)

        # 최소 가격 + 1h 거래대금 > 0 필터 → 상위 top_n개만 추출
        target_symbols = []
        for symbol in ranked:
            t = ticker_map[symbol]
            if t.get("trade_price", 0) < min_price:
                continue
            if vol_1h.get(symbol, 0) <= 0:
                continue
            target_symbols.append(symbol)
            if len(target_symbols) >= top_n:
                break

        # OHLCV 배치 조회 (httpx 직접 + 재시도)
        ohlcv_map = await broker.get_ohlcv_batch(
            target_symbols, interval=candle_interval, count=candle_count
        )

        coins = []
        for symbol in target_symbols:
            t = ticker_map[symbol]
            entry_status = None
            try:
                df = ohlcv_map.get(symbol)
                current_price = t.get("trade_price", 0)
                result = rule_engine.evaluate(symbol, df, current_price)
                indicators = result.get("indicators", {})
                reasons = result.get("reasons", [])
                action = result.get("action", "hold")
                entry_status = {
                    **indicators,
                    "reasons": reasons,
                    "action": action,
                    "current_price": indicators.get("current_price", current_price),
                }
            except Exception:
                pass

            coins.append({
                "rank": len(coins) + 1,
                "symbol": symbol,
                "trade_price": t.get("trade_price", 0),
                "acc_trade_price_1h": vol_1h.get(symbol, 0),
                "acc_trade_price_24h": t.get("acc_trade_price_24h", 0),
                "signed_change_rate": t.get("signed_change_rate", 0),
                "is_target": symbol in active_targets,
                "entry_status": entry_status,
            })

        cooldown = rules.get("trading", {}).get("cooldown_seconds", 60)
        refresh = rules.get("target_coins", {}).get("refresh_interval_seconds", 3600)
        entry_cfg = rules.get("technical_strategy", {}).get("entry", {})
        return {
            "coins": coins,
            "top_n": top_n,
            "total_symbols": len(all_symbols),
            "min_price_krw": min_price,
            "cooldown_seconds": cooldown,
            "refresh_interval_seconds": refresh,
            "rsi_min": entry_cfg.get("rsi_min", 0),
            "rsi_max": entry_cfg.get("rsi_max", 0),
        }
    except Exception as e:
        return {"coins": [], "error": str(e)}


@router.get("/positions")
async def get_positions():
    """현재 보유 포지션 조회 (전체 + 봇 포지션 분리)"""
    from backend.main import get_broker, get_scheduler
    broker = get_broker()
    if broker is None:
        return {"positions": [], "message": "브로커가 초기화되지 않았습니다."}
    try:
        positions = await broker.get_positions()
        balance = await broker.get_balance()
        total_value = balance.get("krw", 0) + sum(
            p.current_price * p.quantity for p in positions
        )

        # 봇 포지션 (엔진의 ManagedPosition 데이터)
        bot_positions: list[dict] = []
        scheduler = get_scheduler()
        if scheduler:
            bot_positions = await scheduler._engine.get_bot_positions()

        # 실현 손익
        total_realized_pnl = 0.0
        bot_realized_pnl = 0.0
        try:
            from backend.models.database import async_session as db_session
            async with db_session() as session:
                pnl_result = await session.execute(
                    select(func.coalesce(func.sum(Trade.pnl), 0.0)).where(
                        Trade.side == "sell", Trade.pnl.isnot(None)
                    )
                )
                total_realized_pnl = float(pnl_result.scalar() or 0.0)

                bot_pnl_result = await session.execute(
                    select(func.coalesce(func.sum(Trade.pnl), 0.0)).where(
                        Trade.side == "sell",
                        Trade.pnl.isnot(None),
                        Trade.signal_source.isnot(None),
                    )
                )
                bot_realized_pnl = float(bot_pnl_result.scalar() or 0.0)
        except Exception:
            pass

        # 최대 포지션 수
        from backend.config.settings import load_trading_rules
        rules = load_trading_rules()
        max_positions = rules.get("trading", {}).get("max_concurrent_positions", 5)

        return {
            "krw_balance": balance.get("krw", 0),
            "total_value": total_value,
            "total_realized_pnl": total_realized_pnl,
            "bot_positions": bot_positions,
            "bot_realized_pnl": bot_realized_pnl,
            "positions": [p.to_dict() for p in positions],
            "max_positions": max_positions,
        }
    except Exception as e:
        return {"positions": [], "error": str(e)}
