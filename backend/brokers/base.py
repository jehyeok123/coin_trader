from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

import pandas as pd


class BrokerType(str, Enum):
    UPBIT = "upbit"
    KIS = "kis"  # 한국투자증권 (TODO)


@dataclass
class OrderResult:
    order_id: str
    symbol: str
    side: str  # "buy" | "sell"
    price: float
    quantity: float
    amount: float
    status: str
    raw: dict = field(default_factory=dict)


@dataclass
class Position:
    symbol: str
    quantity: float
    avg_price: float
    current_price: float = 0.0

    @property
    def pnl(self) -> float:
        if self.avg_price == 0:
            return 0.0
        return (self.current_price - self.avg_price) * self.quantity

    @property
    def pnl_pct(self) -> float:
        if self.avg_price == 0:
            return 0.0
        return ((self.current_price / self.avg_price) - 1) * 100

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "avg_price": self.avg_price,
            "current_price": self.current_price,
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
        }


class BaseBroker(ABC):
    """
    브로커 추상 인터페이스.
    모든 브로커(업비트, 한국투자증권 등)는 이 인터페이스를 구현해야 합니다.
    """

    broker_type: BrokerType

    @abstractmethod
    async def get_balance(self) -> dict:
        """현금 잔고 및 보유 자산 조회"""
        ...

    @abstractmethod
    async def get_positions(self) -> list[Position]:
        """현재 보유 포지션 목록 조회"""
        ...

    @abstractmethod
    async def get_ticker(self, symbol: str) -> dict:
        """특정 종목의 현재 시세 조회"""
        ...

    @abstractmethod
    async def get_tickers(self, symbols: list[str] | None = None) -> list[dict]:
        """여러 종목의 시세 일괄 조회"""
        ...

    @abstractmethod
    async def get_full_tickers(self, symbols: list[str] | None = None) -> list[dict]:
        """여러 종목의 전체 시세 데이터 일괄 조회 (거래대금 포함)"""
        ...

    @abstractmethod
    async def get_orderbook(self, symbol: str) -> dict:
        """호가창 조회"""
        ...

    @abstractmethod
    async def get_ohlcv(
        self, symbol: str, interval: str = "1m", count: int = 200
    ) -> pd.DataFrame:
        """
        OHLCV 캔들 데이터 조회.
        interval: "1m", "5m", "15m", "1h", "4h", "1d" 등
        """
        ...

    @abstractmethod
    async def get_available_symbols(self) -> list[str]:
        """거래 가능한 심볼 목록 조회"""
        ...

    @abstractmethod
    async def buy_market(self, symbol: str, amount_krw: float) -> OrderResult:
        """시장가 매수 (KRW 기준 금액)"""
        ...

    @abstractmethod
    async def sell_market(self, symbol: str, quantity: float) -> OrderResult:
        """시장가 매도 (수량 기준)"""
        ...

    @abstractmethod
    async def get_order(self, order_id: str) -> dict:
        """주문 상태 조회"""
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> dict:
        """주문 취소"""
        ...
