# Historical Backtesting System - Penguin Capitalist

Complete refactor of the trading simulation system to run **historical backtests** instead of real-time trading.

## 📋 Overview

The new system architecture provides:

- **Historical Data Loading**: Fetches OHLCV data from Alpaca for specified date ranges
- **Stale Data Detection**: Automatically removes symbols with insufficient/synthetic data
- **Multi-Strategy Testing**: Simultaneously runs all configured penguin strategies
- **Progress Tracking**: Real-time tqdm progress bars
- **Comprehensive Evaluation**: Performance metrics, capital curves, trade logs, and rankings
- **Clean Organization**: Modular structure with clear separation of concerns

## 🗂️ Project Structure

```
Penguin-Capitalist/
├── backtest/                    # Backtesting engine
│   ├── __init__.py
│   ├── portfolio.py            # Portfolio management & position tracking
│   ├── data_loader.py          # Alpaca historical data fetching
│   └── evaluator.py            # Performance metrics & reporting
├── scripts/                     # Runnable scripts
│   ├── __init__.py
│   └── backtest_runner.py      # Main backtest execution
├── indicators/                  # Technical analysis indicators
│   ├── __init__.py
│   ├── momentum.py             # RSI, ROC
│   └── statsistics.py          # SMA, EMA (note: typo in filename kept for compatibility)
├── penguins/                    # Trading strategies
│   ├── base_penguin.py
│   ├── *_penguin.py            # Individual strategy implementations
│   └── __init__.py
├── backtest_results/            # Output directory for results
│   ├── curves_data.json        # Capital curves for all strategies
│   ├── metrics_summary.json    # Performance metrics
│   └── trades_log.txt          # Detailed trade history
├── run_current/                 # Legacy results
├── config.py                    # Configuration (symbols, capital, timeframe, etc.)
├── run_simulation.py            # Main entry point
└── requirements.txt             # Dependencies
```

## ⚙️ Configuration

Edit [config.py](config.py) to customize:

```python
# Trading symbols to backtest
SYMBOLS = ["NVDA", "AAPL", "PLTR", ...]

# Initial capital
INITIAL_CAPITAL = 5000.0

# Transaction costs
TRANSACTION_COST = 0

# Timeframe for bars
BAR_TIMEFRAME_MINUTES = 1  # 1-minute bars

# Start time (CET timezone)
Run_start = 20260220_1630  # Feb 20, 2026 at 4:30 PM CET

# Active strategies to test
ACTIVE_PENGUINS = [
    BreakoutPenguin,
    MomentumPenguin,
    TrendPenguin,
    # ... more strategies
]
```

## 🚀 Running Backtests

### Prerequisites

1. **Set up Alpaca API credentials**:
   ```bash
   export APCA_API_KEY_ID="your_key_id"
   export APCA_API_SECRET_KEY="your_secret"
   ```

2. **Activate virtual environment**:
   ```bash
   source venvPeng/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

### Execute Backtest

```bash
python run_simulation.py
```

### What happens:

1. ✅ Loads historical 1-minute bars from Alpaca for all symbols
2. 🚨 Detects and removes stale/synthetic data
3. 📊 Initializes all penguin strategies
4. ⏳ Iterates through bars with tqdm progress display
5. 🤖 Each penguin makes BUY/SELL/HOLD decisions per symbol
6. 💾 Records portfolio values and trades
7. 🏁 Sells all positions at the end
8. 📈 Calculates metrics and generates reports

## 📊 Output Files

All results saved to `backtest_results/`:

### `metrics_summary.json`
Performance metrics for each strategy:
```json
{
  "BreakoutPenguin": {
    "total_return": 250.50,
    "return_pct": 5.01,
    "max_drawdown": -12.34,
    "sharpe_ratio": 1.23,
    "total_trades": 45,
    "buy_trades": 23,
    "sell_trades": 22,
    "final_value": 5250.50
  },
  ...
}
```

### `curves_data.json`
Portfolio value history for each strategy (for visualization):
```json
{
  "BreakoutPenguin": [5000.00, 5010.50, 5008.20, ...],
  ...
}
```

### `trades_log.txt`
Detailed trade-by-trade history for each strategy

## 🎯 Key Features

### 1. Stale Data Detection
Automatically eliminates symbols with:
- No recent data
- Very low volume
- Missing bars (synthetic data gaps)

```python
valid_symbols, stale_symbols = loader.detect_stale_data(data)
```

### 2. Real-time Progress Tracking
```
Executing bars: 87%|████████▋     | 523/600 [00:34<00:05, 15.2it/s]
```

### 3. Performance Ranking
Console output shows all strategies ranked by return:
```
====================================================================================================
STRATEGY                            FINAL VALUE    RETURN %     TRADES    SHARPE
====================================================================================================
MomentumPenguin                       $5,523.42      10.47%        34       1.45
BreakoutPenguin                       $5,412.18       8.24%        28       0.93
...
====================================================================================================

🏆 Best Performer: MomentumPenguin
   Final Value: $5,523.42
   Return: 10.47%
   Max Drawdown: -8.34%
   Sharpe Ratio: 1.45
```

### 4. Portfolio Management
The `Portfolio` class tracks:
- Positions per symbol
- Cost basis for P&L calculation
- Transaction history
- Portfolio value over time

```python
portfolio = Portfolio(initial_capital=5000, transaction_cost=0)
portfolio.buy("AAPL", 1, 150.00, timestamp)
portfolio.sell("AAPL", 1, 155.00, timestamp)
value = portfolio.get_total_value(current_prices)
pnl_abs, pnl_pct = portfolio.get_pnl(current_prices)
```

### 5. Technical Indicators
Ready-to-use indicators in `indicators/`:
- **momentum.py**: RSI, ROC
- **statsistics.py**: SMA, EMA, Bollinger Bands, ATR

```python
from indicators.momentum import rsi, roc
from indicators.statsistics import sma, ema

rsi_value = rsi(prices, period=14)  # 0-100
roc_value = roc(prices, period=5)   # decimal change
```

## 🔧 Customizing Backtests

### Adjust Duration
In [scripts/backtest_runner.py](scripts/backtest_runner.py), modify:
```python
num_bars = 60  # Change to desired number of 1-minute bars
```

### Change Timeframe
In [config.py](config.py), modify:
```python
BAR_TIMEFRAME_MINUTES = 5  # Use 5-minute bars instead
```

### Add Custom Strategies
1. Create a new file in `penguins/my_strategy_penguin.py`:
```python
from penguins.base_penguin import BasePenguin

class MyStrategyPenguin(BasePenguin):
    def __init__(self):
        super().__init__("MyStrategyPenguin")
    
    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        # Your logic here
        return "BUY", 1  # or "SELL", 1 or "HOLD", 0
```

2. Add to imports in [config.py](config.py) and `ACTIVE_PENGUINS` list

## 📈 Performance Metrics Explained

- **Total Return**: Dollar amount gained/lost
- **Return %**: Percentage return on initial capital
- **Max Drawdown**: Largest peak-to-trough decline
- **Sharpe Ratio**: Risk-adjusted return (higher is better)
- **Trade Count**: Total number of buy + sell orders
- **Buy/Sell Trades**: Individual order counts

## ⚠️ Important Notes

- **No real money involved**: This is purely historical simulation
- **Data source**: Alpaca market data (requires valid API credentials)
- **Synthetic data handling**: Stale data is automatically filtered to prevent trading on gaps
- **Timezone**: Config times are in CET (Europe/Berlin); converted to UTC for API calls
- **Position sizing**: Currently 1 share per buy signal (configurable in strategies)

## 🐛 Troubleshooting

### "Missing Alpaca API credentials"
Set environment variables:
```bash
export APCA_API_KEY_ID="your_key"
export APCA_API_SECRET_KEY="your_secret"
```

### No valid symbols after stale data filtering
The data_loader is filtering out symbols. Check:
- Symbol availability/spelling
- Market hours (Alpaca data may be sparse outside trading hours)
- Minimum volume thresholds in `data_loader.detect_stale_data()`

### Strategy not included in results
Verify it's in `ACTIVE_PENGUINS` in [config.py](config.py) and imports work

## 📝 Recent Changes

- ✅ Converted from real-time to historical simulation
- ✅ Created modular backtest infrastructure
- ✅ Added automatic stale data detection
- ✅ Created comprehensive evaluation system
- ✅ Added technical indicators module
- ✅ Implemented progress tracking with tqdm
- ✅ Generated detailed performance reports

## 🎓 How It Works

```
1. Config & Setup
   └─> Load symbols, capital, timeframe from config.py

2. Data Loading
   └─> Fetch historical OHLCV bars from Alpaca API

3. Data Validation
   └─> Remove stale/synthetic data, keep only valid symbols

4. Portfolio Initialization
   └─> Create Portfolio object for each penguin strategy

5. Bar-by-Bar Simulation
   └─> For each timestamp in historical data:
       ├─> Update price history for each symbol
       ├─> Query each penguin for decision
       ├─> Execute trades (BUY/SELL)
       └─> Record portfolio value

6. Position Closure
   └─> Sell all remaining positions at final price

7. Metrics Calculation
   └─> Calculate return, drawdown, Sharpe ratio, etc.

8. Report Generation
   └─> Save curves, metrics, trades to backtest_results/

9. Display Summary
   └─> Show ranked strategies by performance
```

---

**Last Updated**: February 25, 2026
