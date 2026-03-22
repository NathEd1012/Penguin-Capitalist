"""Backtest timing and execution configuration."""

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
STOP_DATE = "TODAY"

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
SAVE_TO_RUN_OLD = 1 #False

# ========== OPTIONAL ADDITIONAL PLOTS ==========
# Controls extra visualization outputs like multitimeframe S/R line PNGs + combined PDF.
# True  - Generate additional plot folders and a combined PDF
# False - Skip all additional plotting
ENABLE_ADDITIONAL_PLOTS = 1

__all__ = [
    "START_DATE",
    "STOP_DATE",
    "BINNING",
    "SAVE_TO_RUN_OLD",
    "ENABLE_ADDITIONAL_PLOTS",
]
