"""Shared market data models."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class MarketSnapshot:
    """Current market state for a ticker."""

    symbol: str
    price: float
    provider: str
    currency: str = "USD"


@dataclass(frozen=True)
class OptionChain:
    """Call and put option chain data for one expiration date."""

    symbol: str
    expiration: str
    calls: pd.DataFrame
    puts: pd.DataFrame
    provider: str


class DataProviderError(RuntimeError):
    """Raised when a market data provider cannot return usable data."""
