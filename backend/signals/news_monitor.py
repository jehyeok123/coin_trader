import asyncio

from backend.signals.base import BaseSignalSource, Signal
from backend.signals.gemini_analyzer import GeminiAnalyzer
from backend.config import settings
from backend.utils.logger import logger


class NewsMonitor(BaseSignalSource):
    """
    뉴스/커뮤니티 모니터링 시그널 소스.
    Gemini API를 통해 N분 간격으로 암호화폐 관련 뉴스를 검색하고 분석합니다.
    """

    source_name = "news"

    def __init__(self):
        self._analyzer = GeminiAnalyzer()
        self._running = False
        self._task: asyncio.Task | None = None
        self._interval = settings.news_check_interval_minutes * 60  # 초 단위
        self._last_signals: list[Signal] = []
        self._callbacks: list = []

    def on_signal(self, callback):
        """시그널 발생 시 호출될 콜백 등록"""
        self._callbacks.append(callback)

    async def check(self) -> list[Signal]:
        """Gemini를 통해 최신 뉴스를 검색하고 시그널 반환"""
        logger.info("뉴스 모니터링: Gemini 검색 분석 시작")

        queries = [
            "암호화폐 비트코인 이더리움 최신 뉴스 시장 동향",
            "cryptocurrency bitcoin ethereum breaking news market",
        ]

        all_signals = []
        for query in queries:
            raw_signals = await self._analyzer.search_and_analyze(query)
            for s in raw_signals:
                signal = Signal(
                    source="news",
                    action=s.get("action", "hold"),
                    symbol=s.get("symbol"),
                    confidence=float(s.get("confidence", 0)),
                    summary=s.get("summary", ""),
                    raw_data=str(s),
                )
                all_signals.append(signal)

        self._last_signals = all_signals

        # 콜백 호출
        for sig in all_signals:
            if sig.action != "hold":
                for cb in self._callbacks:
                    try:
                        await cb(sig)
                    except Exception as e:
                        logger.error(f"뉴스 시그널 콜백 오류: {e}")

        logger.info(f"뉴스 모니터링 완료: {len(all_signals)}개 시그널")
        return all_signals

    async def _monitor_loop(self):
        """주기적으로 뉴스를 확인하는 루프"""
        while self._running:
            try:
                await self.check()
            except Exception as e:
                logger.error(f"뉴스 모니터링 루프 오류: {e}")
            await asyncio.sleep(self._interval)

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(
            f"뉴스 모니터링 시작 (간격: {self._interval // 60}분)"
        )

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("뉴스 모니터링 중지")

    def set_interval(self, minutes: int):
        """모니터링 간격 변경 (분 단위)"""
        self._interval = minutes * 60
        logger.info(f"뉴스 모니터링 간격 변경: {minutes}분")

    @property
    def last_signals(self) -> list[Signal]:
        return self._last_signals
