#!/usr/bin/env python3
"""Debug S/R level detection for the multi-timeframe strategy."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from penguins.minmax_sr20_penguin import SupportResistancePenguin
import random

# Create strategy instance
sr = SupportResistancePenguin()

# Generate synthetic price data (1 year of 1-minute bars)
print("Generating synthetic price data...")
num_bars = 390 * 252  # ~1 year of trading
prices = []
current_price = 100.0
for i in range(num_bars):
    # Random walk with support around 97-99 and resistance around 101-103
    change = random.gauss(0, 0.5)
    current_price = max(95, min(105, current_price + change))
    prices.append(current_price)

print(f"✓ Generated {len(prices)} bars of price data")
print(f"  Price range: {min(prices):.2f} - {max(prices):.2f}")
print(f"  Current price: {prices[-1]:.2f}")
print()

# Test level detection
print("Testing multi-timeframe level detection...")
sr._update_levels_for_symbol("TEST", prices)

if "TEST" in sr.level_cache:
    print(f"✓ Levels cached for TEST symbol")
    for timeframe, data in sr.level_cache["TEST"].items():
        supports = data.get("support", [])
        resistances = data.get("resistance", [])
        print(f"  {timeframe:3s}: supports={len(supports):2d} {supports[:3] if supports else 'none'}")
        print(f"        resistances={len(resistances):2d} {resistances[-3:] if resistances else 'none'}")
else:
    print("✗ No levels cached!")

print()
support, resistance = sr._get_relevant_levels("TEST", prices[-1])
print(f"Selected levels:")
print(f"  Support: {support:.2f}")
print(f"  Resistance: {resistance:.2f}")
print(f"  Current price: {prices[-1]:.2f}")
print(f"  Position relative to levels:")
print(f"    - {((prices[-1] - support) / (resistance - support) * 100):.1f}% between support and resistance")
