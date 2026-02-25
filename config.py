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
START_DATE = "2026-02-17 14:30:00"  # Feb 20, 2026 at 2:30 PM UTC (9:30 AM EST)
STOP_DATE = "2026-02-21 23:50:00"   # Feb 21, 2026 at 11:50 PM UTC (market close + after hours)

# Binning/timeframe for bars: "1m", "5m", "15m", "1h", "1d", etc.
BINNING = "1m"

# ========== ACTIVE PENGUINS ==========
from penguins import (
    BreakoutPenguin,
    CarefulTrendPenguin,
    CopilotPenguin,
    MeanReversionPenguin,
    MomentumPenguin,
    RandomPenguin,
    RandomPenguin2,
    SupportResistancePenguin,
    TrendPenguin,
)
from penguins.moving_average_crossover_penguin import MovingAverageCrossoverPenguin
from penguins.rsi_mean_reversion_penguin import RSIMeanReversionPenguin
from penguins.volatility_breakout_penguin import VolatilityBreakoutPenguin
from penguins.sma20_multitimeframe_penguin import SMA20MultiTimeframePenguin

ACTIVE_PENGUINS = [
    #BreakoutPenguin,
    #CarefulTrendPenguin,
    CopilotPenguin,
    #MeanReversionPenguin,
    #MomentumPenguin,
    #MovingAverageCrossoverPenguin,
    #RandomPenguin,
    #RandomPenguin2,
    RSIMeanReversionPenguin,
    SMA20MultiTimeframePenguin,
    SupportResistancePenguin,
    #TrendPenguin,
    #VolatilityBreakoutPenguin,
]
##
