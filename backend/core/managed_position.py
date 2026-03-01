from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from backend.brokers.base import Position


class EntrySource(str, Enum):
    TECHNICAL = "technical"
    EVENT = "event"


@dataclass
class ManagedPosition:
    """
    Position 래퍼 - 봇이 매수한 포지션만 추적합니다.
    봇의 매수 수량/가격을 별도로 관리하여 Upbit 합산 포지션과 분리.
    TradingEngine이 dict[str, ManagedPosition]으로 인메모리 관리.
    """
    position: Position
    entry_source: EntrySource
    entry_time: datetime = field(default_factory=datetime.utcnow)

    # 봇 전용 추적 (Upbit 합산 데이터와 분리)
    bot_quantity: float = 0.0       # 봇이 현재 보유한 수량 (부분매도 시 차감)
    bot_avg_price: float = 0.0      # 봇의 매수가 (변경 안 됨)
    current_price: float = 0.0      # 실시간 현재가

    # 부분 익절 추적
    original_quantity: float = 0.0
    first_tp_done: bool = False

    # Moonbag 트레일링 추적
    peak_pnl_pct: float = 0.0

    @property
    def symbol(self) -> str:
        return self.position.symbol

    @property
    def pnl_pct(self) -> float:
        """봇 매수가 기준 수익률"""
        if self.bot_avg_price == 0:
            return 0.0
        return ((self.current_price / self.bot_avg_price) - 1) * 100

    @property
    def bot_pnl(self) -> float:
        """봇 포지션 절대 수익금"""
        if self.bot_avg_price == 0:
            return 0.0
        return (self.current_price - self.bot_avg_price) * self.bot_quantity

    @property
    def bot_value(self) -> float:
        """봇 포지션 평가금액"""
        return self.current_price * self.bot_quantity

    def update_price(self, current_price: float):
        """현재가 업데이트 + 최고 수익률 갱신 (0 이하는 무시)"""
        if current_price <= 0:
            return
        self.current_price = current_price
        if self.pnl_pct > self.peak_pnl_pct:
            self.peak_pnl_pct = self.pnl_pct

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "bot_quantity": self.bot_quantity,
            "bot_avg_price": self.bot_avg_price,
            "current_price": self.current_price,
            "bot_pnl": round(self.bot_pnl, 2),
            "bot_pnl_pct": round(self.pnl_pct, 4),
            "bot_value": round(self.bot_value, 2),
            "entry_source": self.entry_source.value,
            "original_quantity": self.original_quantity,
            "first_tp_done": self.first_tp_done,
            "peak_pnl_pct": round(self.peak_pnl_pct, 4),
        }
