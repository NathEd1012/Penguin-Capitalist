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
    # --- ETFs / Commodity ETFs -
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
ENABLE_TRANSACTION_COSTS = True
ORDER_QTY = 1  # Quantity per order

# ========== TIMING SETTINGS ==========
BAR_TIMEFRAME_MINUTES = 1  # 1-minute bars
RUN_MINUTES = 300  # Total runtime (60 = 1 hour)

# ========== SIMULATION SETTINGS ==========
SIMULATION_MINUTES = 60  # For backtest (kept for compatibility)
USE_SYNTHETIC_DATA = True  # Use synthetic prices when Alpaca returns no data
FAST_MODE = True  # Skip real-time sleep, run as fast as possible

# ========== OUTPUT FILES ==========
import os
from datetime import datetime

# Create run_current directory if it doesn't exist
CURRENT_RUN_DIR = "run_current"
os.makedirs(CURRENT_RUN_DIR, exist_ok=True)

# Fixed filenames (no timestamp, gets overwritten each run)
CAPITAL_CURVES_FILE = os.path.join(CURRENT_RUN_DIR, "capital_curves.png")
TRADES_LOG_FILE = os.path.join(CURRENT_RUN_DIR, "trades.txt")
CURVES_DATA_FILE = os.path.join(CURRENT_RUN_DIR, "data.json")
