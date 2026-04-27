# Market Data (Alpaca Only)

This project currently uses Alpaca only for historical OHLCV data.

## Environment

Set these keys in `.env` (or your shell):

```env
APCA_API_KEY_ID="your_key"
APCA_API_SECRET_KEY="your_secret"
```

Legacy alias keys are also supported by `backtest/data_loader.py`:

```env
ALPACA_API_KEY="your_key"
ALPACA_SECRET_KEY="your_secret"
```

Note: `TWELVE_DATA_API_KEY` can remain in `.env`, but it is not used by the current code.

## Main Components

- `backtest/data_loader.py`: Direct Alpaca historical data loading for backtests
- `market_data/alpaca_provider.py`: Alpaca provider implementation
- `market_data/provider_router.py`: Router with optional disk cache, using Alpaca only
- `market_data/cache.py`: Local parquet cache helpers

## Quick Usage

```python
from datetime import datetime
import pytz
from market_data import init_router, get_bars

init_router(use_cache=True, cache_dir="data_cache")

start = datetime(2026, 1, 1, tzinfo=pytz.UTC)
end = datetime(2026, 1, 31, tzinfo=pytz.UTC)

df = get_bars("AAPL", start, end, "1h")
print(df.head())
```

## Timeframes

Supported timeframes:

- `1m`
- `5m`
- `15m`
- `1h`
- `1d`

## Notes

- Cache is optional but recommended for repeated runs.
- If Alpaca credentials are missing or invalid, data loading will fail fast with a clear error.
