#!/usr/bin/env python3
"""Test and demonstrate the SyntheticSpreadModel."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.synthetic_spread_model import SyntheticSpreadModel
from datetime import datetime, timedelta
import pytz

# Initialize spread model (Alpaca market hours: 9:30 AM - 4:00 PM ET = 14:30 - 20:00 UTC)
model = SyntheticSpreadModel(
    market_open_time="14:30",
    market_close_time="20:00",
    timezone="UTC"
)

print("=" * 80)
print("SYNTHETIC SPREAD MODEL TEST")
print("=" * 80)
print()

# Test scenarios
scenarios = [
    {
        "name": "Mid-day trading (stable spread)",
        "timestamp": "2026-01-20T16:00:00Z",  # 10:30 AM ET
        "mid_price": 150.50,
        "high": 151.25,
        "low": 150.10,
    },
    {
        "name": "Market opening (widened spread - first 15 min)",
        "timestamp": "2026-01-20T14:35:00Z",  # 9:35 AM ET (5 min after open)
        "mid_price": 150.50,
        "high": 151.25,
        "low": 150.10,
    },
    {
        "name": "Market closing (widened spread - last 15 min)",
        "timestamp": "2026-01-20T19:50:00Z",  # 3:50 PM ET (10 min before close)
        "mid_price": 150.50,
        "high": 151.25,
        "low": 150.10,
    },
    {
        "name": "High volatility candle (wide high-low range)",
        "timestamp": "2026-01-20T16:00:00Z",
        "mid_price": 150.50,
        "high": 155.00,  # 3% range
        "low": 146.00,
    },
    {
        "name": "Low volatility candle (tight range)",
        "timestamp": "2026-01-20T16:00:00Z",
        "mid_price": 150.50,
        "high": 150.60,
        "low": 150.40,
    },
    {
        "name": "Low price stock (spread driven by price factor)",
        "timestamp": "2026-01-20T16:00:00Z",
        "mid_price": 5.50,
        "high": 5.55,
        "low": 5.45,
    },
]

for scenario in scenarios:
    print(f"Scenario: {scenario['name']}")
    print(f"  Timestamp: {scenario['timestamp']}")
    print(f"  Mid Price: ${scenario['mid_price']:.2f}")
    print(f"  High/Low: ${scenario['high']:.2f} / ${scenario['low']:.2f}")
    
    bid, ask, spread = model.get_bid_ask(
        mid_price=scenario['mid_price'],
        high=scenario['high'],
        low=scenario['low'],
        timestamp=scenario['timestamp']
    )
    
    print(f"  Results:")
    print(f"    Bid: ${bid:.4f}")
    print(f"    Ask: ${ask:.4f}")
    print(f"    Spread: ${spread:.4f} ({spread/scenario['mid_price']*100:.4f}% of mid)")
    print()

print("=" * 80)
print("EXECUTION PRICE SIMULATION")
print("=" * 80)
print()

# Demonstrate buy/sell execution
mid_price = 150.50
high = 151.25
low = 150.10
timestamp = "2026-01-20T16:00:00Z"

bid, ask, spread = model.get_bid_ask(mid_price, high, low, timestamp)

initial_capital = 5000.0
buy_price = ask
sell_price = bid

shares = initial_capital / buy_price
profit_per_share = sell_price - buy_price
total_profit = shares * profit_per_share
roi = (total_profit / initial_capital) * 100

print(f"Initial Capital: ${initial_capital:.2f}")
print(f"BUY execution price (ask): ${buy_price:.4f}")
print(f"Shares purchased: {shares:.2f}")
print()
print(f"SELL execution price (bid): ${sell_price:.4f}")
print(f"Profit per share: ${profit_per_share:.4f}")
print(f"Total spread cost: ${total_profit:.2f}")
print(f"ROI from spread: {roi:.4f}%")
print()

print("=" * 80)
print("PERFORMANCE TEST (1000 candles)")
print("=" * 80)
print()

import time

# Generate 1000 candles and measure performance
base_time = datetime(2026, 1, 20, 14, 30, 0, tzinfo=pytz.UTC)
test_count = 1000

start = time.time()
for i in range(test_count):
    candle_time = base_time + timedelta(minutes=i)
    mid_price = 150.50 + (i % 100) * 0.01  # Simulate small price variations
    high = mid_price + 0.50
    low = mid_price - 0.50
    
    bid, ask, spread = model.get_bid_ask(
        mid_price=mid_price,
        high=high,
        low=low,
        timestamp=candle_time
    )

elapsed = time.time() - start
per_candle_ms = (elapsed / test_count) * 1000

print(f"Processed {test_count} candles in {elapsed:.4f} seconds")
print(f"Average time per candle: {per_candle_ms:.4f} ms")
print(f"Throughput: {test_count/elapsed:.0f} candles/second")
print()
