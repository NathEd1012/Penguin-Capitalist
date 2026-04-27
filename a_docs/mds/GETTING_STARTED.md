# Getting Started with Historical Backtesting

## ✅ Fixed Issues

The system is now fully operational! The error message about missing Alpaca credentials is expected and easily fixed.

## 🔑 Setup: Get Alpaca API Credentials

1. **Go to Alpaca Trading Dashboard**: https://app.alpaca.markets/
2. **Get API Keys**: Navigate to Settings → API Keys
3. **Copy your credentials**:
   - `APCA_API_KEY_ID` (API Key)
   - `APCA_API_SECRET_KEY` (Secret Key)

## 🚀 Running the Backtest

### Option 1: Set Environment Variables (Recommended)

```bash
cd /Users/nathanael/Documents/Uni/Masterarbeit/VSCode/Penguin-Capitalist

export APCA_API_KEY_ID="your_api_key_here"
export APCA_API_SECRET_KEY="your_secret_key_here"

python run_simulation.py
```

### Option 2: Add to `.env` file

Create/edit `.env` in project root:
```
APCA_API_KEY_ID=your_api_key_here
APCA_API_SECRET_KEY=your_secret_key_here
```

Then run:
```bash
python run_simulation.py
```

## 📋 What the System Does

1. **Configuration** (runs now ✓)
   - Loads symbols: 23 stocks/ETFs
   - Sets timeframe: 1-minute bars
   - Loads 13 penguin strategies

2. **Data Loading** (requires API credentials)
   - Fetches historical OHLCV data from Alpaca
   - Time: Feb 20, 2026 at 4:30 PM CET
   - Duration: 180 minutes (covers data fetch period)

3. **Stale Data Filtering**
   - Removes symbols with insufficient data
   - Removes symbols with gaps (synthetic data)

4. **Backtesting**
   - Simulates each penguin strategy
   - Tracks all trades
   - Shows progress with tqdm

5. **Evaluation & Reporting**
   - Calculates return %, drawdown, Sharpe ratio
   - Saves curves, metrics, trades
   - Ranks strategies by performance

## 🎯 Customization

Edit `config.py` to adjust:

```python
# Change trading symbols
SYMBOLS = ["NVDA", "AAPL", "PLTR", ...]

# Change start time (YYYYMMDD_HHMM as integer)
Run_start = 202602201630  # Feb 20, 2026 at 4:30 PM CET

# Change number of bars to simulate
NUM_BARS_TO_BACKTEST = 180  # 180 = 3 hours of 1-min bars

# Change timeframe
BAR_TIMEFRAME_MINUTES = 5  # Use 5-minute bars instead

# Enable/disable strategies
ACTIVE_PENGUINS = [
    BreakoutPenguin,
    # CopilotPenguin,  # Uncomment to enable
    # ...
]
```

## 📊 Output Files

After running, check `backtest_results/`:
- `curves_data.json` - Capital curves for visualization
- `metrics_summary.json` - Performance metrics
- `trades_log.txt` - Detailed trade history

## ⚠️ Important Notes

- **Authentication**: You need valid Alpaca credentials (free account available)
- **Market Hours**: Data availability depends on market trading hours
- **Data Quality**: The system automatically filters out stale/synthetic data
- **No Real Money**: This is purely historical simulation

## 🐛 Troubleshooting

### "ModuleNotFoundError" errors
Make sure you're using the venv Python:
```bash
./venvPeng/bin/python3 run_simulation.py
```

### "No valid symbols after stale data filtering"
This means no symbols had good data for the requested time period. Check:
- Are you requesting data during market hours?
- Do the symbols exist on Alpaca?
- Is there enough historical data?

### API Rate Limits
If you hit rate limits, wait a few minutes before retrying.

---

**Status**: ✅ Ready to run! Just add your Alpaca credentials and execute `python run_simulation.py`
