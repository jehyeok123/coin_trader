from datetime import datetime

from sqlalchemy import String, Float, DateTime, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class SignalLog(Base):
    __tablename__ = "signal_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50))  # "news", "twitter", "technical"
    action: Mapped[str] = mapped_column(String(10))  # "buy", "sell", "hold"
    symbol: Mapped[str | None] = mapped_column(String(20), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    raw_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    acted_on: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "action": self.action,
            "symbol": self.symbol,
            "confidence": self.confidence,
            "summary": self.summary,
            "url": self.url,
            "acted_on": self.acted_on,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def to_markdown(self) -> str:
        icon = {"news": "📰", "twitter": "🐦", "technical": "📊"}.get(self.source, "❓")
        action_emoji = {"buy": "🟢", "sell": "🔴", "hold": "⚪"}.get(self.action, "❓")
        return (
            f"| {self.created_at:%Y-%m-%d %H:%M:%S} "
            f"| {icon} {self.source} "
            f"| {action_emoji} {self.action.upper()} "
            f"| `{self.symbol or '-'}` "
            f"| 신뢰도: {self.confidence:.0%} "
            f"| {self.summary or '-'} |"
        )
