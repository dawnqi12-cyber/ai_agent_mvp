"""Volatility calculations for market data."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def historical_volatility(
    history: pd.DataFrame,
    close_column: str | None = None,
    trading_days: int = 252,
) -> float:
    """Return annualized historical volatility from close-to-close log returns."""

    if history.empty:
        raise ValueError("history must not be empty")
    if trading_days <= 0:
        raise ValueError("trading_days must be positive")

    selected_close_column = close_column or _default_close_column(history)
    closes = history[selected_close_column].dropna().astype(float)
    if len(closes) < 2:
        raise ValueError("history must contain at least two closing prices")
    if (closes <= 0).any():
        raise ValueError("closing prices must be positive")

    log_returns = np.log(closes / closes.shift(1)).dropna()
    if log_returns.empty:
        raise ValueError("history must contain at least one return")

    return float(log_returns.std(ddof=1) * math.sqrt(trading_days))


def _default_close_column(history: pd.DataFrame) -> str:
    if "Adj Close" in history.columns:
        return "Adj Close"
    if "Close" in history.columns:
        return "Close"
    raise ValueError("history must contain either 'Adj Close' or 'Close'")
