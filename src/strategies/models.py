"""Shared strategy result models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

InstrumentType = Literal["stock", "call", "put"]
PositionType = Literal["long", "short"]


@dataclass(frozen=True)
class StrategyLeg:
    """One stock or option leg in a strategy."""

    instrument: InstrumentType
    position: PositionType
    quantity: float
    strike: float | None = None
    premium: float = 0.0
    description: str = ""


@dataclass(frozen=True)
class StrategyResult:
    """Structured output for an option strategy research workflow."""

    name: str
    market_view: str
    legs: list[StrategyLeg]
    max_profit: float
    max_loss: float
    breakeven_points: list[float]
    payoff_curve: pd.DataFrame
    risks: list[str]
    suitable_market: str
    unsuitable_market: str
