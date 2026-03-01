from datetime import datetime

from sqlalchemy import String, Float, DateTime, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    broker: Mapped[str] = mapped_column(String(20), default="upbit")
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    side: Mapped[str] = mapped_column(String(10))  # "buy" or "sell"
    price: Mapped[float] = mapped_column(Float)
    quantity: Mapped[float] = mapped_column(Float)
    amount_krw: Mapped[float] = mapped_column(Float)
    order_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="completed")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    signal_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    fee_krw: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "broker": self.broker,
            "symbol": self.symbol,
            "side": self.side,
            "price": self.price,
            "quantity": self.quantity,
            "amount_krw": self.amount_krw,
            "order_id": self.order_id,
            "status": self.status,
            "reason": self.reason,
            "signal_source": self.signal_source,
            "fee_krw": self.fee_krw,
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "created_at": (self.created_at.isoformat() + "Z") if self.created_at else None,
        }

    def to_markdown(self) -> str:
        emoji = "🟢" if self.side == "buy" else "🔴"
        pnl_str = f" | P&L: {self.pnl_pct:+.2f}%" if self.pnl_pct is not None else ""
        return (
            f"| {self.created_at:%Y-%m-%d %H:%M:%S} "
            f"| {emoji} **{self.side.upper()}** "
            f"| `{self.symbol}` "
            f"| {self.price:,.0f} KRW "
            f"| {self.amount_krw:,.0f} KRW"
            f"{pnl_str} "
            f"| {self.reason or '-'} |"
        )
