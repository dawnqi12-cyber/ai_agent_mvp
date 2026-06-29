"""yfinance-backed market data provider."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import math

import pandas as pd

from src.data.models import DataProviderError, OptionChain


class YFinanceMarketDataProvider:
    """Fetch market data from yfinance and normalize it for the project."""

    name = "yfinance"
    _cache_configured = False

    def get_current_price(self, symbol: str) -> float:
        ticker = self._ticker(symbol)

        fast_info = getattr(ticker, "fast_info", None)
        price = self._extract_fast_info_price(fast_info)
        if price is not None:
            return price

        info = self._safe_get_info(ticker)
        for key in ("regularMarketPrice", "currentPrice", "previousClose"):
            price = info.get(key)
            if self._is_positive_number(price):
                return float(price)

        history = self.get_history(symbol=symbol, period="5d")
        return float(history["Close"].dropna().iloc[-1])

    def get_history(
        self,
        symbol: str,
        start: str | date | None = None,
        end: str | date | None = None,
        period: str = "1y",
    ) -> pd.DataFrame:
        ticker = self._ticker(symbol)
        kwargs: dict[str, Any] = {"auto_adjust": False, "actions": False}
        if start or end:
            kwargs["start"] = start
            kwargs["end"] = end
        else:
            kwargs["period"] = period

        history = ticker.history(**kwargs)
        if history is None or history.empty:
            raise DataProviderError(f"yfinance returned no historical data for {symbol}")

        normalized = history.copy()
        if isinstance(normalized.index, pd.DatetimeIndex) and normalized.index.tz is not None:
            normalized.index = normalized.index.tz_localize(None)
        normalized.index.name = "Date"
        required_columns = {"Open", "High", "Low", "Close", "Volume"}
        missing_columns = required_columns.difference(normalized.columns)
        if missing_columns:
            raise DataProviderError(
                f"yfinance history for {symbol} is missing columns: {sorted(missing_columns)}"
            )
        if "Adj Close" not in normalized.columns:
            normalized["Adj Close"] = normalized["Close"]
        return normalized

    def get_expirations(self, symbol: str) -> list[str]:
        ticker = self._ticker(symbol)
        expirations = list(getattr(ticker, "options", []) or [])
        if not expirations:
            raise DataProviderError(f"yfinance returned no option expirations for {symbol}")
        return expirations

    def get_option_chain(self, symbol: str, expiration: str | None = None) -> OptionChain:
        ticker = self._ticker(symbol)
        selected_expiration = expiration or self.get_expirations(symbol)[0]
        chain = ticker.option_chain(selected_expiration)
        calls = self._normalize_option_frame(chain.calls, selected_expiration, "call", symbol)
        puts = self._normalize_option_frame(chain.puts, selected_expiration, "put", symbol)
        if calls.empty or puts.empty:
            raise DataProviderError(
                f"yfinance returned an incomplete option chain for {symbol} {selected_expiration}"
            )
        return OptionChain(
            symbol=symbol.upper().strip(),
            expiration=selected_expiration,
            calls=calls,
            puts=puts,
            provider=self.name,
        )

    def _ticker(self, symbol: str):
        normalized = symbol.upper().strip()
        if not normalized:
            raise DataProviderError("symbol must not be empty")
        try:
            import yfinance as yf
        except Exception as exc:  # pragma: no cover - depends on local environment
            raise DataProviderError("yfinance is not available") from exc
        self._configure_cache(yf)
        return yf.Ticker(normalized)

    def _configure_cache(self, yf) -> None:
        if self.__class__._cache_configured:
            return
        cache_dir = Path.cwd() / ".cache" / "yfinance"
        cache_dir.mkdir(parents=True, exist_ok=True)
        try:
            yf.cache.set_cache_location(str(cache_dir))
        except Exception as exc:
            raise DataProviderError(f"failed to configure yfinance cache at {cache_dir}") from exc
        self.__class__._cache_configured = True

    def _normalize_option_frame(
        self,
        frame: pd.DataFrame,
        expiration: str,
        option_type: str,
        symbol: str,
    ) -> pd.DataFrame:
        if frame is None or frame.empty:
            raise DataProviderError(f"yfinance returned no {option_type} options for {symbol}")
        normalized = frame.copy().reset_index(drop=True)
        normalized["optionType"] = option_type
        normalized["expiration"] = expiration
        return normalized

    def _safe_get_info(self, ticker) -> dict[str, Any]:
        try:
            info = ticker.info
        except Exception:
            return {}
        return info if isinstance(info, dict) else {}

    def _extract_fast_info_price(self, fast_info: Any) -> float | None:
        if not fast_info:
            return None
        for key in ("last_price", "regular_market_price", "previous_close"):
            try:
                value = fast_info.get(key) if hasattr(fast_info, "get") else getattr(fast_info, key)
            except Exception:
                continue
            if self._is_positive_number(value):
                return float(value)
        return None

    def _is_positive_number(self, value: Any) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0
