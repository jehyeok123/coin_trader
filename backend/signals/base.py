from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class SignalAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class SignalSource(str, Enum):
    NEWS = "news"
    TWITTER = "twitter"
    TECHNICAL = "technical"


@dataclass
class Signal:
    """매매 시그널 데이터 클래스"""
    source: str  # "news", "twitter", "technical"
    action: str  # "buy", "sell", "hold"
    symbol: str | None = None
    confidence: float = 0.0  # 0.0 ~ 1.0
    score: int = 0  # Gemini 키워드 점수 (-5 ~ +5), 0 = 미산출
    scope: str = "ticker"  # "ticker" (개별 코인) or "macro" (거시경제)
    summary: str = ""
    url: str = ""  # 원문 링크
    raw_data: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "action": self.action,
            "symbol": self.symbol,
            "confidence": self.confidence,
            "summary": self.summary,
            "url": self.url,
            "created_at": self.created_at.isoformat(),
        }

    def to_markdown(self) -> str:
        icons = {"news": "📰", "twitter": "🐦", "technical": "📊"}
        action_icons = {"buy": "🟢", "sell": "🔴", "hold": "⚪"}
        return (
            f"**{icons.get(self.source, '❓')} [{self.source.upper()}]** "
            f"{action_icons.get(self.action, '❓')} {self.action.upper()} "
            f"`{self.symbol or 'N/A'}` "
            f"(신뢰도: {self.confidence:.0%}) - {self.summary}"
        )


class BaseSignalSource(ABC):
    """
    시그널 소스 추상 인터페이스.
    모든 시그널 소스(뉴스, 트위터, 기술적 분석 등)는 이 인터페이스를 구현해야 합니다.
    """

    source_name: str

    @abstractmethod
    async def check(self) -> list[Signal]:
        """시그널을 확인하고 반환"""
        ...

    @abstractmethod
    async def start(self):
        """모니터링 시작"""
        ...

    @abstractmethod
    async def stop(self):
        """모니터링 중지"""
        ...
