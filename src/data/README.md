# Data

Market data providers for live and offline demos.

Provider order:

1. `yfinance`
2. mock data fallback

The public entry point is `MarketDataClient`, which exposes current price,
historical price, option expiration, and option chain methods. Mock data is
deterministic and supports at least `SPY`, `QQQ`, and `AAPL`.
