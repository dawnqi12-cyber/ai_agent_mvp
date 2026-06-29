"""Explainable option strategy constructors and payoff calculators."""

from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np
import pandas as pd

from src.strategies.models import StrategyLeg, StrategyResult


def covered_call(
    spot: float,
    call_strike: float,
    call_premium: float,
    num_points: int = 101,
) -> StrategyResult:
    """Long stock plus short call."""

    _validate_positive("spot", spot)
    _validate_positive("call_strike", call_strike)
    _validate_non_negative("call_premium", call_premium)

    prices = _price_grid(spot, [call_strike], num_points)
    payoff = prices - spot + call_premium - np.maximum(prices - call_strike, 0)

    return StrategyResult(
        name="Covered Call",
        market_view="Neutral to mildly bullish; willing to cap upside in exchange for option income.",
        legs=[
            StrategyLeg("stock", "long", 1, premium=spot, description="Buy underlying stock"),
            StrategyLeg(
                "call",
                "short",
                1,
                strike=call_strike,
                premium=call_premium,
                description="Sell call option",
            ),
        ],
        max_profit=call_strike - spot + call_premium,
        max_loss=max(0.0, spot - call_premium),
        breakeven_points=[spot - call_premium],
        payoff_curve=_payoff_frame(prices, payoff),
        risks=[
            "Upside is capped above the short call strike.",
            "Downside stock risk remains significant if the underlying falls sharply.",
            "Assignment risk exists when the short call is in the money.",
        ],
        suitable_market="Sideways to moderately rising markets with elevated call premiums.",
        unsuitable_market="Strong bull markets or sharp selloffs.",
    )


def protective_put(
    spot: float,
    put_strike: float,
    put_premium: float,
    num_points: int = 101,
) -> StrategyResult:
    """Long stock plus long put."""

    _validate_positive("spot", spot)
    _validate_positive("put_strike", put_strike)
    _validate_non_negative("put_premium", put_premium)

    prices = _price_grid(spot, [put_strike], num_points)
    payoff = prices - spot + np.maximum(put_strike - prices, 0) - put_premium

    return StrategyResult(
        name="Protective Put",
        market_view="Bullish on the underlying but wants defined downside protection.",
        legs=[
            StrategyLeg("stock", "long", 1, premium=spot, description="Buy underlying stock"),
            StrategyLeg(
                "put",
                "long",
                1,
                strike=put_strike,
                premium=put_premium,
                description="Buy protective put",
            ),
        ],
        max_profit=math.inf,
        max_loss=max(0.0, spot + put_premium - put_strike),
        breakeven_points=[spot + put_premium],
        payoff_curve=_payoff_frame(prices, payoff),
        risks=[
            "Protection has a cost and raises the breakeven price.",
            "Upside remains exposed to the premium drag.",
            "Put protection only applies through the selected expiration.",
        ],
        suitable_market="Bullish markets where the investor still wants crash protection.",
        unsuitable_market="Low-volatility sideways markets where insurance premium may decay.",
    )


def bull_call_spread(
    lower_strike: float,
    higher_strike: float,
    long_call_premium: float,
    short_call_premium: float,
    spot: float | None = None,
    num_points: int = 101,
) -> StrategyResult:
    """Long lower-strike call plus short higher-strike call."""

    _validate_spread_strikes(lower_strike, higher_strike)
    _validate_non_negative("long_call_premium", long_call_premium)
    _validate_non_negative("short_call_premium", short_call_premium)
    net_debit = long_call_premium - short_call_premium
    _validate_positive("net_debit", net_debit)
    width = higher_strike - lower_strike
    if net_debit >= width:
        raise ValueError("net_debit must be less than spread width")

    reference_spot = spot or (lower_strike + higher_strike) / 2
    prices = _price_grid(reference_spot, [lower_strike, higher_strike], num_points)
    payoff = np.maximum(prices - lower_strike, 0) - np.maximum(prices - higher_strike, 0) - net_debit

    return StrategyResult(
        name="Bull Call Spread",
        market_view="Moderately bullish with defined risk and capped upside.",
        legs=[
            StrategyLeg(
                "call",
                "long",
                1,
                strike=lower_strike,
                premium=long_call_premium,
                description="Buy lower-strike call",
            ),
            StrategyLeg(
                "call",
                "short",
                1,
                strike=higher_strike,
                premium=short_call_premium,
                description="Sell higher-strike call",
            ),
        ],
        max_profit=width - net_debit,
        max_loss=net_debit,
        breakeven_points=[lower_strike + net_debit],
        payoff_curve=_payoff_frame(prices, payoff),
        risks=[
            "Maximum profit is capped above the higher strike.",
            "The strategy can lose the full net debit if the underlying finishes below the lower strike.",
            "Time decay can hurt if the expected move does not happen.",
        ],
        suitable_market="Moderately bullish markets with a clear upside target.",
        unsuitable_market="Strongly bullish markets where capped upside is unattractive, or bearish markets.",
    )


def bear_put_spread(
    lower_strike: float,
    higher_strike: float,
    long_put_premium: float,
    short_put_premium: float,
    spot: float | None = None,
    num_points: int = 101,
) -> StrategyResult:
    """Long higher-strike put plus short lower-strike put."""

    _validate_spread_strikes(lower_strike, higher_strike)
    _validate_non_negative("long_put_premium", long_put_premium)
    _validate_non_negative("short_put_premium", short_put_premium)
    net_debit = long_put_premium - short_put_premium
    _validate_positive("net_debit", net_debit)
    width = higher_strike - lower_strike
    if net_debit >= width:
        raise ValueError("net_debit must be less than spread width")

    reference_spot = spot or (lower_strike + higher_strike) / 2
    prices = _price_grid(reference_spot, [lower_strike, higher_strike], num_points)
    payoff = np.maximum(higher_strike - prices, 0) - np.maximum(lower_strike - prices, 0) - net_debit

    return StrategyResult(
        name="Bear Put Spread",
        market_view="Moderately bearish with defined risk and capped downside profit.",
        legs=[
            StrategyLeg(
                "put",
                "long",
                1,
                strike=higher_strike,
                premium=long_put_premium,
                description="Buy higher-strike put",
            ),
            StrategyLeg(
                "put",
                "short",
                1,
                strike=lower_strike,
                premium=short_put_premium,
                description="Sell lower-strike put",
            ),
        ],
        max_profit=width - net_debit,
        max_loss=net_debit,
        breakeven_points=[higher_strike - net_debit],
        payoff_curve=_payoff_frame(prices, payoff),
        risks=[
            "Maximum profit is capped below the lower strike.",
            "The strategy can lose the full net debit if the underlying finishes above the higher strike.",
            "A slow or shallow decline may not overcome premium paid.",
        ],
        suitable_market="Moderately bearish markets with a defined downside target.",
        unsuitable_market="Strongly bearish markets where capped profit is limiting, or bullish markets.",
    )


def iron_condor(
    long_put_strike: float,
    short_put_strike: float,
    short_call_strike: float,
    long_call_strike: float,
    long_put_premium: float,
    short_put_premium: float,
    short_call_premium: float,
    long_call_premium: float,
    spot: float | None = None,
    num_points: int = 101,
) -> StrategyResult:
    """Short put spread plus short call spread."""

    _validate_iron_condor_strikes(
        long_put_strike,
        short_put_strike,
        short_call_strike,
        long_call_strike,
    )
    for name, value in {
        "long_put_premium": long_put_premium,
        "short_put_premium": short_put_premium,
        "short_call_premium": short_call_premium,
        "long_call_premium": long_call_premium,
    }.items():
        _validate_non_negative(name, value)

    net_credit = short_put_premium + short_call_premium - long_put_premium - long_call_premium
    _validate_positive("net_credit", net_credit)
    put_width = short_put_strike - long_put_strike
    call_width = long_call_strike - short_call_strike
    max_loss = max(put_width, call_width) - net_credit
    if max_loss <= 0:
        raise ValueError("net_credit must be smaller than the widest wing")

    reference_spot = spot or (short_put_strike + short_call_strike) / 2
    prices = _price_grid(
        reference_spot,
        [long_put_strike, short_put_strike, short_call_strike, long_call_strike],
        num_points,
    )
    payoff = (
        net_credit
        - np.maximum(short_put_strike - prices, 0)
        + np.maximum(long_put_strike - prices, 0)
        - np.maximum(prices - short_call_strike, 0)
        + np.maximum(prices - long_call_strike, 0)
    )

    return StrategyResult(
        name="Iron Condor",
        market_view="Neutral; expects the underlying to stay inside a range.",
        legs=[
            StrategyLeg(
                "put",
                "long",
                1,
                strike=long_put_strike,
                premium=long_put_premium,
                description="Buy lower-strike protective put",
            ),
            StrategyLeg(
                "put",
                "short",
                1,
                strike=short_put_strike,
                premium=short_put_premium,
                description="Sell higher-strike put",
            ),
            StrategyLeg(
                "call",
                "short",
                1,
                strike=short_call_strike,
                premium=short_call_premium,
                description="Sell lower-strike call",
            ),
            StrategyLeg(
                "call",
                "long",
                1,
                strike=long_call_strike,
                premium=long_call_premium,
                description="Buy higher-strike protective call",
            ),
        ],
        max_profit=net_credit,
        max_loss=max_loss,
        breakeven_points=[short_put_strike - net_credit, short_call_strike + net_credit],
        payoff_curve=_payoff_frame(prices, payoff),
        risks=[
            "Large moves beyond either short strike can quickly turn the trade unprofitable.",
            "Maximum loss occurs if price moves beyond either long wing at expiration.",
            "Short options carry assignment and liquidity risk.",
        ],
        suitable_market="Range-bound markets with elevated option premiums and no expected breakout.",
        unsuitable_market="Trending, event-driven, or high-breakout-risk markets.",
    )


def _payoff_frame(prices: np.ndarray, payoff: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame({"underlying_price": prices, "payoff": payoff}).round(4)


def _price_grid(spot: float, strikes: list[float], num_points: int) -> np.ndarray:
    _validate_positive("spot", spot)
    if num_points < 3:
        raise ValueError("num_points must be at least 3")
    min_anchor = min([spot, *strikes])
    max_anchor = max([spot, *strikes])
    low = max(0.01, min_anchor * 0.5)
    high = max_anchor * 1.5
    return np.linspace(low, high, num_points)


def _validate_spread_strikes(lower_strike: float, higher_strike: float) -> None:
    _validate_positive("lower_strike", lower_strike)
    _validate_positive("higher_strike", higher_strike)
    if lower_strike >= higher_strike:
        raise ValueError("lower_strike must be less than higher_strike")


def _validate_iron_condor_strikes(
    long_put_strike: float,
    short_put_strike: float,
    short_call_strike: float,
    long_call_strike: float,
) -> None:
    for name, value in {
        "long_put_strike": long_put_strike,
        "short_put_strike": short_put_strike,
        "short_call_strike": short_call_strike,
        "long_call_strike": long_call_strike,
    }.items():
        _validate_positive(name, value)
    if not long_put_strike < short_put_strike < short_call_strike < long_call_strike:
        raise ValueError(
            "iron condor strikes must satisfy "
            "long_put_strike < short_put_strike < short_call_strike < long_call_strike"
        )


def _validate_non_negative(name: str, value: float) -> None:
    _validate_number(name, value)
    if value < 0:
        raise ValueError(f"{name} must be non-negative")


def _validate_positive(name: str, value: float) -> None:
    _validate_number(name, value)
    if value <= 0:
        raise ValueError(f"{name} must be positive")


def _validate_number(name: str, value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
