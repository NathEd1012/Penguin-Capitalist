# Market Data System

A flexible, multi-provider market data system for fetching historical OHLCV candles from Alpaca and Twelve Data APIs.

## Architecture

### Components

1. **BaseProvider** (`base_provider.py`)
   - Abstract base class defining the provider interface
   - Standardizes all data to: `timestamp, open, high, low, close, volume`
   - All timestamps normalized to UTC
   - Built-in DataFrame validation and normalization

2. **AlpacaProvider** (`alpaca_provider.py`)
   - Primary provider for US equities
   - Supports: 1m, 5m, 15m, 1h, 1d candles
   - Up to ~2 years of history
   - Credentials from `.env`: `APCA_API_KEY_ID`, `APCA_API_SECRET_KEY`

3. **TwelveDataProvider** (`twelvedata_provider.py`)
   - Fallback provider and global asset support
   - Supports: 1m, 5m, 15m, 1h, 1d candles
   - Works with: stocks (US/international), ETFs, forex, crypto
   - Credentials from `.env`: `TWELVE_DATA_API_KEY`
   - Built-in retry logic with exponential backoff

4. **DataCache** (`cache.py`)
   - Disk-based caching using parquet files
   - Avoids hitting API rate limits (Twelve Data: 800 req/day)
   - Cache files: `data_cache/{symbol}_{timeframe}.parquet`
   - Intelligent range checking: only re-fetches if new data exists outside cache

5. **ProviderRouter** (`provider_router.py`)
   - Intelligent provider selection based on ticker type
   - Fallback chain: US ticker → Alpaca → Twelve Data → Alpaca fail → Twelve Data
   - Global singleton for easy access
   - Manages caching transparently

## Setup

### 1. Add Twelve Data API Key to `.env`

```bash
# .env
ALPACA_API_KEY="PKNTJYA2JYTXO52QYH3E7BY6JT"          # Already set
ALPACA_SECRET_KEY="..."                              # Already set

TWELVE_DATA_API_KEY="your_twelve_data_key_here"      # Add this
```

Get a free key at: https://twelvedata.com/

### 2. Ensure Dependencies

```bash
pip install python-dotenv requests pandas pyarrow
```

`requests` and `pyarrow` may need to be added to `requirements.txt`.

## Usage

### Basic Usage

```python
from market_data import get_bars
from datetime import datetime
import pytz

# Fetch 1-day bars for AAPL
bars = get_bars(
    symbol="AAPL",
    start=datetime(2025, 1, 1, tzinfo=pytz.UTC),
    end=datetime(2025, 12, 31, tzinfo=pytz.UTC),
    timeframe="1d"
)

print(bars.head())
# Output:
#            timestamp  open  high   low  close  volume
# 0 2025-01-02 14:31   ... (UTC)
```

### Advanced: Initialize Custom Router

```python
from market_data import init_router

# Initialize with custom cache directory
router = init_router(
    use_cache=True,
    cache_dir="my_cache_dir"
)

# Use the router directly
bars = router.get_bars("MSFT", start, end, "1h")
```

### Batch Fetching for Backtester

```python
from market_data import get_bars
from config.symbols import US_EQUITIES

symbols = US_EQUITIES[:5]
data = {}

for symbol in symbols:
    try:
        df = get_bars(symbol, start, end, "1m")
        data[symbol] = df  # Or convert to dict format as needed
        print(f"✓ {symbol}")
    except Exception as e:
        print(f"✗ {symbol}: {e}")
```

## Symbol Universe

Available in `config/symbols.py`:

```python
from config.symbols import SYMBOLS, ALL_SYMBOLS, US_EQUITIES, INTERNATIONAL_EQUITIES, ETFS

# SYMBOLS: Dict organized by category
# ALL_SYMBOLS: Flattened list of all symbols
# US_EQUITIES: Tech, Defense, Alt assets
# INTERNATIONAL_EQUITIES: NVO, ASML, TSM, BABA
# ETFS: Commodities, miners, macro

print(SYMBOLS.keys())
# dict_keys(['tech', 'defense', 'alt_assets', 'international', 'miners', 'commodities', 'macro_etfs'])

print(len(ALL_SYMBOLS))  # 49 unique symbols
```

## Provider Selection Logic

```
if symbol in US_TICKERS:
    try:
        Use Alpaca
    except:
        Fallback to Twelve Data
else:
    Use Twelve Data
```

### US Ticker Detection

Simple heuristic: 1-4 uppercase letters (e.g., "AAPL", "AMD")
- `AAPL` → US ticker
- `ASML.AMS` → International (fallback to Twelve Data)
- `TSM` → Treated as US (will fail on Alpaca, fallback to Twelve Data)

## Caching Behavior

1. **First call**: Fetches from API, caches result
2. **Subsequent calls within cached range**: Loads from disk cache
3. **Calls outside cached range**: Fetches new data, merges with cache
4. **Corrupted cache**: Silently ignored, re-fetches from API

Example:
```python
# First call: fetches from API
df1 = get_bars("AAPL", "2025-01-01", "2025-01-31", "1d")

# Second call: loads from cache (instant)
df2 = get_bars("AAPL", "2025-01-01", "2025-01-31", "1d")

# Third call: merges new data with cache
df3 = get_bars("AAPL", "2025-01-01", "2025-02-15", "1d")
```

## Integration with Existing Backtester

The new system is a drop-in improvement to `backtest/data_loader.py`.

### Option 1: Gradual Migration

Keep existing `DataLoader`, add market_data system alongside:

```python
# backtest_runner.py
from market_data import get_bars
from config.symbols import SYMBOLS

# Use new system for specific symbols, old system as fallback
try:
    df = get_bars(symbol, start, end, "1m")
    data[symbol] = df  # Convert format as needed
except:
    # Fall back to old DataLoader
    data = old_loader.load_bars([symbol], start, end, "1m")
```

### Option 2: Full Replacement

Replace `DataLoader` with new `ProviderRouter`:

```python
# backtest_runner.py
from market_data import init_router, get_bars
from config.symbols import ALL_SYMBOLS

router = init_router()

# Fetch all data
for symbol in ALL_SYMBOLS:
    df = router.get_bars(symbol, start, end, "1m")
    # Process as needed
```

## Error Handling

```python
from market_data import get_bars

try:
    df = get_bars("UNKNOWN_SYMBOL", start, end, "1d")
except RuntimeError as e:
    print(f"Failed to fetch: {e}")
    # Fallback to cache or skip symbol
```

## Rate Limits

- **Alpaca**: No official limit (free tier)
- **Twelve Data**: 800 requests/day (free tier), 15 req/minute

**Mitigation**: Use caching! Cache hits have zero API cost.

## Performance Tips

1. **Cache everything**: `use_cache=True` (default)
2. **Batch requests**: Fetch multiple symbols in parallel (future enhancement)
3. **Use appropriate timeframes**: 
   - `1m` candles for strategy development
   - `1h` or `1d` for multi-year backtests (faster, less data)
4. **Pre-populate cache**: Run demo once on a fast machine, commit cache files

## Troubleshooting

### "subscription does not permit querying recent SIP data"
- Alpaca doesn't have data for this symbol
- Solution: Symbol automatically falls back to Twelve Data
- Or: Add API key to `.env`

### "Missing Twelve Data API key"
- Add `TWELVE_DATA_API_KEY` to `.env`
- Get free key at: https://twelvedata.com/

### "Failed to fetch ... after 3 retries"
- API might be down or rate limited
- Check `.env` credentials
- Wait a few minutes and retry
- Check cache with: `DataCache().load_cache("AAPL", "1d")`

### Cache file corrupted
- Delete file: `rm data_cache/SYMBOL_timeframe.parquet`
- System will re-fetch on next call

## Testing

Run the examples:

```bash
python market_data/examples.py
```

This demonstrates:
- Single symbol fetch
- International equity fetch
- Batch fetching
- Different timeframes
- Backtester integration

## Future Enhancements

- [ ] Parallel batch fetching
- [ ] Compressed cache (currently uncompressed parquet)
- [ ] Cache size limits
- [ ] Data quality validation
- [ ] Historical cache versioning
- [ ] Support for more providers (IB, CCXT, etc.)

## Files

```
market_data/
├── __init__.py                 # Module exports
├── base_provider.py            # Abstract provider class
├── alpaca_provider.py          # Alpaca implementation
├── twelvedata_provider.py      # Twelve Data implementation
├── cache.py                    # Disk caching
├── provider_router.py          # Router and fallback logic
└── examples.py                 # Usage examples

config/
├── __init__.py                 # Config module exports
└── symbols.py                  # Expanded symbol universe

data_cache/                      # Created on first use
└── SYMBOL_timeframe.parquet    # Cached OHLCV data
```
