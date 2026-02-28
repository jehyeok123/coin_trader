from datetime import datetime

from sqlalchemy import String, DateTime, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class SystemLog(Base):
    __tablename__ = "system_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    level: Mapped[str] = mapped_column(String(10))  # INFO, WARN, ERROR
    category: Mapped[str] = mapped_column(String(50))  # trading, signal, system
    message: Mapped[str] = mapped_column(Text)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "level": self.level,
            "category": self.category,
            "message": self.message,
            "details": self.details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def to_markdown(self) -> str:
        level_icon = {
            "INFO": "ℹ️",
            "WARN": "⚠️",
            "ERROR": "❌",
        }.get(self.level, "📝")
        return (
            f"| {self.created_at:%Y-%m-%d %H:%M:%S} "
            f"| {level_icon} {self.level} "
            f"| [{self.category}] "
            f"| {self.message} |"
        )
