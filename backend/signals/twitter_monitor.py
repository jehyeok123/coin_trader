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
    Gemini API로 키워드 점수 분석하여 매매 시그널을 생성합니다.
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
        self._callbacks.append(callback)

    def set_accounts(self, accounts: list[str]):
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

            for entry in new_entries:
                self._seen_ids.add(entry["id"])
                content = (
                    f"Tweet from @{account}:\n"
                    f"{entry['content']}\n"
                    f"Published: {entry['published']}"
                )

                score_result = await self._analyzer.analyze(content)
                if score_result is None:
                    continue

                signal = self._score_to_signal(score_result, account, entry.get("link", ""))
                if signal is None:
                    continue

                all_signals.append(signal)

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

    @staticmethod
    def _score_to_signal(score_result: dict, account: str, url: str = "") -> Signal | None:
        """점수 결과를 Signal 객체로 변환"""
        ticker = score_result.get("ticker")
        score = int(score_result.get("score", 0))
        reason = score_result.get("reason", "")
        scope = score_result.get("scope", "ticker")

        if score == 0:
            return None

        if scope == "macro":
            symbol = None
        else:
            if ticker is None:
                return None
            symbol = f"KRW-{ticker}" if not ticker.startswith("KRW-") else ticker

        if score >= 4:
            action = "buy"
        elif score <= -4:
            action = "sell"
        else:
            action = "hold"

        confidence = min(abs(score) / 5.0, 1.0)

        return Signal(
            source="twitter",
            action=action,
            symbol=symbol,
            confidence=confidence,
            score=score,
            scope=scope,
            summary=f"@{account} [{scope}|score:{score:+d}] {reason}",
            url=url,
            raw_data=str(score_result),
        )

    async def _monitor_loop(self):
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
        logger.info(f"트위터 모니터링 시작 (계정: {self._accounts}, 간격: {self._interval}초)")

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
