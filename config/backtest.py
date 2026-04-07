"""In-time simulation and plotting configuration."""

# ========== IN-TIME SIMULATION SETTINGS ==========
# This branch runs time-based simulation loops (minutes), not date-ranged backtests.

BAR_TIMEFRAME_MINUTES = 1
RUN_MINUTES = 180
SIMULATION_MINUTES = RUN_MINUTES

# Use synthetic fallback prices when quote/bar fetch fails.
USE_SYNTHETIC_DATA = True

# When True, loop can skip real-time sleeping (if used by runner logic).
FAST_MODE = True

# Legacy keys kept for compatibility with older modules/docs.
START_DATE = None
STOP_DATE = None
BINNING = "1m"

# ========== RUN ARCHIVING SETTINGS ==========
# Whether to save completed runs to run_old/ directory
# True  - Archive each run with timestamp (for historical comparison)
# False - Only update run_current/ (saves disk space)
SAVE_TO_RUN_OLD = 0 #False

# ========== OPTIONAL ADDITIONAL PLOTS ==========
# Controls extra visualization outputs like multitimeframe S/R line PNGs + combined PDF.
# True  - Generate additional plot folders and a combined PDF
# False - Skip all additional plotting
ENABLE_ADDITIONAL_PLOTS = 1

# ========== SMA EXPORT SETTINGS ==========
# Simple moving-average windows to compute for each symbol and export per run.
SMA_WINDOWS = [200, 500]

# Pre-smooth raw price with this SMA window before computing SMA_WINDOWS.
SMA_PRE_SMOOTH_WINDOW = 50

# Price clustering threshold used to group many SMA extrema around similar levels.
SMA_EXTREMA_CLUSTER_THRESHOLD_PCT = 0.002  # 0.2%

# Minimum number of extrema in a cluster to draw a horizontal level.
SMA_EXTREMA_MIN_TOUCHES = 3

# Nearby extrema within this many bars are merged into one touch event.
SMA_EXTREMA_MERGE_BAR_GAP = 5

__all__ = [
    "BAR_TIMEFRAME_MINUTES",
    "RUN_MINUTES",
    "SIMULATION_MINUTES",
    "USE_SYNTHETIC_DATA",
    "FAST_MODE",
    "START_DATE",
    "STOP_DATE",
    "BINNING",
    "SAVE_TO_RUN_OLD",
    "ENABLE_ADDITIONAL_PLOTS",
    "SMA_WINDOWS",
    "SMA_PRE_SMOOTH_WINDOW",
    "SMA_EXTREMA_CLUSTER_THRESHOLD_PCT",
    "SMA_EXTREMA_MIN_TOUCHES",
    "SMA_EXTREMA_MERGE_BAR_GAP",
]
