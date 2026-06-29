"""Simplified option strategy simulator for research prototypes.

This module is intentionally not an institution-grade options backtester. It
uses historical close prices, estimated option premiums, fixed holding windows,
and expiration payoff. It ignores execution quality, bid/ask slippage, early
assignment, margin, corporate actions, taxes, and liquidity constraints.

Education and research only. Not financial advice.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Literal

import numpy as np
import pandas as pd

from src.backtest.models import BacktestResult, RESEARCH_DISCLAIMER
from src.data import MarketDataClient, historical_volatility
from src.pricing import black_scholes_price
from src.strategies import bull_call_spread, covered_call, protective_put

StrategyType = Literal["covered_call", "protective_put", "bull_call_spread"]


def run_strategy_backtest(
    history: pd.DataFrame,
    strategy_type: StrategyType,
    holding_period_days: int = 21,
    rebalance_days: int | None = None,
    risk_free_rate: float = 0.04,
    otm_pct: float = 0.05,
    spread_width_pct: float = 0.08,
    initial_equity: float = 1.0,
) -> BacktestResult:
    """Run a simplified rolling expiration-payoff simulation.

    The returned equity curve compounds per-trade returns. For stock-based
    strategies, returns are scaled by stock capital. For debit spreads, returns
    are scaled by the net debit paid.
    """

    prices = _extract_close_prices(history)
    _validate_positive_int("holding_period_days", holding_period_days)
    if rebalance_days is None:
        rebalance_days = holding_period_days
    _validate_positive_int("rebalance_days", rebalance_days)
    _validate_positive("risk_free_rate", risk_free_rate, allow_zero=True)
    _validate_positive("otm_pct", otm_pct)
    _validate_positive("spread_width_pct", spread_width_pct)
    _validate_positive("initial_equity", initial_equity)
    if strategy_type not in {"covered_call", "protective_put", "bull_call_spread"}:
        raise ValueError("strategy_type must be covered_call, protective_put, or bull_call_spread")
    if len(prices) <= holding_period_days:
        raise ValueError("history must contain more rows than holding_period_days")

    trades: list[dict[str, object]] = []
    equity = initial_equity
    equity_rows = [{"date": prices.index[0], "equity": equity, "trade_return": 0.0}]

    for entry_idx in range(0, len(prices) - holding_period_days, rebalance_days):
        exit_idx = entry_idx + holding_period_days
        entry_date = prices.index[entry_idx]
        exit_date = prices.index[exit_idx]
        entry_price = float(prices.iloc[entry_idx])
        exit_price = float(prices.iloc[exit_idx])
        sigma = _estimate_volatility(history=prices.iloc[: entry_idx + 1].to_frame("Close"))
        trade = _simulate_trade(
            strategy_type=strategy_type,
            entry_price=entry_price,
            exit_price=exit_price,
            holding_period_days=holding_period_days,
            risk_free_rate=risk_free_rate,
            sigma=sigma,
            otm_pct=otm_pct,
            spread_width_pct=spread_width_pct,
        )
        equity *= 1 + trade["return"]
        trades.append(
            {
                "entry_date": entry_date,
                "exit_date": exit_date,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "historical_volatility": sigma,
                **trade,
            }
        )
        equity_rows.append({"date": exit_date, "equity": equity, "trade_return": trade["return"]})

    trades_frame = pd.DataFrame(trades)
    equity_curve = pd.DataFrame(equity_rows)
    returns = trades_frame["return"] if not trades_frame.empty else pd.Series(dtype=float)

    return BacktestResult(
        strategy_name=_strategy_display_name(strategy_type),
        cumulative_return=float(equity / initial_equity - 1),
        max_drawdown=_max_drawdown(equity_curve["equity"]),
        win_rate=float((returns > 0).mean()) if not returns.empty else 0.0,
        average_return=float(returns.mean()) if not returns.empty else 0.0,
        equity_curve=equity_curve,
        trades=trades_frame,
        disclaimer=RESEARCH_DISCLAIMER,
    )


def run_mock_backtest(
    symbol: str,
    strategy_type: StrategyType,
    period: str = "1y",
    prefer_mock: bool = True,
    **kwargs,
) -> BacktestResult:
    """Fetch history through the data layer and run the simplified simulation."""

    client = MarketDataClient(prefer_mock=prefer_mock)
    history = client.get_history(symbol=symbol, period=period)
    return run_strategy_backtest(history=history, strategy_type=strategy_type, **kwargs)


def _simulate_trade(
    strategy_type: StrategyType,
    entry_price: float,
    exit_price: float,
    holding_period_days: int,
    risk_free_rate: float,
    sigma: float,
    otm_pct: float,
    spread_width_pct: float,
) -> dict[str, object]:
    time_to_expiry = holding_period_days / 252
    if strategy_type == "covered_call":
        call_strike = entry_price * (1 + otm_pct)
        call_premium = _option_price(entry_price, call_strike, time_to_expiry, risk_free_rate, sigma, "call")
        strategy = covered_call(entry_price, call_strike, call_premium)
        pnl = exit_price - entry_price + call_premium - max(exit_price - call_strike, 0)
        capital = entry_price
        return _trade_result(strategy.name, pnl, capital, {"call_strike": call_strike, "call_premium": call_premium})

    if strategy_type == "protective_put":
        put_strike = entry_price * (1 - otm_pct)
        put_premium = _option_price(entry_price, put_strike, time_to_expiry, risk_free_rate, sigma, "put")
        strategy = protective_put(entry_price, put_strike, put_premium)
        pnl = exit_price - entry_price + max(put_strike - exit_price, 0) - put_premium
        capital = entry_price + put_premium
        return _trade_result(strategy.name, pnl, capital, {"put_strike": put_strike, "put_premium": put_premium})

    lower_strike = entry_price
    higher_strike = entry_price * (1 + spread_width_pct)
    long_call_premium = _option_price(
        entry_price, lower_strike, time_to_expiry, risk_free_rate, sigma, "call"
    )
    short_call_premium = _option_price(
        entry_price, higher_strike, time_to_expiry, risk_free_rate, sigma, "call"
    )
    strategy = bull_call_spread(
        lower_strike=lower_strike,
        higher_strike=higher_strike,
        long_call_premium=long_call_premium,
        short_call_premium=short_call_premium,
        spot=entry_price,
    )
    net_debit = long_call_premium - short_call_premium
    pnl = max(exit_price - lower_strike, 0) - max(exit_price - higher_strike, 0) - net_debit
    return _trade_result(
        strategy.name,
        pnl,
        net_debit,
        {
            "lower_strike": lower_strike,
            "higher_strike": higher_strike,
            "long_call_premium": long_call_premium,
            "short_call_premium": short_call_premium,
        },
    )


def _trade_result(
    strategy_name: str,
    pnl: float,
    capital: float,
    details: dict[str, float],
) -> dict[str, object]:
    _validate_positive("capital", capital)
    return {
        "strategy_name": strategy_name,
        "pnl": float(pnl),
        "capital": float(capital),
        "return": float(pnl / capital),
        **{key: float(value) for key, value in details.items()},
    }


def _option_price(
    spot: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    sigma: float,
    option_type: Literal["call", "put"],
) -> float:
    return black_scholes_price(
        spot=spot,
        strike=strike,
        time_to_expiry=time_to_expiry,
        risk_free_rate=risk_free_rate,
        volatility=max(sigma, 0.05),
        option_type=option_type,
    )


def _extract_close_prices(history: pd.DataFrame) -> pd.Series:
    if history.empty:
        raise ValueError("history must not be empty")
    close_column = "Adj Close" if "Adj Close" in history.columns else "Close"
    if close_column not in history.columns:
        raise ValueError("history must contain either 'Adj Close' or 'Close'")
    prices = history[close_column].dropna().astype(float)
    if (prices <= 0).any():
        raise ValueError("close prices must be positive")
    if not isinstance(prices.index, pd.DatetimeIndex):
        prices.index = pd.to_datetime(prices.index)
    return prices


def _estimate_volatility(history: pd.DataFrame, fallback: float = 0.25) -> float:
    try:
        if len(history) < 30:
            return fallback
        return max(historical_volatility(history.tail(63)), 0.05)
    except ValueError:
        return fallback


def _max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    running_max = equity.cummax()
    drawdowns = equity / running_max - 1
    return float(drawdowns.min())


def _strategy_display_name(strategy_type: StrategyType) -> str:
    names = {
        "covered_call": "Covered Call",
        "protective_put": "Protective Put",
        "bull_call_spread": "Bull Call Spread",
    }
    return names[strategy_type]


def _validate_positive_int(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _validate_positive(name: str, value: float, allow_zero: bool = False) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if allow_zero:
        if value < 0:
            raise ValueError(f"{name} must be non-negative")
    elif value <= 0:
        raise ValueError(f"{name} must be positive")
