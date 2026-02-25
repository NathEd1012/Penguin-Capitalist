"""Investigate price data around bar 428."""
import json
from pathlib import Path

# Load curves data to get bar count
curves_file = Path("run_current/curves_data.json")
with open(curves_file, 'r') as f:
    curves = json.load(f)

# Load all metrics to see what symbols CarefulTrendPenguin held
metrics_file = Path("run_current/metrics_summary.json")
with open(metrics_file, 'r') as f:
    metrics = json.load(f)

print("CarefulTrendPenguin at end of run:")
print("=" * 80)
careful_metrics = metrics.get("CarefulTrendPenguin", {})
print(f"Total Trades: {careful_metrics.get('total_trades', 0)}")
print(f"Buy Trades: {careful_metrics.get('buy_trades', 0)}")
print(f"Sell Trades: {careful_metrics.get('sell_trades', 0)}")
print(f"Final Value: ${careful_metrics.get('final_value', 0):,.2f}")

print("\n" + "=" * 80)
print("Possible cause of bar 428 drop:")
print("=" * 80)
print("""
The -44.06% drop at bar 428 occurred when:
- No trades were recorded for CarefulTrendPenguin
- RSI Mean Reversion bought 1 AAPL
- Value dropped from $4,254.70 → $2,380.18

This suggests:
1. Missing price data for one or more symbols held by CarefulTrendPenguin
2. The portfolio valuation couldn't compute certain positions at bar 428
3. Then prices returned at bar 429, restoring the +78.77% recovery

ACTION NEEDED:
1. Add defensive price handling in get_total_value()
2. Log missing price data events
3. Use last-known-good price when current data is missing
""")

# Show curve values
print("\nCareful Trend Penguin curve profile:")
print("-" * 80)
values = curves["CarefulTrendPenguin"]
print(f"Initial: ${values[0]:,.2f}")
print(f"Min: ${min(values):,.2f} (bar {values.index(min(values))})")
print(f"Max: ${max(values):,.2f}")
print(f"Final: ${values[-1]:,.2f}")
print(f"Return: {((values[-1] - values[0]) / values[0] * 100):.2f}%")
