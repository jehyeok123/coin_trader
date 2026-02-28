import asyncio
import json
import time
from datetime import datetime
from functools import partial

from fastapi import WebSocket, WebSocketDisconnect

from backend.utils.logger import logger


class ConnectionManager:
    """WebSocket 연결 관리자"""

    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.append(ws)
        logger.info(f"WebSocket 연결 ({len(self._connections)}개 활성)")

    def disconnect(self, ws: WebSocket):
        if ws in self._connections:
            self._connections.remove(ws)
        logger.info(f"WebSocket 연결 해제 ({len(self._connections)}개 활성)")

    async def broadcast(self, message: dict):
        """모든 연결에 메시지 브로드캐스트"""
        if not self._connections:
            return
        data = json.dumps(message, default=str, ensure_ascii=False)
        disconnected = []
        for ws in self._connections:
            try:
                await ws.send_text(data)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.disconnect(ws)

    @property
    def active_count(self) -> int:
        return len(self._connections)


ws_manager = ConnectionManager()

# 최근 latency 저장 (대시보드에서 조회 가능)
_last_latency_ms: int = 0


def get_last_latency() -> int:
    return _last_latency_ms


async def price_ticker_loop():
    """1초 간격으로 업비트 실시간 가격을 WebSocket으로 브로드캐스트"""
    global _last_latency_ms
    import pyupbit

    logger.info("실시간 가격 스트리밍 시작")

    # 심볼 목록 캐시 (30초마다 갱신)
    cached_symbols: list[str] = []
    last_symbol_refresh = 0.0

    while True:
        try:
            if ws_manager.active_count == 0:
                await asyncio.sleep(1)
                continue

            now = time.time()
            # 30초마다 심볼 목록 갱신
            if now - last_symbol_refresh > 30 or not cached_symbols:
                loop = asyncio.get_event_loop()
                symbols = await loop.run_in_executor(
                    None, partial(pyupbit.get_tickers, fiat="KRW")
                )
                if symbols:
                    cached_symbols = symbols
                last_symbol_refresh = now

            if not cached_symbols:
                await asyncio.sleep(2)
                continue

            # 전체 가격 한 번에 조회
            loop = asyncio.get_event_loop()
            t0 = time.time()
            prices = await loop.run_in_executor(
                None, partial(pyupbit.get_current_price, cached_symbols)
            )
            latency = round((time.time() - t0) * 1000)
            _last_latency_ms = latency

            if prices and isinstance(prices, dict):
                await ws_manager.broadcast({
                    "type": "price_update",
                    "data": {
                        "prices": {k: v for k, v in prices.items() if v is not None},
                        "latency_ms": latency,
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                })

        except Exception as e:
            logger.error(f"가격 스트리밍 오류: {e}")

        await asyncio.sleep(1)


async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 엔드포인트 핸들러"""
    await ws_manager.connect(websocket)
    try:
        # 초기 상태 전송
        await websocket.send_json({
            "type": "connected",
            "data": {"message": "WebSocket 연결 성공"},
            "timestamp": datetime.utcnow().isoformat(),
        })

        while True:
            # 클라이언트 메시지 수신 (ping/pong 및 명령)
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat(),
                    })
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)
