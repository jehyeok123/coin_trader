import asyncio

from backend.core.trading_engine import TradingEngine
from backend.signals.news_monitor import NewsMonitor
from backend.signals.twitter_monitor import TwitterMonitor
from backend.utils.logger import logger


class TradingScheduler:
    """
    트레이딩 스케줄러.
    매매 엔진과 시그널 모니터를 통합 관리합니다.
    """

    def __init__(self, engine: TradingEngine):
        self._engine = engine
        self._news_monitor = NewsMonitor()
        self._twitter_monitor = TwitterMonitor()
        self._running = False

        # 시그널 콜백 등록 - 인터럽트 시그널을 엔진에 전달
        self._news_monitor.on_signal(self._engine.handle_interrupt_signal)
        self._twitter_monitor.on_signal(self._engine.handle_interrupt_signal)

    @property
    def news_monitor(self) -> NewsMonitor:
        return self._news_monitor

    @property
    def twitter_monitor(self) -> TwitterMonitor:
        return self._twitter_monitor

    async def start_all(self):
        """모든 서비스 시작"""
        if self._running:
            return
        self._running = True

        logger.info("전체 트레이딩 시스템 시작")
        await self._engine.start()
        await self._news_monitor.start()
        # 트위터 모니터는 기본 OFF (설정에서 수동 ON 가능)
        logger.info("전체 트레이딩 시스템 시작 완료 (트위터 모니터: OFF)")

    async def stop_all(self):
        """모든 서비스 중지"""
        self._running = False

        logger.info("전체 트레이딩 시스템 중지")
        await self._engine.stop()
        await self._news_monitor.stop()
        await self._twitter_monitor.stop()
        logger.info("전체 트레이딩 시스템 중지 완료")

    async def start_trading_only(self):
        """매매 엔진만 시작"""
        await self._engine.start()

    async def stop_trading_only(self):
        """매매 엔진만 중지"""
        await self._engine.stop()

    def set_news_interval(self, seconds: int):
        """뉴스 모니터링 간격 변경"""
        self._news_monitor.set_interval(seconds)

    def set_twitter_accounts(self, accounts: list[str]):
        """트위터 감시 계정 변경"""
        self._twitter_monitor.set_accounts(accounts)

    async def toggle_news_monitor(self, enabled: bool):
        """뉴스 모니터 on/off"""
        if enabled and not self._news_monitor._running:
            await self._news_monitor.start()
        elif not enabled and self._news_monitor._running:
            await self._news_monitor.stop()

    async def toggle_twitter_monitor(self, enabled: bool):
        """트위터 모니터 on/off"""
        if enabled and not self._twitter_monitor._running:
            await self._twitter_monitor.start()
        elif not enabled and self._twitter_monitor._running:
            await self._twitter_monitor.stop()

    async def get_status(self) -> dict:
        """전체 시스템 상태 조회"""
        engine_status = await self._engine.get_status()

        return {
            "engine": engine_status,
            "news_monitor": {
                "running": self._news_monitor._running,
                "interval_seconds": self._news_monitor._interval,
                "last_signals_count": len(self._news_monitor.last_signals),
                "last_check_time": self._news_monitor.last_check_time.isoformat() if self._news_monitor.last_check_time else None,
            },
            "twitter_monitor": {
                "running": self._twitter_monitor._running,
                "accounts": self._twitter_monitor._accounts,
                "interval_seconds": self._twitter_monitor._interval,
                "last_signals_count": len(self._twitter_monitor.last_signals),
            },
        }
