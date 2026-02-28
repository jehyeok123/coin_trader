import numpy as np
import pandas as pd

from backend.config.settings import load_trading_rules
from backend.utils.logger import logger


class RuleEngine:
    """
    JSON 기반 매매 규칙 평가 엔진.
    규칙에 정의된 지표와 필터를 기반으로 매매 시그널을 생성합니다.

    현재는 스켈레톤 구현이며, 구체적인 규칙과 지표는 향후 상세화됩니다.
    """

    def __init__(self):
        self._rules = load_trading_rules()

    def reload_rules(self):
        """규칙을 다시 로드"""
        self._rules = load_trading_rules()
        logger.info("매매 규칙 리로드 완료")

    @property
    def rules(self) -> dict:
        return self._rules

    def evaluate(self, symbol: str, df: pd.DataFrame, current_price: float) -> dict:
        """
        주어진 OHLCV 데이터와 규칙을 기반으로 매매 시그널을 평가합니다.

        Args:
            symbol: 종목 심볼
            df: OHLCV 데이터프레임
            current_price: 현재 가격

        Returns:
            dict: {
                "action": "buy" | "sell" | "hold",
                "confidence": 0.0 ~ 1.0,
                "reasons": ["reason1", "reason2"],
                "indicators": {"rsi": 25.3, ...}
            }
        """
        if df is None or df.empty or len(df) < 20:
            return {
                "action": "hold",
                "confidence": 0.0,
                "reasons": ["데이터 부족"],
                "indicators": {},
            }

        indicators = {}
        buy_signals = []
        sell_signals = []

        # RSI 계산 및 평가
        if self._rules.get("indicators", {}).get("rsi", {}).get("enabled", False):
            rsi = self._calculate_rsi(df, self._rules["indicators"]["rsi"]["period"])
            indicators["rsi"] = round(rsi, 2)
            oversold = self._rules["indicators"]["rsi"]["oversold"]
            overbought = self._rules["indicators"]["rsi"]["overbought"]
            if rsi < oversold:
                buy_signals.append(f"RSI 과매도 ({rsi:.1f} < {oversold})")
            elif rsi > overbought:
                sell_signals.append(f"RSI 과매수 ({rsi:.1f} > {overbought})")

        # 거래량 급증 평가
        if self._rules.get("indicators", {}).get("volume_spike", {}).get("enabled", False):
            vol_config = self._rules["indicators"]["volume_spike"]
            is_spike, vol_ratio = self._check_volume_spike(
                df,
                vol_config["threshold_multiplier"],
                vol_config["lookback_periods"],
            )
            indicators["volume_ratio"] = round(vol_ratio, 2)
            if is_spike:
                buy_signals.append(f"거래량 급증 (x{vol_ratio:.1f})")

        # MACD (스켈레톤 - 활성화 시 계산)
        if self._rules.get("indicators", {}).get("macd", {}).get("enabled", False):
            macd_config = self._rules["indicators"]["macd"]
            macd_result = self._calculate_macd(
                df,
                macd_config["fast_period"],
                macd_config["slow_period"],
                macd_config["signal_period"],
            )
            indicators["macd"] = macd_result
            if macd_result.get("crossover") == "golden":
                buy_signals.append("MACD 골든크로스")
            elif macd_result.get("crossover") == "dead":
                sell_signals.append("MACD 데드크로스")

        # 볼린저 밴드 (스켈레톤)
        if self._rules.get("indicators", {}).get("bollinger_bands", {}).get("enabled", False):
            bb_config = self._rules["indicators"]["bollinger_bands"]
            bb = self._calculate_bollinger(df, bb_config["period"], bb_config["std_dev"])
            indicators["bollinger"] = bb
            if current_price < bb.get("lower", 0):
                buy_signals.append("볼린저 하단 돌파")
            elif current_price > bb.get("upper", float("inf")):
                sell_signals.append("볼린저 상단 돌파")

        # 종합 판단
        if buy_signals and not sell_signals:
            action = "buy"
            confidence = min(len(buy_signals) * 0.3, 1.0)
            reasons = buy_signals
        elif sell_signals and not buy_signals:
            action = "sell"
            confidence = min(len(sell_signals) * 0.3, 1.0)
            reasons = sell_signals
        elif buy_signals and sell_signals:
            action = "hold"
            confidence = 0.3
            reasons = ["혼합 시그널: " + ", ".join(buy_signals + sell_signals)]
        else:
            action = "hold"
            confidence = 0.0
            reasons = ["시그널 없음"]

        return {
            "action": action,
            "confidence": confidence,
            "reasons": reasons,
            "indicators": indicators,
        }

    def check_stop_loss(self, avg_price: float, current_price: float) -> bool:
        """손절 조건 확인"""
        if avg_price <= 0:
            return False
        pnl_pct = ((current_price / avg_price) - 1) * 100
        return pnl_pct <= -self._rules.get("trading", {}).get("stop_loss_pct", 3.0)

    def check_take_profit(self, avg_price: float, current_price: float) -> bool:
        """익절 조건 확인"""
        if avg_price <= 0:
            return False
        pnl_pct = ((current_price / avg_price) - 1) * 100
        return pnl_pct >= self._rules.get("trading", {}).get("take_profit_pct", 5.0)

    def passes_filters(self, symbol: str, volume_24h: float) -> bool:
        """필터 조건을 통과하는지 확인"""
        filters = self._rules.get("filters", {})
        min_vol = filters.get("min_volume_24h_krw", 0)
        blacklist = filters.get("blacklist", [])
        whitelist = filters.get("whitelist", [])

        if symbol in blacklist:
            return False
        if whitelist and symbol not in whitelist:
            return False
        if volume_24h < min_vol:
            return False
        return True

    @staticmethod
    def _calculate_rsi(df: pd.DataFrame, period: int = 14) -> float:
        """RSI 계산"""
        close = df["close"]
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iloc[-1]) if not rsi.empty and not np.isnan(rsi.iloc[-1]) else 50.0

    @staticmethod
    def _check_volume_spike(
        df: pd.DataFrame, threshold: float, lookback: int
    ) -> tuple[bool, float]:
        """거래량 급증 확인"""
        if len(df) < lookback + 1:
            return False, 1.0
        current_vol = df["volume"].iloc[-1]
        avg_vol = df["volume"].iloc[-lookback - 1 : -1].mean()
        if avg_vol <= 0:
            return False, 1.0
        ratio = current_vol / avg_vol
        return ratio >= threshold, ratio

    @staticmethod
    def _calculate_macd(
        df: pd.DataFrame, fast: int, slow: int, signal: int
    ) -> dict:
        """MACD 계산"""
        close = df["close"]
        ema_fast = close.ewm(span=fast).mean()
        ema_slow = close.ewm(span=slow).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal).mean()
        histogram = macd_line - signal_line

        crossover = "none"
        if len(histogram) >= 2:
            if histogram.iloc[-1] > 0 and histogram.iloc[-2] <= 0:
                crossover = "golden"
            elif histogram.iloc[-1] < 0 and histogram.iloc[-2] >= 0:
                crossover = "dead"

        return {
            "macd": round(float(macd_line.iloc[-1]), 4),
            "signal": round(float(signal_line.iloc[-1]), 4),
            "histogram": round(float(histogram.iloc[-1]), 4),
            "crossover": crossover,
        }

    @staticmethod
    def _calculate_bollinger(df: pd.DataFrame, period: int, std_dev: float) -> dict:
        """볼린저 밴드 계산"""
        close = df["close"]
        sma = close.rolling(window=period).mean()
        std = close.rolling(window=period).std()
        upper = sma + std_dev * std
        lower = sma - std_dev * std
        return {
            "upper": round(float(upper.iloc[-1]), 2),
            "middle": round(float(sma.iloc[-1]), 2),
            "lower": round(float(lower.iloc[-1]), 2),
        }
