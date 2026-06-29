"""Backtesting package."""

from src.backtest.models import BacktestResult, RESEARCH_DISCLAIMER
from src.backtest.simulator import run_mock_backtest, run_strategy_backtest

__all__ = [
    "BacktestResult",
    "RESEARCH_DISCLAIMER",
    "run_mock_backtest",
    "run_strategy_backtest",
]
