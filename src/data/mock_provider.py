"""Deterministic mock market data provider used as a safe fallback."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

from src.data.models import DataProviderError, OptionChain
from src.data.volatility import historical_volatility


@dataclass(frozen=True)
class MockTickerProfile:
    symbol: str
    base_price: float
    annual_volatility: float
    drift: float
    average_volume: int


class MockMarketDataProvider:
    """Generate realistic-enough deterministic data for offline demos."""

    name = "mock"

    _profiles = {
        "SPY": MockTickerProfile("SPY", 545.0, 0.18, 0.07, 74_000_000),
        "QQQ": MockTickerProfile("QQQ", 475.0, 0.24, 0.09, 48_000_000),
        "AAPL": MockTickerProfile("AAPL", 210.0, 0.28, 0.08, 58_000_000),
    }

    def get_current_price(self, symbol: str) -> float:
        history = self.get_history(symbol=symbol, period="6mo")
        return float(history["Close"].iloc[-1])

    def get_history(
        self,
        symbol: str,
        start: str | date | None = None,
        end: str | date | None = None,
        period: str = "1y",
    ) -> pd.DataFrame:
        profile = self._profile_for(symbol)
        dates = _business_dates(start=start, end=end, period=period)
        if len(dates) < 2:
            raise DataProviderError("mock history requires at least two business dates")

        rng = np.random.default_rng(_seed_for(profile.symbol))
        daily_vol = profile.annual_volatility / np.sqrt(252)
        daily_drift = profile.drift / 252
        shocks = rng.normal(loc=daily_drift, scale=daily_vol, size=len(dates))
        close = profile.base_price * np.exp(np.cumsum(shocks))
        open_ = close * (1 + rng.normal(0, daily_vol / 3, size=len(dates)))
        high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, daily_vol / 2, size=len(dates))))
        low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, daily_vol / 2, size=len(dates))))
        volume = rng.normal(profile.average_volume, profile.average_volume * 0.12, size=len(dates))

        history = pd.DataFrame(
            {
                "Open": open_,
                "High": high,
                "Low": np.maximum(low, 0.01),
                "Close": close,
                "Adj Close": close,
                "Volume": np.maximum(volume.astype(int), 1),
            },
            index=pd.DatetimeIndex(dates, name="Date"),
        )
        return history.round(
            {"Open": 2, "High": 2, "Low": 2, "Close": 2, "Adj Close": 2}
        )

    def get_expirations(self, symbol: str) -> list[str]:
        self._profile_for(symbol)
        today = date.today()
        expirations: list[str] = []
        cursor = today + timedelta(days=20)
        while len(expirations) < 6:
            if cursor.weekday() == 4 and 15 <= cursor.day <= 21:
                expirations.append(cursor.isoformat())
            cursor += timedelta(days=1)
        return expirations

    def get_option_chain(self, symbol: str, expiration: str | None = None) -> OptionChain:
        profile = self._profile_for(symbol)
        selected_expiration = expiration or self.get_expirations(symbol)[0]
        spot = self.get_current_price(symbol)
        history = self.get_history(symbol=symbol, period="1y")
        hv = historical_volatility(history)
        expiry_date = pd.Timestamp(selected_expiration).date()
        days_to_expiry = max((expiry_date - date.today()).days, 1)
        time_to_expiry = days_to_expiry / 365

        strikes = _strike_grid(spot)
        calls = self._build_options_frame(
            profile=profile,
            spot=spot,
            strikes=strikes,
            expiration=selected_expiration,
            option_type="call",
            implied_volatility=max(hv, profile.annual_volatility),
            time_to_expiry=time_to_expiry,
        )
        puts = self._build_options_frame(
            profile=profile,
            spot=spot,
            strikes=strikes,
            expiration=selected_expiration,
            option_type="put",
            implied_volatility=max(hv, profile.annual_volatility),
            time_to_expiry=time_to_expiry,
        )
        return OptionChain(
            symbol=profile.symbol,
            expiration=selected_expiration,
            calls=calls,
            puts=puts,
            provider=self.name,
        )

    def _build_options_frame(
        self,
        profile: MockTickerProfile,
        spot: float,
        strikes: np.ndarray,
        expiration: str,
        option_type: str,
        implied_volatility: float,
        time_to_expiry: float,
    ) -> pd.DataFrame:
        intrinsic = np.maximum(spot - strikes, 0) if option_type == "call" else np.maximum(strikes - spot, 0)
        moneyness = np.abs(np.log(strikes / spot))
        time_value = spot * implied_volatility * np.sqrt(time_to_expiry) * np.exp(-6 * moneyness) * 0.12
        last_price = np.maximum(intrinsic + time_value, 0.01)
        bid = np.maximum(last_price - np.maximum(0.03, last_price * 0.015), 0.01)
        ask = last_price + np.maximum(0.03, last_price * 0.015)
        rng = np.random.default_rng(_seed_for(f"{profile.symbol}-{expiration}-{option_type}"))

        return pd.DataFrame(
            {
                "contractSymbol": [
                    f"{profile.symbol}{expiration.replace('-', '')}{option_type[0].upper()}{int(strike * 1000):08d}"
                    for strike in strikes
                ],
                "lastTradeDate": pd.Timestamp(date.today()),
                "strike": strikes,
                "lastPrice": last_price,
                "bid": bid,
                "ask": ask,
                "change": rng.normal(0, 0.15, size=len(strikes)),
                "percentChange": rng.normal(0, 1.5, size=len(strikes)),
                "volume": rng.integers(10, 5_000, size=len(strikes)),
                "openInterest": rng.integers(100, 25_000, size=len(strikes)),
                "impliedVolatility": implied_volatility * (1 + 0.35 * moneyness),
                "inTheMoney": strikes < spot if option_type == "call" else strikes > spot,
                "contractSize": "REGULAR",
                "currency": "USD",
                "optionType": option_type,
                "expiration": expiration,
            }
        ).round(
            {
                "strike": 2,
                "lastPrice": 2,
                "bid": 2,
                "ask": 2,
                "change": 2,
                "percentChange": 2,
                "impliedVolatility": 4,
            }
        )

    def _profile_for(self, symbol: str) -> MockTickerProfile:
        normalized = symbol.upper().strip()
        if not normalized:
            raise DataProviderError("symbol must not be empty")
        if normalized in self._profiles:
            return self._profiles[normalized]

        seed = _seed_for(normalized)
        base_price = 50 + (seed % 450)
        annual_volatility = 0.2 + (seed % 20) / 100
        return MockTickerProfile(
            symbol=normalized,
            base_price=float(base_price),
            annual_volatility=float(annual_volatility),
            drift=0.06,
            average_volume=5_000_000 + seed % 10_000_000,
        )


def _business_dates(
    start: str | date | None,
    end: str | date | None,
    period: str,
) -> pd.DatetimeIndex:
    end_date = pd.Timestamp(end).normalize() if end else pd.Timestamp.today().normalize()
    if start:
        start_date = pd.Timestamp(start).normalize()
    else:
        start_date = end_date - pd.Timedelta(days=_period_to_days(period))
    return pd.bdate_range(start=start_date, end=end_date)


def _period_to_days(period: str) -> int:
    normalized = period.lower().strip()
    if normalized.endswith("mo"):
        return int(normalized[:-2]) * 31
    if normalized.endswith("y"):
        return int(normalized[:-1]) * 365
    if normalized.endswith("d"):
        return int(normalized[:-1])
    return 365


def _strike_grid(spot: float) -> np.ndarray:
    step = 1 if spot < 100 else 5
    low = np.floor(spot * 0.75 / step) * step
    high = np.ceil(spot * 1.25 / step) * step
    return np.arange(low, high + step, step, dtype=float)


def _seed_for(symbol: str) -> int:
    return sum((index + 1) * ord(char) for index, char in enumerate(symbol.upper()))
