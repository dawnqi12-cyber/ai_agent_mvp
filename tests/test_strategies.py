import math

import pytest

from src.strategies import (
    StrategyResult,
    bear_put_spread,
    bull_call_spread,
    covered_call,
    iron_condor,
    protective_put,
)


@pytest.mark.parametrize(
    "strategy",
    [
        covered_call(spot=100, call_strike=110, call_premium=3),
        protective_put(spot=100, put_strike=95, put_premium=2),
        bull_call_spread(
            lower_strike=100,
            higher_strike=110,
            long_call_premium=6,
            short_call_premium=2,
        ),
        bear_put_spread(
            lower_strike=90,
            higher_strike=100,
            long_put_premium=7,
            short_put_premium=2,
        ),
        iron_condor(
            long_put_strike=85,
            short_put_strike=90,
            short_call_strike=110,
            long_call_strike=115,
            long_put_premium=1,
            short_put_premium=2,
            short_call_premium=2,
            long_call_premium=1,
        ),
    ],
)
def test_strategy_generates_explainable_result(strategy: StrategyResult) -> None:
    assert strategy.name
    assert strategy.market_view
    assert strategy.legs
    assert strategy.max_loss >= 0
    assert strategy.breakeven_points
    assert strategy.risks
    assert strategy.suitable_market
    assert strategy.unsuitable_market
    assert {"underlying_price", "payoff"}.issubset(strategy.payoff_curve.columns)
    assert len(strategy.payoff_curve) == 101


def test_covered_call_key_metrics() -> None:
    result = covered_call(spot=100, call_strike=110, call_premium=3)

    assert result.max_profit == pytest.approx(13)
    assert result.max_loss == pytest.approx(97)
    assert result.breakeven_points == pytest.approx([97])


def test_protective_put_has_unlimited_upside_and_defined_loss() -> None:
    result = protective_put(spot=100, put_strike=95, put_premium=2)

    assert math.isinf(result.max_profit)
    assert result.max_loss == pytest.approx(7)
    assert result.breakeven_points == pytest.approx([102])


def test_bull_call_spread_key_metrics() -> None:
    result = bull_call_spread(
        lower_strike=100,
        higher_strike=110,
        long_call_premium=6,
        short_call_premium=2,
    )

    assert result.max_profit == pytest.approx(6)
    assert result.max_loss == pytest.approx(4)
    assert result.breakeven_points == pytest.approx([104])


def test_bear_put_spread_key_metrics() -> None:
    result = bear_put_spread(
        lower_strike=90,
        higher_strike=100,
        long_put_premium=7,
        short_put_premium=2,
    )

    assert result.max_profit == pytest.approx(5)
    assert result.max_loss == pytest.approx(5)
    assert result.breakeven_points == pytest.approx([95])


def test_iron_condor_key_metrics() -> None:
    result = iron_condor(
        long_put_strike=85,
        short_put_strike=90,
        short_call_strike=110,
        long_call_strike=115,
        long_put_premium=1,
        short_put_premium=2,
        short_call_premium=2,
        long_call_premium=1,
    )

    assert result.max_profit == pytest.approx(2)
    assert result.max_loss == pytest.approx(3)
    assert result.breakeven_points == pytest.approx([88, 112])


def test_invalid_spread_strikes_raise_error() -> None:
    with pytest.raises(ValueError, match="lower_strike must be less than higher_strike"):
        bull_call_spread(
            lower_strike=110,
            higher_strike=100,
            long_call_premium=6,
            short_call_premium=2,
        )
