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
RUN_MINUTES = 15  # 50  # Total runtime (60 = 1 hour)

# ========== SIMULATION SETTINGS ==========
SIMULATION_MINUTES = 60  # For backtest (kept for compatibility)
USE_SYNTHETIC_DATA = True  # Use synthetic prices when Alpaca returns no data
FAST_MODE = True  # Skip real-time sleep, run as fast as possible

# ========== OUTPUT FILES ==========
import os
from datetime import datetime

# Create plots directory if it doesn't exist
PLOTS_DIR = "plots"
os.makedirs(PLOTS_DIR, exist_ok=True)

# Dynamic filenames with date/time
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
CAPITAL_CURVES_FILE = os.path.join(PLOTS_DIR, f"capital_curves_{timestamp}.png")
TRADES_LOG_FILE = f"trades_log_{timestamp}.txt"
