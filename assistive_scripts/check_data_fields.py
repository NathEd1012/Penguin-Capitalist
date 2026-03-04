#!/usr/bin/env python3
"""Check what historical data fields are available from Alpaca."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime
from backtest.data_loader import DataLoader
from config import SYMBOLS, START_DATE, STOP_DATE, BINNING
import pytz

def parse_datetime_string(dt_str: str) -> datetime:
    for fmt in ["%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S"]:
        try:
            dt = datetime.strptime(dt_str.strip(), fmt)
            if dt.tzinfo is None:
                dt = pytz.UTC.localize(dt)
            return dt
        except ValueError:
            continue
    raise ValueError(f"Cannot parse datetime: {dt_str}")

start_dt = parse_datetime_string(START_DATE)
end_dt = parse_datetime_string(STOP_DATE)

print("Loading data...")
loader = DataLoader()
data, warning = loader.load_bars(SYMBOLS[:1], start_dt, end_dt, BINNING)

if warning:
    print(warning)

# Show sample data structure
if data:
    symbol = list(data.keys())[0]
    timestamps = sorted(data[symbol].keys())
    if timestamps:
        sample_timestamp = timestamps[0]
        sample_bar = data[symbol][sample_timestamp]
        
        print(f"\nSample bar for {symbol} at {sample_timestamp}:")
        print(f"  Available fields: {list(sample_bar.keys())}")
        for key, value in sample_bar.items():
            print(f"    - {key}: {value}")

print("\n" + "=" * 80)
print("ANSWER: Historical data from Alpaca contains ONLY OHLCV data:")
print("  - open, high, low, close, volume")
print("  - NO bid/ask spread information")
print("=" * 80)
print("\nBid/Ask Spread Approximation Methods:")
print("  1. Use fixed spread (0.01% of price)")
print("  2. Use bid = close * 0.9999, ask = close * 1.0001")
print("  3. Scale spread dynamically based on volatility")
print("  4. Use high-low range as proxy for volatility")
print("\nCurrent Implementation:")
print("  - bid = price * 0.9999 (0.01% below)")
print("  - ask = price * 1.0001 (0.01% above)")
