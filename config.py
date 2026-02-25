# ========== TRADING SYMBOLS ==========
SYMBOLS = [
    "NVDA",
    "AAPL",
    "PLTR",
    "AMD",
    "BE",
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

# ========== TIMING SETTINGS ==========
BAR_TIMEFRAME_MINUTES = 1  # 1-minute bars

# ========== BACKTEST SETTINGS ==========
Run_start = 202602201400  # Start time: Feb 20, 2026 at 2:00 PM CET (YYYYMMDD_HHMM as integer)
NUM_BARS_TO_BACKTEST = 180  # Number of bars to simulate (e.g., 180 = 3 hours of 1-min bars)

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
    #SupportResistancePenguin,
    #TrendPenguin,
    #VolatilityBreakoutPenguin,
]
##
