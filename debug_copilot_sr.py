#!/usr/bin/env python3
"""Debug CopilotPenguin and SupportResistancePenguin trading logic."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from datetime import datetime
from backtest.data_loader import DataLoader
from config import SYMBOLS, START_DATE, STOP_DATE, BINNING, INITIAL_CAPITAL, TRANSACTION_COST
from backtest.portfolio import Portfolio
from penguins.copilot_penguin import CopilotPenguin
from penguins.support_resistance_penguin import SupportResistancePenguin
import pytz
from collections import defaultdict

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
data, warning = loader.load_bars(SYMBOLS, start_dt, end_dt, BINNING)
if warning:
    print(warning)

valid_symbols, stale_symbols = loader.detect_stale_data(data)
print(f"Valid symbols: {len(valid_symbols)}\n")

# Initialize strategies
copilot = CopilotPenguin()
sr = SupportResistancePenguin()

copilot_portfolio = Portfolio(INITIAL_CAPITAL, TRANSACTION_COST)
sr_portfolio = Portfolio(INITIAL_CAPITAL, TRANSACTION_COST)

sorted_timestamps = sorted(set(ts for symbol in valid_symbols for ts in data[symbol].keys()))
print(f"Total bars: {len(sorted_timestamps)}\n")

test_symbol = "AAPL"
print(f"Testing {test_symbol} - CopilotPenguin and SupportResistancePenguin")
print("=" * 100)

price_history = defaultdict(list)

# Run through first 200 bars
for bar_idx, timestamp in enumerate(sorted_timestamps[:200]):
    prices = {}
    for symbol in valid_symbols:
        if timestamp in data[symbol]:
            bar = data[symbol][timestamp]
            prices[symbol] = bar['close']
            price_history[symbol].append(bar['close'])
    
    if test_symbol not in prices or len(price_history[test_symbol]) < 3:
        continue
    
    mid_prices = price_history[test_symbol]
    bid = prices[test_symbol] * 0.9999
    ask = prices[test_symbol] * 1.0001
    
    # Test CopilotPenguin
    signal_cop, qty_cop = copilot.decide(test_symbol, mid_prices, bid, ask, copilot_portfolio)
    
    # Test SupportResistancePenguin
    signal_sr, qty_sr = sr.decide(test_symbol, mid_prices, bid, ask, sr_portfolio)
    
    # Print debug info every 10 bars or when signal is generated
    if bar_idx % 15 == 0 or signal_cop != "HOLD" or signal_sr != "HOLD":
        print(f"\nBar {bar_idx:3d} (len={len(mid_prices):3d}): Price=${prices[test_symbol]:.2f}")
        
        if len(mid_prices) >= 50:
            # Calculate indicators for CopilotPenguin
            from indicators.momentum import rsi, roc
            rsi_val = rsi(mid_prices, n=14)
            roc_short = roc(mid_prices, n=3)
            roc_medium = roc(mid_prices, n=7)
            sma_20 = sum(mid_prices[-20:]) / 20
            sma_50 = sum(mid_prices[-50:]) / 50
            is_uptrend = prices[test_symbol] > sma_20 > sma_50
            
            print(f"  CopilotPenguin:")
            print(f"    RSI={rsi_val:.2f}, ROC_med={roc_medium:.6f} (min={copilot.min_trend_roc:.6f}), Uptrend={is_uptrend}")
            print(f"    → Signal: {signal_cop} qty={qty_cop}")
        
        print(f"  SupportResistancePenguin:")
        print(f"    → Signal: {signal_sr} qty={qty_sr}")

print("\n" + "=" * 100)
print("\nKey findings:")
print("- CopilotPenguin requires: ROC > 0.005 AND RSI 40-70")
print("- SupportResistancePenguin requires: Zones detected + buy/sell signals")
print("- Both need proper conditions to trigger")
