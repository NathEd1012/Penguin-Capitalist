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

# Create plots directory if it doesn't exist
PLOTS_DIR = "plots"
os.makedirs(PLOTS_DIR, exist_ok=True)

# Create logs directory if it doesn't exist
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

# Dynamic filenames with date/time
now = datetime.now()
rounded_minute = round(now.minute / 10) * 10
if rounded_minute == 60:
    now = now.replace(hour=now.hour + 1, minute=0, second=0)
else:
    now = now.replace(minute=rounded_minute, second=0)
timestamp = now.strftime("%y%m%d_%H%M")
CAPITAL_CURVES_FILE = os.path.join(PLOTS_DIR, f"capital_{timestamp}.png")
TRADES_LOG_FILE = os.path.join(LOGS_DIR, f"trades_{timestamp}.txt")
CURVES_DATA_FILE = os.path.join(LOGS_DIR, f"data_{timestamp}.json")
