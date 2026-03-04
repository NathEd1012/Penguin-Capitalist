# ========== TRADING SYMBOLS ==========
SYMBOLS = [
    "NVDA",
    "AAPL",
    "PLTR",
    "AMD",
    #"BE",
    "MP",
    "MSTR",
    "MSFT",
    "TSLA",
    "NOC",
    "LMT",
    "NVO",

    # --- ETFs / Commodity ETFs ---
    "GLD",  # Gold
    "SLV",  # Silver
    "PPLT",  # Platinum
    "COPX",  # Copper miners
    "JO",  # Coffee
    "LIT",  # Lithium & Battery Tech
    "URTH",  # MSCI World
    "GDXJ",  # Junior gold miners
    "SIL",  # Silver miners
    "REMX",  # Rare earth / critical metals
    "PICK",  # Global metals & mining
]

INITIAL_CAPITAL = 5000.0
TRANSACTION_COST = 0

# ========== BACKTEST TIMING SETTINGS ==========
# ISO format dates (YYYY-MM-DD HH:MM:SS in UTC or market timezone)
START_DATE = "2026-01-17 14:30:00"  # Feb 20, 2026 at 2:30 PM UTC (9:30 AM EST)
STOP_DATE = "TODAY" #"2026-03-01 23:50:00"   # Feb 21, 2026 at 11:50 PM UTC (market close + after hours)

# Binning/timeframe for bars: "1m", "5m", "15m", "1h", "1d", etc.
BINNING = "1m"

# ========== RUN ARCHIVING SETTINGS ==========
# Whether to save runs to run_old directory (set False to only update run_current)
SAVE_TO_RUN_OLD = False

# ========== ACTIVE PENGUINS ==========
from penguins import (
    BreakoutPenguin,
    CarefulTrendPenguin,
    CopilotPenguin,
    MeanReversionPenguin,
    MovingAverageCrossoverPenguin,
    MomentumPenguin,
    RandomPenguin,
    RandomPenguin2,
    RSIMeanReversionPenguin,
    SMA20MultiTimeframePenguin,
    SupportResistancePenguin,
    TrendPenguin,
    VolatilityBreakoutPenguin,
)

ACTIVE_PENGUINS = [
    #BreakoutPenguin,
    #CarefulTrendPenguin,
    CopilotPenguin,
    #MeanReversionPenguin,
    #MomentumPenguin,
    #MovingAverageCrossoverPenguin,
    #RandomPenguin,
    #RandomPenguin2,
    #RSIMeanReversionPenguin,
    SMA20MultiTimeframePenguin,
    SupportResistancePenguin,
    #TrendPenguin,
    #VolatilityBreakoutPenguin,
]
##
