"""
Example usage of the new market data system.
This demonstrates how to use the flexible provider system with fallback logic.
"""

from datetime import datetime, timedelta
import pytz
from market_data import get_bars, init_router
from config.symbols import ALL_SYMBOLS, US_EQUITIES, INTERNATIONAL_EQUITIES

# Initialize the router with caching enabled
router = init_router(use_cache=True, cache_dir="data_cache")

# Example 1: Fetch data for a single US equity
print("=" * 80)
print("Example 1: Single US Equity (AAPL)")
print("=" * 80)

start = datetime(2025, 1, 1, tzinfo=pytz.UTC)
end = datetime(2025, 12, 31, tzinfo=pytz.UTC)

try:
    df = get_bars("AAPL", start, end, "1d")
    print(f"Fetched {len(df)} bars for AAPL")
    print(df.head())
except Exception as e:
    print(f"Error: {e}")

# Example 2: Fetch data for an international equity
print("\n" + "=" * 80)
print("Example 2: International Equity (TSM)")
print("=" * 80)

try:
    df = get_bars("TSM", start, end, "1d")
    print(f"Fetched {len(df)} bars for TSM")
    print(df.head())
except Exception as e:
    print(f"Error: {e}")

# Example 3: Batch fetch for multiple symbols
print("\n" + "=" * 80)
print("Example 3: Batch Fetch (US Equities)")
print("=" * 80)

results = {}
for symbol in US_EQUITIES[:3]:  # Fetch first 3 for testing
    try:
        df = get_bars(symbol, start, end, "1d")
        results[symbol] = {
            "bars": len(df),
            "start": df["timestamp"].min(),
            "end": df["timestamp"].max(),
        }
        print(f"{symbol}: {len(df)} bars from {results[symbol]['start']} to {results[symbol]['end']}")
    except Exception as e:
        print(f"{symbol}: Error - {e}")

# Example 4: Use different timeframes
print("\n" + "=" * 80)
print("Example 4: Different Timeframes (AAPL, 1-hour candles)")
print("=" * 80)

start_recent = datetime.now(pytz.UTC) - timedelta(days=7)
end_recent = datetime.now(pytz.UTC)

try:
    df_1h = get_bars("AAPL", start_recent, end_recent, "1h")
    print(f"Fetched {len(df_1h)} hourly bars for AAPL (last 7 days)")
    print(f"DataFrame shape: {df_1h.shape}")
    print(f"Columns: {list(df_1h.columns)}")
except Exception as e:
    print(f"Error: {e}")

# Example 5: Integration with backtester
print("\n" + "=" * 80)
print("Example 5: Backtester Integration")
print("=" * 80)

def fetch_backtest_data(symbols, start, end, timeframe="1m"):
    """Helper function for backtester to fetch multi-symbol data."""
    data = {}
    all_timestamps = set()
    
    for symbol in symbols:
        try:
            df = get_bars(symbol, start, end, timeframe)
            if df.empty:
                print(f"Warning: No data for {symbol}")
                continue
            
            # Convert to dict format compatible with existing backtester
            data[symbol] = {}
            for _, row in df.iterrows():
                data[symbol][row["timestamp"]] = {
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": int(row["volume"]),
                }
                all_timestamps.add(row["timestamp"])
            
            print(f"✓ {symbol}: {len(data[symbol])} bars")
        except Exception as e:
            print(f"✗ {symbol}: {e}")
    
    return data, sorted(all_timestamps)

# Test backtester integration
symbols_to_test = ["AAPL", "MSFT"]
backtest_start = datetime(2025, 1, 1, tzinfo=pytz.UTC)
backtest_end = datetime(2025, 3, 1, tzinfo=pytz.UTC)

print(f"\nFetching data for {symbols_to_test}...")
data, timestamps = fetch_backtest_data(symbols_to_test, backtest_start, backtest_end, "1d")

print(f"\nTotal unique timestamps: {len(timestamps)}")
print(f"Data is ready for backtester!")

print("\n" + "=" * 80)
print("Demo Complete!")
print("=" * 80)
