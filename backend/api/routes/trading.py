from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database import get_db
from backend.models.trade import Trade

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
    db: AsyncSession = Depends(get_db),
):
    """거래 내역 조회"""
    query = select(Trade).order_by(desc(Trade.created_at))
    if symbol:
        query = query.where(Trade.symbol == symbol)
    if side:
        query = query.where(Trade.side == side)
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    trades = result.scalars().all()
    return {
        "trades": [t.to_dict() for t in trades],
        "total": len(trades),
        "offset": offset,
        "limit": limit,
    }


@router.get("/positions")
async def get_positions():
    """현재 보유 포지션 조회"""
    from backend.main import get_broker
    broker = get_broker()
    if broker is None:
        return {"positions": [], "message": "브로커가 초기화되지 않았습니다."}
    try:
        positions = await broker.get_positions()
        balance = await broker.get_balance()
        total_value = balance.get("krw", 0) + sum(
            p.current_price * p.quantity for p in positions
        )
        return {
            "krw_balance": balance.get("krw", 0),
            "total_value": total_value,
            "positions": [p.to_dict() for p in positions],
        }
    except Exception as e:
        return {"positions": [], "error": str(e)}
