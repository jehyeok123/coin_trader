import numpy as np
import pandas as pd

from backend.config.settings import load_trading_rules
from backend.utils.logger import logger


class RuleEngine:
    """
    매매 규칙 평가 엔진.
    15분봉 눌림목 전략 (200 EMA + 20 EMA + RSI) 기반 진입 시그널을 생성합니다.
    청산 로직은 TradingEngine에서 ManagedPosition 기반으로 처리합니다.
    """

    def __init__(self):
        self._rules = load_trading_rules()

    def reload_rules(self):
        self._rules = load_trading_rules()
        logger.info("매매 규칙 리로드 완료")

    @property
    def rules(self) -> dict:
        return self._rules

    def evaluate(self, symbol: str, df: pd.DataFrame, current_price: float) -> dict:
        """
        15분봉 정배열 전략 평가.
        진입 조건 (ALL must be true):
          - 현재가 > EMA(20) > EMA(200) (정배열 — 불변 조건)
          - rsi_min <= RSI <= rsi_max (설정 가능, 0이면 해당 바운드 비활성화)
        """
        tech = self._rules.get("technical_strategy", {})
        entry = tech.get("entry", {})
        ema_long_period = entry.get("ema_long", 200)
        ema_short_period = entry.get("ema_short", 20)
        rsi_period = entry.get("rsi_period", 14)
        rsi_min = entry.get("rsi_min", 0)
        rsi_max = entry.get("rsi_max", 0)

        min_candles = max(ema_long_period, 50)
        if df is None or df.empty or len(df) < min_candles:
            return {
                "action": "hold",
                "confidence": 0.0,
                "reasons": [f"데이터 부족 ({len(df) if df is not None else 0}/{min_candles}봉 필요)"],
                "indicators": {},
            }

        ema_long = self._calculate_ema(df, ema_long_period)
        ema_short = self._calculate_ema(df, ema_short_period)
        rsi = self._calculate_rsi(df, rsi_period)

        ema_long_val = float(ema_long.iloc[-1])
        ema_short_val = float(ema_short.iloc[-1])

        indicators = {
            f"ema_{ema_long_period}": round(ema_long_val, 2),
            f"ema_{ema_short_period}": round(ema_short_val, 2),
            "rsi": round(rsi, 2),
            "current_price": current_price,
        }

        # 고정 조건: 현재가 > EMA20 > EMA200 (정배열)
        conditions = [
            (f"price > E{ema_short_period}", current_price > ema_short_val),
            (f"E{ema_short_period} > E{ema_long_period}", ema_short_val > ema_long_val),
        ]

        # RSI 조건: 0이면 해당 바운드 비활성화
        if rsi_min > 0:
            conditions.append((f"RSI >= {rsi_min}", rsi >= rsi_min))
        if rsi_max > 0:
            conditions.append((f"RSI <= {rsi_max}", rsi <= rsi_max))

        all_met = all(c[1] for c in conditions)
        met = [c[0] for c in conditions if c[1]]
        unmet = [f"{c[0]} 미충족" for c in conditions if not c[1]]

        if all_met:
            return {
                "action": "buy",
                "confidence": 0.8,
                "reasons": met,
                "indicators": indicators,
            }

        return {
            "action": "hold",
            "confidence": 0.0,
            "reasons": unmet,
            "indicators": indicators,
        }

    def passes_filters(self, symbol: str) -> bool:
        """블랙리스트/화이트리스트 필터"""
        filters = self._rules.get("filters", {})
        blacklist = filters.get("blacklist", [])
        whitelist = filters.get("whitelist", [])

        if symbol in blacklist:
            return False
        if whitelist and symbol not in whitelist:
            return False
        return True

    @staticmethod
    def _calculate_ema(df: pd.DataFrame, period: int) -> pd.Series:
        return df["close"].ewm(span=period, adjust=False).mean()

    @staticmethod
    def _calculate_rsi(df: pd.DataFrame, period: int = 14) -> float:
        close = df["close"]
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iloc[-1]) if not rsi.empty and not np.isnan(rsi.iloc[-1]) else 50.0
