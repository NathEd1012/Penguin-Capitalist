"""Backtest timing and execution configuration."""

import os

# ========== BACKTEST TIMING SETTINGS ==========

# Start date for backtest (ISO format: YYYY-MM-DD HH:MM:SS in UTC)
# Examples:
#   "2026-01-03 10:30:00"  - Specific datetime
#   "2026-01-03"           - Defaults to 00:00:00
START_DATE = "2024-01-01 0:00:00"

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

# ========== OPTIONAL ADDITIONAL PLOTS ==========
# Controls extra visualization outputs like multitimeframe S/R line PNGs + combined PDF.
# True  - Generate additional plot folders and a combined PDF
# False - Skip all additional plotting
ENABLE_ADDITIONAL_PLOTS = 0

# ========== EXTREMA FIT SETTINGS ==========
# Centered window widths used for local-extrema based fit extraction.
EXTREMA_WINDOWS = [50]

# Optional pre-smoothing window for exports that still use centered-mean helpers.
FIT_PRE_SMOOTH_WINDOW = 20

# Price clustering threshold used to group repeated extrema touches.
EXTREMA_CLUSTER_THRESHOLD_PCT = 0.004  # 0.4%

# Minimum number of extrema in a cluster to draw a horizontal level.
EXTREMA_MIN_TOUCHES = 3

# Nearby extrema within this many bars are merged into one touch event.
EXTREMA_MERGE_BAR_GAP = 5

# Backward-compatible aliases for older code paths.
SMA_WINDOWS = EXTREMA_WINDOWS
SMA_PRE_SMOOTH_WINDOW = FIT_PRE_SMOOTH_WINDOW
SMA_EXTREMA_CLUSTER_THRESHOLD_PCT = EXTREMA_CLUSTER_THRESHOLD_PCT
SMA_EXTREMA_MIN_TOUCHES = EXTREMA_MIN_TOUCHES
SMA_EXTREMA_MERGE_BAR_GAP = EXTREMA_MERGE_BAR_GAP

__all__ = [
    "START_DATE",
    "STOP_DATE",
    "BINNING",
    "SAVE_TO_RUN_OLD",
    "ENABLE_ADDITIONAL_PLOTS",
    "EXTREMA_WINDOWS",
    "FIT_PRE_SMOOTH_WINDOW",
    "EXTREMA_CLUSTER_THRESHOLD_PCT",
    "EXTREMA_MIN_TOUCHES",
    "EXTREMA_MERGE_BAR_GAP",
    "SMA_WINDOWS",
    "SMA_PRE_SMOOTH_WINDOW",
    "SMA_EXTREMA_CLUSTER_THRESHOLD_PCT",
    "SMA_EXTREMA_MIN_TOUCHES",
    "SMA_EXTREMA_MERGE_BAR_GAP",
]
