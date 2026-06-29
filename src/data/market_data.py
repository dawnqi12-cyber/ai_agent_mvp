"""Unified market data interface with yfinance-to-mock fallback."""

from __future__ import annotations

from datetime import date
from typing import Protocol

import pandas as pd

from src.data.mock_provider import MockMarketDataProvider
from src.data.models import MarketSnapshot, OptionChain
from src.data.yfinance_provider import YFinanceMarketDataProvider


class MarketDataProvider(Protocol):
    name: str

    def get_current_price(self, symbol: str) -> float: ...

    def get_history(
        self,
        symbol: str,
        start: str | date | None = None,
        end: str | date | None = None,
        period: str = "1y",
    ) -> pd.DataFrame: ...

    def get_expirations(self, symbol: str) -> list[str]: ...

    def get_option_chain(self, symbol: str, expiration: str | None = None) -> OptionChain: ...


class MarketDataClient:
    """Primary data access point for later Agent and UI layers."""

    def __init__(
        self,
        primary_provider: MarketDataProvider | None = None,
        fallback_provider: MarketDataProvider | None = None,
        prefer_mock: bool = False,
    ) -> None:
        self.primary_provider = primary_provider or YFinanceMarketDataProvider()
        self.fallback_provider = fallback_provider or MockMarketDataProvider()
        self.prefer_mock = prefer_mock
        self.last_provider: str | None = None
        self.last_fallback_reason: str | None = None

    def get_current_price(self, symbol: str) -> float:
        return float(self._call_provider("get_current_price", symbol))

    def get_snapshot(self, symbol: str) -> MarketSnapshot:
        price = self.get_current_price(symbol)
        return MarketSnapshot(symbol=symbol.upper().strip(), price=price, provider=self.last_provider or "unknown")

    def get_history(
        self,
        symbol: str,
        start: str | date | None = None,
        end: str | date | None = None,
        period: str = "1y",
    ) -> pd.DataFrame:
        return self._call_provider("get_history", symbol, start=start, end=end, period=period)

    def get_expirations(self, symbol: str) -> list[str]:
        return list(self._call_provider("get_expirations", symbol))

    def get_option_chain(self, symbol: str, expiration: str | None = None) -> OptionChain:
        return self._call_provider("get_option_chain", symbol, expiration=expiration)

    def _call_provider(self, method_name: str, symbol: str, **kwargs):
        if self.prefer_mock:
            self.last_fallback_reason = "prefer_mock is enabled"
            return self._call_specific_provider(self.fallback_provider, method_name, symbol, **kwargs)

        try:
            self.last_fallback_reason = None
            return self._call_specific_provider(self.primary_provider, method_name, symbol, **kwargs)
        except Exception as exc:
            self.last_fallback_reason = f"{type(exc).__name__}: {exc}"
            return self._call_specific_provider(self.fallback_provider, method_name, symbol, **kwargs)

    def _call_specific_provider(
        self,
        provider: MarketDataProvider,
        method_name: str,
        symbol: str,
        **kwargs,
    ):
        method = getattr(provider, method_name)
        result = method(symbol, **kwargs)
        self.last_provider = provider.name
        return result
