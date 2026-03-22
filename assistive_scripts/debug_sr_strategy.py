#!/usr/bin/env python3
"""Debug S/R strategy with actual price data from backtest."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from penguins.minmax_sr20_penguin import SupportResistancePenguin

# Generate realistic price data (trending down then up)
print("Generating realistic price scenario...")
prices = []
base_price = 250.0
for i in range(1000):
    # Downtrend for first 400 bars
    if i < 400:
        change = -0.1 + (0.2 * (i / 400))  # Gradual uptrend within downtrend
        price = base_price - 50 + (i * 0.1)
    # Bouncing phase (support zone) for next 300 bars
    elif i < 700:
        support_zone = base_price - 40
        cycle = (i - 400) % 50
        if cycle < 25:
            price = support_zone + (cycle / 25 * 15)  # Bounce up
        else:
            price = support_zone + 15 - ((cycle - 25) / 25 * 12)  # Settle, minor down
    # Uptrend for last 300 bars
    else:
        price = base_price - 35 + ((i - 700) * 0.05)
    
    prices.append(price)

print(f"✓ Generated {len(prices)} bars")
print(f"  Price range: {min(prices):.2f} - {max(prices):.2f}")
print(f"  Recent 10 prices: {[f'{p:.2f}' for p in prices[-10:]]}")

# Test strategy through time
sr = SupportResistancePenguin()
print("\n" + "="*70)
print("Simulating strategy decisions through time...")
print("="*70 + "\n")

# Mock portfolio
class MockPosition:
    def __init__(self):
        self.qty = 0
        self.avg_price = 0

class MockPortfolio:
    def __init__(self):
        self.positions = {}
        self.cash = 5000.0

portfolio = MockPortfolio()
portfolio.positions["TEST"] = MockPosition()

buy_signals = 0
sell_signals = 0
hold_count = 0

for bar_idx in range(100, min(len(prices), 800)):
    mid_prices = prices[:bar_idx + 1]
    current_price = mid_prices[-1]
    previous_price = mid_prices[-2]
    
    # Simulate bid/ask
    bid = current_price * 0.99
    ask = current_price * 1.01
    
    action, qty = sr.decide("TEST", mid_prices, bid, ask, portfolio)
    
    if action == "BUY":
        buy_signals += 1
        print(f"Bar {bar_idx:4d} (price {current_price:7.2f}): BUY  ✓")
        portfolio.positions["TEST"].qty = qty
        portfolio.positions["TEST"].avg_price = current_price
        portfolio.cash -= ask * qty
    elif action == "SELL":
        sell_signals += 1
        print(f"Bar {bar_idx:4d} (price {current_price:7.2f}): SELL ✓")
        pnl = (current_price - portfolio.positions["TEST"].avg_price) * portfolio.positions["TEST"].qty
        portfolio.cash += current_price * qty + pnl
        portfolio.positions["TEST"].qty = 0
    else:
        hold_count += 1

print(f"\n" + "="*70)
print(f"Summary:")
print(f"  Buy signals: {buy_signals}")
print(f"  Sell signals: {sell_signals}")
print(f"  Holdings: {hold_count}")
print(f"  Cache entries: {len(sr.level_cache.get('TEST', {}))}")
if "TEST" in sr.level_cache:
    for tf, data in sr.level_cache["TEST"].items():
        sup = data.get("support", [None])[0]
        res = data.get("resistance", [None])[0]
        print(f"    {tf:3s}: S={sup:7.2f}, R={res:7.2f}")
