# Configuration Module

This folder contains all configuration settings for the Penguin Capitalist backtesting system.

## 📁 File Structure

```
config/
├── __init__.py          # Consolidates all config imports
├── symbols.py           # Trading symbols and categories  
├── portfolio.py         # Portfolio capital and costs
├── backtest.py          # Backtest timing and execution
├── strategies.py        # Active trading strategies (penguins)
└── README.md            # This file
```

## 🎯 Quick Start

### Import Configuration

Import anywhere in your code:

```python
from config import (
    SYMBOLS,           # Active trading symbols
    INITIAL_CAPITAL,   # Starting capital
    START_DATE,        # Backtest start
    STOP_DATE,         # Backtest end
    BINNING,           # Timeframe ("1m", "5m", etc.)
    ACTIVE_PENGUINS,   # Strategy classes
)
```

### Modify Configuration

Edit the appropriate file in `config/`:

- **Change symbols** → Edit `config/symbols.py` (ACTIVE_SYMBOLS list)
- **Change capital/costs** → Edit `config/portfolio.py`
- **Change dates/timeframe** → Edit `config/backtest.py`
- **Enable/disable strategies** → Edit `config/strategies.py`

## 📄 Configuration Files

### 1. `symbols.py` - Trading Symbols

Defines which symbols to trade and provides categorized symbol lists.

**Key Variables:**
- `ACTIVE_SYMBOLS` - Primary list used for backtesting (22 symbols by default)
- `SYMBOL_CATEGORIES` - Dict of symbols organized by sector/type
- `ALL_SYMBOLS` - All available symbols flattened
- `US_EQUITIES`, `INTERNATIONAL_EQUITIES`, `ETFS` - Filtered lists

**Example:**
```python
# Edit ACTIVE_SYMBOLS to change what's traded
ACTIVE_SYMBOLS = [
    "AAPL",
    "MSFT", 
    "NVDA",
    # ... add more
]
```

### 2. `portfolio.py` - Portfolio Settings

Capital and transaction cost configuration.

**Key Variables:**
- `INITIAL_CAPITAL` - Starting capital in USD (default: $5000)
- `TRANSACTION_COST` - Fixed cost per trade in USD (default: $0)

**Example:**
```python
INITIAL_CAPITAL = 10000.0    # Start with $10k
TRANSACTION_COST = 5.0       # $5 per trade
```

### 3. `backtest.py` - Backtest Timing

Date ranges, timeframes, and execution settings.

**Key Variables:**
- `START_DATE` - Backtest start datetime (ISO format or "TODAY")
- `STOP_DATE` - Backtest end datetime (ISO format or "TODAY")
- `BINNING` - Candle interval: "1m", "5m", "15m", "1h", "1d"
- `SAVE_TO_RUN_OLD` - Whether to archive runs

**Examples:**
```python
# Specific date range
START_DATE = "2026-01-15 09:30:00"
STOP_DATE = "2026-02-15 16:00:00"

# Use "TODAY" for dynamic dates (resolves to yesterday 23:50 UTC)
STOP_DATE = "TODAY"

# Change timeframe
BINNING = "5m"  # 5-minute bars instead of 1-minute
```

**Special Date Handling:**
- `"TODAY"` resolves to yesterday at 23:50 UTC (avoids Alpaca recent data restrictions)
- Dates without timezone assume UTC
- ISO format: "YYYY-MM-DD HH:MM:SS"

### 4. `strategies.py` - Active Strategies

Which trading strategies (penguins) to run in the backtest.

**Key Variables:**
- `ACTIVE_PENGUINS` - List of strategy classes to execute

**Example:**
```python
ACTIVE_PENGUINS = [
    SupportResistancePenguin,           # ✓ Active
    MultitimeframeReactionSRPenguin,    # ✓ Active
    # MomentumPenguin,                  # ✗ Commented out = disabled
    CopilotPenguin,                     # ✓ Active
]
```

**To enable/disable strategies:**
- Uncomment to enable: Remove the `#` prefix
- Comment out to disable: Add `#` prefix

## 🔧 Common Configuration Tasks

### Change Trading Symbols

Edit [config/symbols.py](symbols.py):

```python
ACTIVE_SYMBOLS = [
    "AAPL",
    "MSFT",
    "GOOGL",  # Add new symbols here
]
```

### Change Backtest Date Range

Edit [config/backtest.py](backtest.py):

```python
START_DATE = "2026-01-01 09:30:00"
STOP_DATE = "2026-01-31 16:00:00"
```

### Change Starting Capital

Edit [config/portfolio.py](portfolio.py):

```python
INITIAL_CAPITAL = 10000.0  # Start with $10k instead of $5k
```

### Add Transaction Costs

Edit [config/portfolio.py](portfolio.py):

```python
TRANSACTION_COST = 5.0  # $5 per trade (e.g., for traditional brokers)
```

### Use Different Timeframe

Edit [config/backtest.py](backtest.py):

```python
BINNING = "5m"   # 5-minute bars (faster backtest, less granular)
BINNING = "1h"   # 1-hour bars (much faster, daily strategies)
BINNING = "1d"   # Daily bars (long-term strategies)
```

### Enable/Disable Strategies

Edit [config/strategies.py](strategies.py):

```python
# Comment out with # to disable
# Uncomment to enable
ACTIVE_PENGUINS = [
    SupportResistancePenguin,     # ✓ Enabled
    # MomentumPenguin,            # ✗ Disabled
    CopilotPenguin,               # ✓ Enabled
]
```

## 📊 Symbol Categories

The `SYMBOL_CATEGORIES` dict organizes symbols by sector:

- **tech** - Technology companies (NVDA, AAPL, MSFT, etc.)
- **defense** - Defense contractors (LMT, NOC, RTX, GD)
- **alt_assets** - Alternative assets (MSTR, MP, PLTR)
- **international** - International stocks (NVO, ASML, TSM, BABA)
- **miners** - Mining ETFs (COPX, PICK, REMX, GDXJ, SIL)
- **commodities** - Commodity ETFs (GLD, SLV, PPLT, JO, LIT)
- **macro_etfs** - Broad market ETFs (SPY, QQQ, IWM, TLT, URTH)

**Use case examples:**

```python
from config import SYMBOL_CATEGORIES, US_EQUITIES, ETFS

# Run backtest on tech stocks only
tech_stocks = SYMBOL_CATEGORIES["tech"]

# Run backtest on all US equities
us_stocks = US_EQUITIES

# Run backtest on ETFs only
etf_list = ETFS
```

## 🔄 Backwards Compatibility

The root `config.py` file is maintained for backwards compatibility but is now just a thin wrapper:

```python
# Old way (still works)
from config import SYMBOLS, START_DATE

# New way (preferred)
from config import SYMBOLS, START_DATE
```

Both import methods work identically. The root config.py simply re-exports everything from the config module.

## ⚙️ How It Works

The config module uses a hierarchical import structure:

1. Individual config files define settings:
   - `symbols.py`, `portfolio.py`, `backtest.py`, `strategies.py`

2. `__init__.py` consolidates all imports:
   ```python
   from config.symbols import ACTIVE_SYMBOLS, SYMBOL_CATEGORIES
   from config.portfolio import INITIAL_CAPITAL, TRANSACTION_COST
   from config.backtest import START_DATE, STOP_DATE, BINNING
   from config.strategies import ACTIVE_PENGUINS
   ```

3. Root `config.py` re-exports for backwards compatibility:
   ```python
   from config import *
   ```

This structure:
- ✓ Separates concerns (symbols, portfolio, timing, strategies)
- ✓ Makes config changes easier to locate
- ✓ Maintains backwards compatibility
- ✓ Provides clear documentation per domain

## 🚀 Integration with Backtest

The backtest system automatically uses these config values:

```python
# In your code
from config import SYMBOLS, INITIAL_CAPITAL, START_DATE, ACTIVE_PENGUINS

# Backtest runner automatically uses these:
# - SYMBOLS: Which assets to trade
# - INITIAL_CAPITAL: Starting portfolio value
# - START_DATE/STOP_DATE: Simulation period
# - BINNING: Bar granularity
# - ACTIVE_PENGUINS: Which strategies to test
```

**No code changes needed** - just edit the config files and run:

```bash
python run_simulation.py
```

## 📝 Best Practices

### DO ✓

- Edit config files in `config/` folder
- Comment clearly when changing values
- Test configuration after changes:
  ```bash
  python -c "from config import *; print('Config OK!')"
  ```
- Keep `ACTIVE_SYMBOLS` reasonably sized (10-30 symbols for 1m bars)
- Use `BINNING = "5m"` or higher for faster backtests

### DON'T ✗

- Don't edit the root `config.py` directly (edit `config/` files instead)
- Don't mix timeframes in a single backtest
- Don't use "TODAY" for START_DATE (use a specific date instead)
- Don't add too many symbols with 1-minute bars (can be slow)

## 🔍 Validation

Validate your configuration:

```bash
# Check all imports
python -c "from config import *; print('✓ Config valid')"

# Check specific values
python -c "from config import SYMBOLS, START_DATE, STOP_DATE; print(f'{len(SYMBOLS)} symbols, {START_DATE} to {STOP_DATE}')"

# Check strategies
python -c "from config import ACTIVE_PENGUINS; print(f'{len(ACTIVE_PENGUINS)} strategies:', [p.__name__ for p in ACTIVE_PENGUINS])"
```

## 📚 Related Documentation

- Main README: `../README.md`
- Backtest documentation: `../backtest/BACKTEST_README.md`
- Market data: `../MARKET_DATA_README.md`
- Spread model: `../docs/SPREAD_MODEL_REFERENCE.md`

## 🛠️ Troubleshooting

### Import Errors

```
ImportError: cannot import name 'SYMBOLS' from 'config'
```

**Solution:** Ensure you're importing from `config`, not `config.py`:
```python
from config import SYMBOLS  # ✓ Correct
# not: from config.py import SYMBOLS  # ✗ Wrong
```

### Circular Import Errors

The new structure avoids circular imports. If you encounter one:
- Make sure you're importing from `config` module
- Check that you're not importing from the root `config.py` in config submodules

### Date Parsing Errors

```
ValueError: Cannot parse datetime: XYZ
```

**Solution:** Use ISO format dates:
```python
START_DATE = "2026-01-15 09:30:00"  # ✓ Correct
# not: START_DATE = "Jan 15, 2026"  # ✗ Wrong
```

### Strategy Not Running

If an active penguin isn't executing:
- Check `config/strategies.py` - is it commented out?
- Verify import path matches class name
- Check for typos in `ACTIVE_PENGUINS` list

## 📧 Support

For configuration issues:
1. Check this README
2. Validate config: `python -c "from config import *"`
3. Review error messages carefully
4. Check related documentation in `docs/`

---

**Last Updated:** March 9, 2026  
**Config Version:** 2.0 (Modular structure)
