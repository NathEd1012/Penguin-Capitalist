"""Analyze suspicious value drop around bar 430 for CarefulTrendPenguin."""
import json
from pathlib import Path

# Load curves data
curves_file = Path("run_current/curves_data.json")
with open(curves_file, 'r') as f:
    curves = json.load(f)

# Look at CarefulTrendPenguin
penguin_name = "CarefulTrendPenguin"
if penguin_name in curves:
    values = curves[penguin_name]
    
    print(f"CarefulTrendPenguin total bars: {len(values)}")
    print("=" * 80)
    
    # Show values around bar 430 (indices 425-435)
    print(f"\nValues around bar 430:")
    print("-" * 80)
    for i in range(max(0, 425), min(len(values), 435)):
        print(f"Bar {i}: ${values[i]:,.2f}")
    
    # Find the minimum value
    min_val = min(values)
    min_idx = values.index(min_val)
    print(f"\n\nGlobal minimum: Bar {min_idx} = ${min_val:,.2f}")
    
    # Show context around minimum (±10 bars)
    print(f"\nContext around minimum (±10 bars):")
    print("-" * 80)
    for i in range(max(0, min_idx-10), min(len(values), min_idx+11)):
        change = ""
        if i > 0:
            pct_change = ((values[i] - values[i-1]) / values[i-1]) * 100
            change = f" ({pct_change:+.2f}%)"
        marker = " <-- MINIMUM" if i == min_idx else ""
        print(f"Bar {i}: ${values[i]:,.2f}{change}{marker}")
    
    # Find all sharp drops (>15%)
    print(f"\n\nAll sharp drops (>15% in one bar):")
    print("-" * 80)
    for i in range(1, len(values)):
        pct_change = ((values[i] - values[i-1]) / values[i-1]) * 100
        if pct_change < -15:
            print(f"Bar {i-1} → {i}: ${values[i-1]:,.2f} → ${values[i]:,.2f} ({pct_change:.2f}%)")
