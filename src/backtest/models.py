"""Shared models for simplified strategy simulation."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

RESEARCH_DISCLAIMER = (
    "This simplified backtest is for education and research only. "
    "It ignores many real-world trading details and is not financial advice."
)


@dataclass(frozen=True)
class BacktestResult:
    """Summary and time series output from a simplified strategy simulation."""

    strategy_name: str
    cumulative_return: float
    max_drawdown: float
    win_rate: float
    average_return: float
    equity_curve: pd.DataFrame
    trades: pd.DataFrame
    disclaimer: str = RESEARCH_DISCLAIMER
