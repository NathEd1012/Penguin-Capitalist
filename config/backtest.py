"""Backtest timing and execution configuration."""

import os

# ========== BACKTEST TIMING SETTINGS ==========

# Start date for backtest (ISO format: YYYY-MM-DD HH:MM:SS in UTC)
# Examples:
#   "2026-01-03 10:30:00"  - Specific datetime
#   "2026-01-03"           - Defaults to 00:00:00
START_DATE = "2026-01-01 0:00:00"

# Stop date for backtest
# Special keyword "TODAY" resolves to yesterday at 23:50 UTC 
# (to avoid Alpaca recent SIP data restrictions)
# Examples:
#   "TODAY"                - Use yesterday's end-of-day
#   "2026-02-03 21:30:00"  - Specific end datetime
STOP_DATE = "TODAY" #"2025-06-01 0:00:00" #"TODAY"

# ========== TIMEFRAME / BINNING ==========
# Candle interval for bars
# Supported values: "1m", "5m", "15m", "1h", "1d"
#   "1m"  - 1-minute bars (highest granularity, more data)
#   "5m"  - 5-minute bars
#   "15m" - 15-minute bars
#   "1h"  - 1-hour bars
#   "1d"  - Daily bars (lowest granularity, less data)
BINNING = "1m"

# ========== RUN ARCHIVING SETTINGS ==========
# Whether to save completed runs to run_old/ directory
# True  - Archive each run with timestamp (for historical comparison)
# False - Only update run_current/ (saves disk space)
SAVE_TO_RUN_OLD = int(os.getenv("SAVE_TO_RUN_OLD", "0"))

# ========== PORTFOLIO SETTINGS ==========
# Initial capital to start backtesting with (USD)
INITIAL_CAPITAL = 100000.0

# Transaction cost per trade (USD)
TRANSACTION_COST = 2.0

__all__ = [
    "START_DATE",
    "STOP_DATE",
    "BINNING",
    "SAVE_TO_RUN_OLD",
    "INITIAL_CAPITAL",
    "TRANSACTION_COST",
]
