from src.backtest import RESEARCH_DISCLAIMER, BacktestResult, run_mock_backtest, run_strategy_backtest
from src.data import MockMarketDataProvider


def test_covered_call_backtest_runs_on_mock_history() -> None:
    history = MockMarketDataProvider().get_history("SPY", period="1y")

    result = run_strategy_backtest(history, "covered_call", holding_period_days=21)

    assert isinstance(result, BacktestResult)
    assert result.strategy_name == "Covered Call"
    assert not result.equity_curve.empty
    assert not result.trades.empty
    assert "return" in result.trades.columns
    assert -1 <= result.max_drawdown <= 0
    assert 0 <= result.win_rate <= 1
    assert result.disclaimer == RESEARCH_DISCLAIMER


def test_protective_put_backtest_runs_on_mock_history() -> None:
    history = MockMarketDataProvider().get_history("QQQ", period="1y")

    result = run_strategy_backtest(history, "protective_put", holding_period_days=21)

    assert result.strategy_name == "Protective Put"
    assert not result.equity_curve.empty
    assert not result.trades.empty
    assert result.trades["capital"].gt(0).all()


def test_bull_call_spread_backtest_runs_on_mock_history() -> None:
    history = MockMarketDataProvider().get_history("AAPL", period="1y")

    result = run_strategy_backtest(history, "bull_call_spread", holding_period_days=21)

    assert result.strategy_name == "Bull Call Spread"
    assert not result.equity_curve.empty
    assert not result.trades.empty
    assert result.trades["capital"].gt(0).all()


def test_run_mock_backtest_fetches_history_and_runs() -> None:
    result = run_mock_backtest("SPY", "covered_call", period="6mo")

    assert result.strategy_name == "Covered Call"
    assert not result.equity_curve.empty
    assert "education and research" in result.disclaimer
