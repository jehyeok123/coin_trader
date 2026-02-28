from dataclasses import dataclass
from datetime import datetime


@dataclass
class UpbitTicker:
    market: str
    trade_price: float
    trade_volume: float
    acc_trade_price_24h: float
    acc_trade_volume_24h: float
    signed_change_rate: float
    highest_52_week_price: float
    lowest_52_week_price: float
    timestamp: int

    @classmethod
    def from_dict(cls, data: dict) -> "UpbitTicker":
        return cls(
            market=data.get("market", ""),
            trade_price=float(data.get("trade_price", 0)),
            trade_volume=float(data.get("trade_volume", 0)),
            acc_trade_price_24h=float(data.get("acc_trade_price_24h", 0)),
            acc_trade_volume_24h=float(data.get("acc_trade_volume_24h", 0)),
            signed_change_rate=float(data.get("signed_change_rate", 0)),
            highest_52_week_price=float(data.get("highest_52_week_price", 0)),
            lowest_52_week_price=float(data.get("lowest_52_week_price", 0)),
            timestamp=int(data.get("timestamp", 0)),
        )

    def to_dict(self) -> dict:
        return {
            "market": self.market,
            "trade_price": self.trade_price,
            "trade_volume": self.trade_volume,
            "acc_trade_price_24h": self.acc_trade_price_24h,
            "acc_trade_volume_24h": self.acc_trade_volume_24h,
            "signed_change_rate": self.signed_change_rate,
            "change_rate_pct": self.signed_change_rate * 100,
            "highest_52_week_price": self.highest_52_week_price,
            "lowest_52_week_price": self.lowest_52_week_price,
        }


@dataclass
class UpbitCandle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def to_dict(self) -> dict:
        return {
            "time": int(self.timestamp.timestamp()),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }
