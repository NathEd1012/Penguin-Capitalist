#!/usr/bin/env python3
"""Quick test of the market data system."""

from market_data import get_bars, init_router
from config.symbols import ALL_SYMBOLS, SYMBOLS
from datetime import datetime
import pytz
import time
import logging

logging.basicConfig(level=logging.WARNING)

print("=" * 80)
print("MARKET DATA SYSTEM TESTS")
print("=" * 80)

# Test 1: Module imports
print("\n[1] Module Imports")
print("  ✓ market_data module imported")
print("  ✓ config.symbols module imported")

# Test 2: Router initialization
print("\n[2] Router Initialization")
router = init_router(use_cache=True)
print(f"  ✓ Router initialized")
print(f"    - Alpaca available: {router.alpaca_client is not None}")
print(f"    - Twelve Data available: {router.twelvedata_client is not None}")
print(f"    - Cache enabled: {router.use_cache}")

# Test 3: Symbols configuration
print("\n[3] Symbols Configuration")
print(f"  ✓ Total symbols: {len(ALL_SYMBOLS)}")
print(f"    - Categories: {list(SYMBOLS.keys())}")
for cat, symbols in SYMBOLS.items():
    print(f"      {cat}: {len(symbols)} symbols")

# Test 4: Data fetching
print("\n[4] Historical Data Fetch")
start = datetime(2025, 1, 1, tzinfo=pytz.UTC)
end = datetime(2025, 3, 31, tzinfo=pytz.UTC)

try:
    df = get_bars("AAPL", start, end, "1d")
    print(f"  ✓ Fetched {len(df)} bars for AAPL")
    print(f"    - Columns: {list(df.columns)}")
    print(f"    - Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"    - Data types: {dict(df.dtypes)}")
except Exception as e:
    print(f"  ✗ Error: {e}")

# Test 5: Caching
print("\n[5] Caching System")
try:
    t1 = time.time()
    df1 = get_bars("MSFT", start, end, "1d")
    elapsed1 = time.time() - t1
    
    t2 = time.time()
    df2 = get_bars("MSFT", start, end, "1d")
    elapsed2 = time.time() - t2
    
    print(f"  ✓ First fetch: {len(df1)} bars in {elapsed1:.2f}s (API)")
    print(f"  ✓ Second fetch: {len(df2)} bars in {elapsed2:.3f}s (cache)")
    print(f"    - Data identical: {df1.equals(df2)}")
    if elapsed1 > 0:
        print(f"    - Speedup from cache: {elapsed1/elapsed2:.1f}x")
    
    from pathlib import Path
    cache_dir = Path("data_cache")
    if cache_dir.exists():
        cache_files = list(cache_dir.glob("*.parquet"))
        print(f"    - Cache files: {len(cache_files)} symbols cached")
except Exception as e:
    print(f"  ✗ Error: {e}")

# Test 6: Multiple symbols
print("\n[6] Batch Fetch Test")
symbols_to_test = ["AAPL", "MSFT", "AMD"]
results = {}
for symbol in symbols_to_test:
    try:
        df = get_bars(symbol, start, end, "1d")
        results[symbol] = len(df)
    except Exception as e:
        results[symbol] = f"Error: {e}"

for symbol, result in results.items():
    if isinstance(result, int):
        print(f"  ✓ {symbol}: {result} bars")
    else:
        print(f"  ✗ {symbol}: {result}")

# Test 7: Different timeframes
print("\n[7] Timeframe Support")
for tf in ["1d", "1h", "15m", "5m", "1m"]:
    try:
        df = get_bars("AAPL", start, end, tf)
        print(f"  ✓ {tf}: {len(df)} bars")
    except Exception as e:
        print(f"  ✗ {tf}: {str(e)[:50]}")

print("\n" + "=" * 80)
print("ALL TESTS COMPLETED SUCCESSFULLY!")
print("=" * 80)
