from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os

from dotenv import load_dotenv

# .env 파일 로드 (프로젝트 루트에서)
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

from backend.models.database import init_db
import backend.models.trade  # noqa: F401 - ensure tables are registered
import backend.models.signal  # noqa: F401 - ensure tables are registered
from backend.api.routes import api_router
from backend.api.websocket import websocket_endpoint, ws_manager, price_ticker_loop
from backend.brokers.upbit import UpbitBroker
from backend.brokers.base import BaseBroker
from backend.core.trading_engine import TradingEngine
from backend.core.scheduler import TradingScheduler
from backend.utils.logger import logger

# 전역 인스턴스
_broker: BaseBroker | None = None
_scheduler: TradingScheduler | None = None


def get_broker() -> BaseBroker | None:
    return _broker


def get_scheduler() -> TradingScheduler | None:
    return _scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 수명주기 관리"""
    global _broker, _scheduler

    # 시작
    logger.info("Coin Trader 시스템 초기화 중...")
    await init_db()
    logger.info("데이터베이스 초기화 완료")

    # 브로커 초기화
    _broker = UpbitBroker()

    # 매매 엔진 및 스케줄러 초기화
    engine = TradingEngine(_broker)
    engine.on_update(ws_manager.broadcast)  # WebSocket 연결
    _scheduler = TradingScheduler(engine)

    # 실시간 가격 스트리밍 시작
    import asyncio
    price_task = asyncio.create_task(price_ticker_loop())

    logger.info("Coin Trader 시스템 초기화 완료")

    yield

    # 가격 스트리밍 종료
    price_task.cancel()
    try:
        await price_task
    except asyncio.CancelledError:
        pass

    # 종료
    if _scheduler:
        await _scheduler.stop_all()
    logger.info("Coin Trader 시스템 종료")


app = FastAPI(
    title="Coin Trader",
    description="암호화폐 자동 매매 시스템",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 라우트 등록
app.include_router(api_router)

# WebSocket 등록
app.websocket("/ws")(websocket_endpoint)

# 프론트엔드 정적 파일 서빙 (빌드된 경우)
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "coin-trader"}
