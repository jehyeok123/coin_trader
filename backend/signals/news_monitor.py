import asyncio
from datetime import datetime, timedelta

from backend.signals.base import BaseSignalSource, Signal
from backend.signals.gemini_analyzer import GeminiAnalyzer
from backend.models.database import async_session
from backend.models.signal import SignalLog
from backend.config import settings
from backend.utils.logger import logger


class NewsMonitor(BaseSignalSource):
    """
    뉴스 모니터링 시그널 소스.
    Gemini 검색을 통해 최신 암호화폐 뉴스를 수집하고 분석합니다.
    """

    source_name = "news"

    def __init__(self):
        self._analyzer = GeminiAnalyzer()
        self._running = False
        self._task: asyncio.Task | None = None
        self._interval = settings.news_check_interval_seconds
        self._last_signals: list[Signal] = []
        self._callbacks: list = []
        self._last_check_time: datetime | None = None

    def on_signal(self, callback):
        self._callbacks.append(callback)

    async def _save_signal_to_db(self, signal: Signal):
        """시그널을 DB에 직접 저장"""
        try:
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
        except Exception as e:
            logger.error(f"시그널 DB 저장 실패: {e}")

    @staticmethod
    def _fmt_kst(dt: datetime) -> str:
        """UTC datetime을 KST 문자열로 변환"""
        kst = dt + timedelta(hours=9)
        return kst.strftime("%H:%M:%S")

    async def check(self) -> list[Signal]:
        """Gemini를 통해 최신 뉴스를 검색하고 시그널 반환.
        매 Gemini 호출마다 요청/응답 시각과 결과를 DB에 기록합니다.
        """
        queries = [
            "cryptocurrency bitcoin ethereum breaking news market events",
            "crypto altcoin listing delisting hack exploit latest news",
        ]

        now = datetime.utcnow()
        self._last_check_time = now
        time_from = (now - timedelta(seconds=self._interval)).strftime("%Y-%m-%d %H:%M UTC")
        time_to = now.strftime("%Y-%m-%d %H:%M UTC")

        logger.info(f"뉴스 모니터링: Gemini 검색 분석 시작 (시간 범위: {time_from} ~ {time_to})")

        all_signals = []
        for query in queries:
            req_time = datetime.utcnow()
            try:
                score_result = await self._analyzer.search_and_analyze(
                    query, time_from=time_from, time_to=time_to
                )
                resp_time = datetime.utcnow()
                time_tag = f"[요청 {self._fmt_kst(req_time)} → 응답 {self._fmt_kst(resp_time)}]"

                if score_result is None:
                    # Gemini 응답 파싱 실패 또는 빈 응답
                    all_signals.append(Signal(
                        source="news", action="hold", symbol=None,
                        confidence=0.0, score=0, scope="none",
                        summary=f"{time_tag} 뉴스 없음 (Gemini 응답 없음)",
                        raw_data="",
                    ))
                    continue

                signal = self._score_to_signal(score_result)
                if signal:
                    # 실제 뉴스 시그널 - 시각 태그 추가
                    signal.summary = f"{time_tag} {signal.summary}"
                    all_signals.append(signal)
                else:
                    # score=0 또는 scope=none (뉴스 없음)
                    reason = score_result.get("reason", "주요 뉴스 없음")
                    all_signals.append(Signal(
                        source="news", action="hold", symbol=None,
                        confidence=0.0, score=0, scope="none",
                        summary=f"{time_tag} 뉴스 없음 - {reason}",
                        raw_data=str(score_result),
                    ))
            except Exception as e:
                resp_time = datetime.utcnow()
                time_tag = f"[요청 {self._fmt_kst(req_time)} → 응답 {self._fmt_kst(resp_time)}]"
                logger.error(f"Gemini 검색 분석 실패: {e}")
                all_signals.append(Signal(
                    source="news", action="hold", symbol=None,
                    confidence=0.0, score=0, scope="none",
                    summary=f"{time_tag} Gemini 오류: {str(e)[:80]}",
                    raw_data="",
                ))

        self._last_signals = all_signals

        # 모든 시그널을 DB에 저장 (hold 포함)
        for sig in all_signals:
            await self._save_signal_to_db(sig)

        # 매매 콜백은 non-hold 시그널만
        for sig in all_signals:
            if sig.action != "hold":
                for cb in self._callbacks:
                    try:
                        await cb(sig)
                    except Exception as e:
                        logger.error(f"뉴스 시그널 콜백 오류: {e}")

        logger.info(f"뉴스 모니터링 완료: {len(all_signals)}개 시그널 (DB 저장 완료)")
        return all_signals

    @staticmethod
    def _score_to_signal(score_result: dict) -> Signal | None:
        """점수 결과를 Signal 객체로 변환"""
        ticker = score_result.get("ticker")
        score = int(score_result.get("score", 0))
        reason = score_result.get("reason", "")
        scope = score_result.get("scope", "ticker")

        # "뉴스 없음" 응답 처리
        if scope == "none" or ticker == "NONE":
            return None

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
            source="news",
            action=action,
            symbol=symbol,
            confidence=confidence,
            score=score,
            scope=scope,
            summary=f"[{scope}|score:{score:+d}] {reason}",
            raw_data=str(score_result),
        )

    async def _monitor_loop(self):
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
        logger.info(f"뉴스 모니터링 시작 (간격: {self._interval}초)")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("뉴스 모니터링 중지")

    def set_interval(self, seconds: int):
        self._interval = seconds
        logger.info(f"뉴스 모니터링 간격 변경: {seconds}초")

    @property
    def last_signals(self) -> list[Signal]:
        return self._last_signals

    @property
    def last_check_time(self) -> datetime | None:
        return self._last_check_time
