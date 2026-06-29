import pandas as pd

from src.data import MarketDataClient, MockMarketDataProvider, historical_volatility
from src.data.models import DataProviderError


class FailingProvider:
    name = "failing"

    def get_current_price(self, symbol: str) -> float:
        raise DataProviderError("network unavailable")

    def get_history(self, symbol: str, **kwargs) -> pd.DataFrame:
        raise DataProviderError("network unavailable")

    def get_expirations(self, symbol: str) -> list[str]:
        raise DataProviderError("network unavailable")

    def get_option_chain(self, symbol: str, expiration: str | None = None):
        raise DataProviderError("network unavailable")


def test_mock_provider_supports_core_symbols() -> None:
    provider = MockMarketDataProvider()

    for symbol in ["SPY", "QQQ", "AAPL"]:
        price = provider.get_current_price(symbol)
        history = provider.get_history(symbol, period="6mo")
        expirations = provider.get_expirations(symbol)
        chain = provider.get_option_chain(symbol, expirations[0])

        assert price > 0
        assert not history.empty
        assert {"Open", "High", "Low", "Close", "Adj Close", "Volume"}.issubset(history.columns)
        assert len(expirations) >= 1
        assert not chain.calls.empty
        assert not chain.puts.empty
        assert {"strike", "lastPrice", "bid", "ask", "impliedVolatility"}.issubset(chain.calls.columns)


def test_client_falls_back_to_mock_when_primary_fails() -> None:
    client = MarketDataClient(primary_provider=FailingProvider(), fallback_provider=MockMarketDataProvider())

    snapshot = client.get_snapshot("SPY")
    history = client.get_history("SPY", period="3mo")
    expirations = client.get_expirations("SPY")
    chain = client.get_option_chain("SPY", expirations[0])

    assert snapshot.price > 0
    assert snapshot.provider == "mock"
    assert client.last_provider == "mock"
    assert not history.empty
    assert expirations
    assert chain.provider == "mock"


def test_historical_volatility_from_mock_history() -> None:
    history = MockMarketDataProvider().get_history("AAPL", period="1y")

    hv = historical_volatility(history)

    assert 0 < hv < 1
