"""
한국투자증권(KIS) 브로커 클라이언트 - 스켈레톤

TODO: 향후 구현 예정
- 국내 주식 매매
- 해외 주식 매매
- KIS Developers API 연동
  (https://apiportal.koreainvestment.com/)
"""

import pandas as pd

from backend.brokers.base import BaseBroker, BrokerType, OrderResult, Position


class KISBroker(BaseBroker):
    """
    한국투자증권 API 브로커 구현 (스켈레톤).
    BaseBroker 인터페이스를 구현하여 동일한 방식으로 사용 가능합니다.
    """

    broker_type = BrokerType.KIS

    def __init__(self):
        # TODO: KIS API 인증 초기화
        pass

    async def get_balance(self) -> dict:
        raise NotImplementedError("KIS 브로커는 아직 구현되지 않았습니다.")

    async def get_positions(self) -> list[Position]:
        raise NotImplementedError("KIS 브로커는 아직 구현되지 않았습니다.")

    async def get_ticker(self, symbol: str) -> dict:
        raise NotImplementedError("KIS 브로커는 아직 구현되지 않았습니다.")

    async def get_tickers(self, symbols: list[str] | None = None) -> list[dict]:
        raise NotImplementedError("KIS 브로커는 아직 구현되지 않았습니다.")

    async def get_orderbook(self, symbol: str) -> dict:
        raise NotImplementedError("KIS 브로커는 아직 구현되지 않았습니다.")

    async def get_ohlcv(
        self, symbol: str, interval: str = "1m", count: int = 200
    ) -> pd.DataFrame:
        raise NotImplementedError("KIS 브로커는 아직 구현되지 않았습니다.")

    async def get_available_symbols(self) -> list[str]:
        raise NotImplementedError("KIS 브로커는 아직 구현되지 않았습니다.")

    async def buy_market(self, symbol: str, amount_krw: float) -> OrderResult:
        raise NotImplementedError("KIS 브로커는 아직 구현되지 않았습니다.")

    async def sell_market(self, symbol: str, quantity: float) -> OrderResult:
        raise NotImplementedError("KIS 브로커는 아직 구현되지 않았습니다.")

    async def get_order(self, order_id: str) -> dict:
        raise NotImplementedError("KIS 브로커는 아직 구현되지 않았습니다.")

    async def cancel_order(self, order_id: str) -> dict:
        raise NotImplementedError("KIS 브로커는 아직 구현되지 않았습니다.")
