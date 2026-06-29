import math

import pytest

from src.pricing import Greeks, black_scholes_greeks, black_scholes_price, implied_volatility


def test_black_scholes_call_price() -> None:
    price = black_scholes_price(
        spot=100,
        strike=100,
        time_to_expiry=1,
        risk_free_rate=0.05,
        volatility=0.2,
        option_type="call",
    )

    assert price == pytest.approx(10.450583572185565)


def test_black_scholes_put_price() -> None:
    price = black_scholes_price(
        spot=100,
        strike=100,
        time_to_expiry=1,
        risk_free_rate=0.05,
        volatility=0.2,
        option_type="put",
    )

    assert price == pytest.approx(5.573526022256971)


def test_call_greeks() -> None:
    greeks = black_scholes_greeks(
        spot=100,
        strike=100,
        time_to_expiry=1,
        risk_free_rate=0.05,
        volatility=0.2,
        option_type="call",
    )

    assert isinstance(greeks, Greeks)
    assert greeks.delta == pytest.approx(0.6368306511756191)
    assert greeks.gamma == pytest.approx(0.018762017345846895)
    assert greeks.theta == pytest.approx(-6.414027546438197)
    assert greeks.vega == pytest.approx(37.52403469169379)
    assert greeks.rho == pytest.approx(53.232481545376345)


def test_put_greeks() -> None:
    greeks = black_scholes_greeks(
        spot=100,
        strike=100,
        time_to_expiry=1,
        risk_free_rate=0.05,
        volatility=0.2,
        option_type="put",
    )

    assert greeks.delta == pytest.approx(-0.3631693488243809)
    assert greeks.gamma == pytest.approx(0.018762017345846895)
    assert greeks.theta == pytest.approx(-1.657880423934626)
    assert greeks.vega == pytest.approx(37.52403469169379)
    assert greeks.rho == pytest.approx(-41.89046090469506)


@pytest.mark.parametrize("option_type", ["call", "put"])
def test_implied_volatility_round_trip(option_type: str) -> None:
    market_price = black_scholes_price(
        spot=100,
        strike=100,
        time_to_expiry=1,
        risk_free_rate=0.05,
        volatility=0.2,
        option_type=option_type,
    )

    iv = implied_volatility(
        market_price=market_price,
        spot=100,
        strike=100,
        time_to_expiry=1,
        risk_free_rate=0.05,
        option_type=option_type,
    )

    assert iv == pytest.approx(0.2, abs=1e-8)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"spot": 0}, "spot must be positive"),
        ({"strike": -1}, "strike must be positive"),
        ({"time_to_expiry": 0}, "time_to_expiry must be positive"),
        ({"volatility": 0}, "volatility must be positive"),
        ({"risk_free_rate": math.inf}, "risk_free_rate must be a finite number"),
        ({"option_type": "invalid"}, "option_type must be 'call' or 'put'"),
    ],
)
def test_input_validation(kwargs: dict[str, object], message: str) -> None:
    params = {
        "spot": 100,
        "strike": 100,
        "time_to_expiry": 1,
        "risk_free_rate": 0.05,
        "volatility": 0.2,
        "option_type": "call",
    }
    params.update(kwargs)

    with pytest.raises(ValueError, match=message):
        black_scholes_price(**params)


def test_implied_volatility_rejects_invalid_market_price() -> None:
    with pytest.raises(ValueError, match="market_price is outside no-arbitrage bounds"):
        implied_volatility(
            market_price=200,
            spot=100,
            strike=100,
            time_to_expiry=1,
            risk_free_rate=0.05,
            option_type="call",
        )
