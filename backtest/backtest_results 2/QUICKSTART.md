# Quick Start Guide - Historical Backtesting

## ✅ System Status

Your historical backtesting system is **fully operational**! 

## 🚀 How to Run

### 1. Basic Run (recommended for first test)

```bash
python run_simulation.py
```

That's it! The system will:
- ✅ Load historical market data from Alpaca
- ✅ Filter out stale/synthetic data automatically
- ✅ Run all 13 penguin strategies in parallel
- ✅ Show live progress with tqdm
- ✅ Generate detailed performance reports

### 2. Run with Virtual Environment (if not activated)

```bash
source venvPeng/bin/activate
python run_simulation.py
```

Or:

```bash
./venvPeng/bin/python3 run_simulation.py
```

## 📋 Customization

### Change Backtest Duration

Edit [config.py](../config.py):

```python
NUM_BARS_TO_BACKTEST = 180  # 3 hours of 1-minute bars
NUM_BARS_TO_BACKTEST = 60   # 1 hour
NUM_BARS_TO_BACKTEST = 1440 # 1 day
```

### Change Timeframe

```python
BAR_TIMEFRAME_MINUTES = 1   # 1-minute bars (default)
BAR_TIMEFRAME_MINUTES = 5   # 5-minute bars
BAR_TIMEFRAME_MINUTES = 60  # 1-hour bars
```

### Change Start Date/Time

For a different date, update `Run_start` (format: YYYYMMDD_HHMM as integer):

```python
Run_start = 202602201400  # Feb 20, 2026 at 2:00 PM CET
```

**Current date:** February 25, 2026

**Recent historical dates you can test:**
- `202602251200` - Today at noon CET
- `202602241400` - Yesterday at 2 PM CET
- `202602231000` - 2 days ago at 10 AM CET

### Change Symbols

Edit the `SYMBOLS` list in [config.py](../config.py):

```python
SYMBOLS = [
    "NVDA",
    "AAPL",
    "PLTR",
    # ... add or remove symbols
]
```

### Select Specific Strategies

Edit `ACTIVE_PENGUINS` in [config.py](../config.py):

```python
ACTIVE_PENGUINS = [
    BreakoutPenguin,
    MomentumPenguin,
    # CommentOut strategies you don't want to test
]
```

## 📊 Output Files

After running, results appear in this folder:

- `curves_data.json` - Portfolio value history for each strategy (for plotting)
- `metrics_summary.json` - Performance metrics (return %, drawdown, Sharpe, etc.)
- `trades_log.txt` - Detailed trade-by-trade history

## 🏆 Interpreting Results

The console shows strategies ranked by return %:

```
STRATEGY                          FINAL VALUE    RETURN %     TRADES    SHARPE
CopilotPenguin                    $5,523.42      10.47%        34       1.45
BreakoutPenguin                   $5,412.18       8.24%        28       0.93
...

🏆 Best Performer: CopilotPenguin
   Return: 10.47% | Max Drawdown: -8.34% | Sharpe: 1.45
```

**Key Metrics:**
- **Return %** - Profit/loss as percentage of initial capital
- **Trades** - Total buy + sell orders executed
- **Sharpe Ratio** - Risk-adjusted return (higher is better)
- **Max Drawdown** - Largest peak-to-trough decline

## 🔍 Troubleshooting

### Issue: "No valid symbols to trade!"

**Cause:** All symbols have stale/insufficient data

**Solution:** 
- Use a more recent date (try today's date around trading hours)
- Check that symbols are actively trading on the chosen date
- Verify Alpaca credentials in `.env` file

### Issue: "Missing Alpaca API credentials"

**Cause:** Environment variables not loaded

**Solution:**
Verify `.env` file exists and has:
```
ALPACA_API_KEY = "YOUR_KEY"
ALPACA_SECRET_KEY = "YOUR_SECRET"
```

### Issue: Some strategies report 0 trades

**Cause:** Normal - some strategies only trade on specific signals

**Solution:** This is expected behavior. Different strategies have different trade frequencies.

## 📈 Next Steps

1. **Test with different dates** to see how strategies perform in various market conditions
2. **Adjust NUM_BARS_TO_BACKTEST** to test longer periods (e.g., full trading day)
3. **Modify penguin strategies** in `penguins/` folder to improve performance
4. **Analyze results** using the JSON output files for deeper analysis

## 📚 Full Documentation

See [BACKTEST_README.md](BACKTEST_README.md) for complete technical documentation.

## 🎯 Example Commands

**Quick test (20 minutes of data):**
```python
NUM_BARS_TO_BACKTEST = 20
python run_simulation.py
```

**Full trading session (6.5 hours):**
```python
NUM_BARS_TO_BACKTEST = 390  # Market hours: 9:30 AM - 4:00 PM
python run_simulation.py
```

**Daily backtest (1-hour bars, 1 full day):**
```python
BAR_TIMEFRAME_MINUTES = 60
NUM_BARS_TO_BACKTEST = 8  # ~8 hours of trading
python run_simulation.py
```

---

🚀 **Ready to backtest!** Run `python run_simulation.py` and see your strategies in action.
