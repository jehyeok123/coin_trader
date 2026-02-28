import asyncio
from datetime import datetime

import feedparser
import httpx

from backend.signals.base import BaseSignalSource, Signal
from backend.signals.gemini_analyzer import GeminiAnalyzer
from backend.config import settings
from backend.utils.logger import logger


class TwitterMonitor(BaseSignalSource):
    """
    트위터(X) 모니터링 시그널 소스.
    RSS/Nitter를 통해 특정 계정의 새 글을 폴링하고,
    Gemini API로 분석하여 매매 시그널을 생성합니다.
    """

    source_name = "twitter"

    def __init__(self):
        self._analyzer = GeminiAnalyzer()
        self._running = False
        self._task: asyncio.Task | None = None
        self._interval = settings.twitter_check_interval_seconds
        self._accounts = settings.twitter_accounts
        self._seen_ids: set[str] = set()
        self._last_signals: list[Signal] = []
        self._callbacks: list = []
        self._nitter_url = settings.nitter_instance_url.rstrip("/")

    def on_signal(self, callback):
        """시그널 발생 시 호출될 콜백 등록"""
        self._callbacks.append(callback)

    def set_accounts(self, accounts: list[str]):
        """감시 대상 계정 목록 변경"""
        self._accounts = accounts
        logger.info(f"트위터 감시 계정 변경: {accounts}")

    async def _fetch_feed(self, account: str) -> list[dict]:
        """Nitter RSS 피드를 가져옵니다."""
        url = f"{self._nitter_url}/{account}/rss"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    logger.warning(f"트위터 RSS 가져오기 실패 ({account}): HTTP {response.status_code}")
                    return []

            feed = feedparser.parse(response.text)
            entries = []
            for entry in feed.entries:
                entry_id = entry.get("id", entry.get("link", ""))
                entries.append({
                    "id": entry_id,
                    "account": account,
                    "title": entry.get("title", ""),
                    "content": entry.get("summary", entry.get("title", "")),
                    "published": entry.get("published", ""),
                    "link": entry.get("link", ""),
                })
            return entries

        except Exception as e:
            logger.error(f"트위터 RSS 가져오기 오류 ({account}): {e}")
            return []

    async def check(self) -> list[Signal]:
        """모든 감시 계정의 새 글을 확인하고 시그널 반환"""
        all_signals = []

        for account in self._accounts:
            entries = await self._fetch_feed(account)
            new_entries = [e for e in entries if e["id"] not in self._seen_ids]

            if not new_entries:
                continue

            # 새 글을 Gemini로 분석
            for entry in new_entries:
                self._seen_ids.add(entry["id"])
                content = (
                    f"트위터 계정 @{account}의 새 글:\n"
                    f"내용: {entry['content']}\n"
                    f"게시 시간: {entry['published']}"
                )

                raw_signals = await self._analyzer.analyze(content)
                for s in raw_signals:
                    signal = Signal(
                        source="twitter",
                        action=s.get("action", "hold"),
                        symbol=s.get("symbol"),
                        confidence=float(s.get("confidence", 0)),
                        summary=f"@{account}: {s.get('summary', '')}",
                        raw_data=str(entry),
                    )
                    all_signals.append(signal)

                    # 즉시 콜백 (인터럽트 트레이딩)
                    if signal.action != "hold":
                        for cb in self._callbacks:
                            try:
                                await cb(signal)
                            except Exception as e:
                                logger.error(f"트위터 시그널 콜백 오류: {e}")

        self._last_signals = all_signals
        if all_signals:
            logger.info(f"트위터 모니터링: {len(all_signals)}개 시그널 감지")
        return all_signals

    async def _monitor_loop(self):
        """주기적으로 트위터를 확인하는 루프"""
        while self._running:
            try:
                await self.check()
            except Exception as e:
                logger.error(f"트위터 모니터링 루프 오류: {e}")
            await asyncio.sleep(self._interval)

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(
            f"트위터 모니터링 시작 (계정: {self._accounts}, 간격: {self._interval}초)"
        )

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("트위터 모니터링 중지")

    @property
    def last_signals(self) -> list[Signal]:
        return self._last_signals
