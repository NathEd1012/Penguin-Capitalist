"""Debug script to check data quality from Alpaca."""
from datetime import datetime, timedelta
import sys
from pathlib import Path
import pytz

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest.data_loader import DataLoader

cet = pytz.timezone('Europe/Berlin')
start = (datetime.now(cet) - timedelta(days=5)).replace(hour=14, minute=0, second=0, microsecond=0)
end = start + timedelta(hours=1)

start_utc = start.astimezone(pytz.UTC)
end_utc = end.astimezone(pytz.UTC)

print(f"Loading data from {start_utc} to {end_utc}\n")

loader = DataLoader()
data, warning = loader.load_bars(
    ["AAPL", "NVDA", "MSFT"],
    start_utc,
    end_utc,
    1
)

if warning:
    print(warning)

for symbol, bars in data.items():
    print(f"{symbol}: {len(bars)} bars")
    if bars:
        timestamps = sorted(bars.keys())
        print(f"  First: {timestamps[0]}")
        print(f"  Last:  {timestamps[-1]}")
        sample_key = list(bars.keys())[0]
        sample = bars[sample_key]
        print(f"  Sample: {sample}")
        
        # Check volume
        volumes = [b['volume'] for b in bars.values()]
        avg_vol = sum(volumes) / len(volumes) if volumes else 0
        print(f"  Avg Volume: {avg_vol:.0f}\n")
