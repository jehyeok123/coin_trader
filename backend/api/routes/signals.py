from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database import get_db
from backend.models.signal import SignalLog

router = APIRouter(prefix="/signals", tags=["Signals"])


@router.get("")
async def get_signals(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    source: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """시그널 로그 조회"""
    query = select(SignalLog).order_by(desc(SignalLog.created_at))
    if source:
        query = query.where(SignalLog.source == source)
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    signals = result.scalars().all()
    return {
        "signals": [s.to_dict() for s in signals],
        "total": len(signals),
    }


@router.get("/latest")
async def get_latest_signals():
    """뉴스/트위터 모니터의 최신 시그널 조회"""
    from backend.main import get_scheduler
    scheduler = get_scheduler()
    if scheduler is None:
        return {"news": [], "twitter": []}
    return {
        "news": [s.to_dict() for s in scheduler.news_monitor.last_signals],
        "twitter": [s.to_dict() for s in scheduler.twitter_monitor.last_signals],
    }


@router.post("/check-news")
async def trigger_news_check():
    """수동으로 뉴스 체크 트리거"""
    from backend.main import get_scheduler
    scheduler = get_scheduler()
    if scheduler is None:
        return {"success": False, "message": "스케줄러가 초기화되지 않았습니다."}
    signals = await scheduler.news_monitor.check()
    return {
        "success": True,
        "signals": [s.to_dict() for s in signals],
    }
