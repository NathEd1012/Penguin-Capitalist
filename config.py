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
]

"""
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
"""

INITIAL_CAPITAL = 5000.0
TRANSACTION_COST = 0
ENABLE_TRANSACTION_COSTS = True
ORDER_QTY = 1  # Quantity per order

# ========== TIMING SETTINGS ==========
BAR_TIMEFRAME_MINUTES = 1  # 1-minute bars
RUN_MINUTES = 320  # Total runtime (60 = 1 hour)

# ========== SIMULATION SETTINGS ==========
SIMULATION_MINUTES = 60  # For backtest (kept for compatibility)
USE_SYNTHETIC_DATA = True  # Use synthetic prices when Alpaca returns no data
FAST_MODE = True  # Skip real-time sleep, run as fast as possible

# ========== DATA QUALITY SETTINGS ==========
MAX_QUOTE_AGE_SEC = 60  # Reject quotes older than this while market is open
MAX_NO_UPDATE_MINUTES = 2  # Reject quotes unchanged for this many consecutive minutes

# ========== OUTPUT FILES ==========
import os
from datetime import datetime

# Create output directories if they don't exist
PLOTS_DIR = "plots"
RUN_CURRENT_DIR = "run_current"
os.makedirs(PLOTS_DIR, exist_ok=True)
os.makedirs(RUN_CURRENT_DIR, exist_ok=True)

# Run-current filenames (overwritten each run)
CAPITAL_CURVES_FILE = os.path.join(RUN_CURRENT_DIR, "capital_curves.png")
TRADES_LOG_FILE = os.path.join(RUN_CURRENT_DIR, "trades_log.txt")
CURVES_DATA_FILE = os.path.join(RUN_CURRENT_DIR, "curves_data.json")

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
    # BreakoutPenguin,
    CarefulTrendPenguin,
    CopilotPenguin,
    # MeanReversionPenguin,
    # MomentumPenguin,
    MovingAverageCrossoverPenguin,
    # RandomPenguin,
    # RandomPenguin2,
    RSIMeanReversionPenguin,
    SMA20MultiTimeframePenguin,
    SupportResistancePenguin,
    # TrendPenguin,
    # VolatilityBreakoutPenguin,
]
##
