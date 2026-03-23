#!/usr/bin/env python3
"""Debug script to analyze strategy signals during backtesting."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime
from backtest.data_loader import DataLoader
from config import SYMBOLS, START_DATE, STOP_DATE, BINNING, ACTIVE_PENGUINS
from backtest.portfolio import Portfolio
from config import INITIAL_CAPITAL, TRANSACTION_COST
import pytz

# Parse dates
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

# Load data
print("Loading data...")
loader = DataLoader()
data, warning = loader.load_bars(SYMBOLS, start_dt, end_dt, BINNING)
if warning:
    print(warning)

# Detect stale symbols
valid_symbols, stale_symbols = loader.detect_stale_data(data)
print(f"Valid symbols: {len(valid_symbols)}, Stale: {stale_symbols}")

# Initialize strategies
print(f"\nInitializing {len(ACTIVE_PENGUINS)} strategies:")
portfolios = {}
penguins = {}
for penguin_class in ACTIVE_PENGUINS:
    try:
        penguin = penguin_class()
        pen_name = penguin.name
        portfolios[pen_name] = Portfolio(INITIAL_CAPITAL, TRANSACTION_COST)
        penguins[pen_name] = penguin
        print(f"  ✓ {pen_name}")
    except Exception as e:
        print(f"  ✗ {penguin_class.__name__}: {e}")

# Get timestamps
sorted_timestamps = sorted(
    set(ts for symbol in valid_symbols for ts in data[symbol].keys())
)

print(f"\nTotal bars: {len(sorted_timestamps)}")

# Find one symbol we can test
test_symbol = valid_symbols[0] if valid_symbols else SYMBOLS[0]
print(f"\nTesting with symbol: {test_symbol}")

# Run through first 100 bars
print(f"\nAnalyzing strategy signals (first 100 bars):")
print("=" * 80)

from collections import defaultdict
price_history = defaultdict(list)

for bar_idx, timestamp in enumerate(sorted_timestamps[:100]):
    # Get prices
    prices = {}
    for symbol in valid_symbols:
        if timestamp in data[symbol]:
            bar = data[symbol][timestamp]
            prices[symbol] = bar['close']
            price_history[symbol].append(bar['close'])
    
    if test_symbol not in prices:
        continue
    
    # Test each strategy
    for pen_name, penguin in penguins.items():
        portfolio = portfolios[pen_name]
        
        if test_symbol not in price_history or len(price_history[test_symbol]) < 2:
            continue
        
        mid_prices = price_history[test_symbol]
        bid = prices[test_symbol] * 0.9999
        ask = prices[test_symbol] * 1.0001
        
        signal, qty = penguin.decide(test_symbol, mid_prices, bid, ask, portfolio)
        
        if signal != "HOLD" or bar_idx % 10 == 0:
            print(f"Bar {bar_idx:3d}: {pen_name:30s} -> {signal} qty={qty} (price=${prices[test_symbol]:.2f}, bars={len(mid_prices)})")

print("\n" + "=" * 80)
print("\nKey Issues:")
print("- SMA20Penguin: initialize_sma_levels() never called (data_client remains None)")
print("- CopilotPenguin: Requires SMA20 > SMA50 + momentum > 0.005 + RSI 50-70 (strict conditions)")
print("- SupportResistancePenguin: Needs 20 bars minimum (3+3+14)")
