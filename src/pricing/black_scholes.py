"""Black-Scholes pricing, Greeks, and implied volatility utilities."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from scipy.optimize import brentq
from scipy.stats import norm

OptionType = Literal["call", "put"]


@dataclass(frozen=True)
class Greeks:
    """Black-Scholes Greeks using annualized conventions."""

    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float


def black_scholes_price(
    spot: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    volatility: float,
    option_type: OptionType,
    dividend_yield: float = 0.0,
) -> float:
    """Return the Black-Scholes theoretical price for a European call or put."""

    _validate_inputs(
        spot=spot,
        strike=strike,
        time_to_expiry=time_to_expiry,
        risk_free_rate=risk_free_rate,
        volatility=volatility,
        option_type=option_type,
        dividend_yield=dividend_yield,
    )
    d1, d2 = _d1_d2(spot, strike, time_to_expiry, risk_free_rate, volatility, dividend_yield)
    discounted_spot = spot * math.exp(-dividend_yield * time_to_expiry)
    discounted_strike = strike * math.exp(-risk_free_rate * time_to_expiry)

    if option_type == "call":
        return discounted_spot * norm.cdf(d1) - discounted_strike * norm.cdf(d2)
    return discounted_strike * norm.cdf(-d2) - discounted_spot * norm.cdf(-d1)


def black_scholes_greeks(
    spot: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    volatility: float,
    option_type: OptionType,
    dividend_yield: float = 0.0,
) -> Greeks:
    """Return Delta, Gamma, Theta, Vega, and Rho for a European call or put.

    Theta is expressed per year. Vega is per 1.0 volatility point, and Rho is
    per 1.0 interest-rate point. UI layers can scale these by 100 if needed.
    """

    _validate_inputs(
        spot=spot,
        strike=strike,
        time_to_expiry=time_to_expiry,
        risk_free_rate=risk_free_rate,
        volatility=volatility,
        option_type=option_type,
        dividend_yield=dividend_yield,
    )
    d1, d2 = _d1_d2(spot, strike, time_to_expiry, risk_free_rate, volatility, dividend_yield)
    sqrt_t = math.sqrt(time_to_expiry)
    discount_q = math.exp(-dividend_yield * time_to_expiry)
    discount_r = math.exp(-risk_free_rate * time_to_expiry)
    pdf_d1 = norm.pdf(d1)

    gamma = discount_q * pdf_d1 / (spot * volatility * sqrt_t)
    vega = spot * discount_q * pdf_d1 * sqrt_t
    common_theta = -(spot * discount_q * pdf_d1 * volatility) / (2 * sqrt_t)

    if option_type == "call":
        delta = discount_q * norm.cdf(d1)
        theta = (
            common_theta
            - risk_free_rate * strike * discount_r * norm.cdf(d2)
            + dividend_yield * spot * discount_q * norm.cdf(d1)
        )
        rho = strike * time_to_expiry * discount_r * norm.cdf(d2)
    else:
        delta = discount_q * (norm.cdf(d1) - 1)
        theta = (
            common_theta
            + risk_free_rate * strike * discount_r * norm.cdf(-d2)
            - dividend_yield * spot * discount_q * norm.cdf(-d1)
        )
        rho = -strike * time_to_expiry * discount_r * norm.cdf(-d2)

    return Greeks(delta=delta, gamma=gamma, theta=theta, vega=vega, rho=rho)


def implied_volatility(
    market_price: float,
    spot: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    option_type: OptionType,
    dividend_yield: float = 0.0,
    lower_bound: float = 1e-6,
    upper_bound: float = 5.0,
    tolerance: float = 1e-8,
    max_iterations: int = 100,
) -> float:
    """Solve implied volatility from a market option price using Brent's method."""

    _validate_positive_finite("market_price", market_price)
    _validate_inputs(
        spot=spot,
        strike=strike,
        time_to_expiry=time_to_expiry,
        risk_free_rate=risk_free_rate,
        volatility=lower_bound,
        option_type=option_type,
        dividend_yield=dividend_yield,
    )
    _validate_positive_finite("upper_bound", upper_bound)
    _validate_positive_finite("tolerance", tolerance)
    if upper_bound <= lower_bound:
        raise ValueError("upper_bound must be greater than lower_bound")
    if max_iterations <= 0:
        raise ValueError("max_iterations must be positive")

    lower_price_bound, upper_price_bound = _no_arbitrage_price_bounds(
        spot, strike, time_to_expiry, risk_free_rate, option_type, dividend_yield
    )
    if market_price < lower_price_bound or market_price > upper_price_bound:
        raise ValueError(
            "market_price is outside no-arbitrage bounds "
            f"[{lower_price_bound:.6f}, {upper_price_bound:.6f}]"
        )

    def objective(sigma: float) -> float:
        return (
            black_scholes_price(
                spot=spot,
                strike=strike,
                time_to_expiry=time_to_expiry,
                risk_free_rate=risk_free_rate,
                volatility=sigma,
                option_type=option_type,
                dividend_yield=dividend_yield,
            )
            - market_price
        )

    low_value = objective(lower_bound)
    high_value = objective(upper_bound)
    if abs(low_value) <= tolerance:
        return lower_bound
    if abs(high_value) <= tolerance:
        return upper_bound
    if low_value * high_value > 0:
        raise ValueError("Could not bracket implied volatility with the provided bounds")

    return brentq(
        objective,
        lower_bound,
        upper_bound,
        xtol=tolerance,
        rtol=tolerance,
        maxiter=max_iterations,
    )


def _d1_d2(
    spot: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    volatility: float,
    dividend_yield: float,
) -> tuple[float, float]:
    sqrt_t = math.sqrt(time_to_expiry)
    d1 = (
        math.log(spot / strike)
        + (risk_free_rate - dividend_yield + 0.5 * volatility**2) * time_to_expiry
    ) / (volatility * sqrt_t)
    d2 = d1 - volatility * sqrt_t
    return d1, d2


def _no_arbitrage_price_bounds(
    spot: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    option_type: OptionType,
    dividend_yield: float,
) -> tuple[float, float]:
    discounted_spot = spot * math.exp(-dividend_yield * time_to_expiry)
    discounted_strike = strike * math.exp(-risk_free_rate * time_to_expiry)

    if option_type == "call":
        return max(0.0, discounted_spot - discounted_strike), discounted_spot
    return max(0.0, discounted_strike - discounted_spot), discounted_strike


def _validate_inputs(
    spot: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    volatility: float,
    option_type: OptionType,
    dividend_yield: float,
) -> None:
    _validate_positive_finite("spot", spot)
    _validate_positive_finite("strike", strike)
    _validate_positive_finite("time_to_expiry", time_to_expiry)
    _validate_positive_finite("volatility", volatility)
    _validate_finite("risk_free_rate", risk_free_rate)
    _validate_finite("dividend_yield", dividend_yield)
    if option_type not in {"call", "put"}:
        raise ValueError("option_type must be 'call' or 'put'")


def _validate_positive_finite(name: str, value: float) -> None:
    _validate_finite(name, value)
    if value <= 0:
        raise ValueError(f"{name} must be positive")


def _validate_finite(name: str, value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
