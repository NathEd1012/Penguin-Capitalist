"""Trading symbol configuration for backtesting.

This module contains:
1. ACTIVE_SYMBOLS - The current list of symbols used for backtesting
2. SYMBOL_CATEGORIES - Organized categorization of available symbols
3. Helper lists for different market segments
"""

# ========== ACTIVE SYMBOLS FOR BACKTESTING ==========
# This is the primary list used by the backtest engine
# Choose active list by changing just this variable:
# "LIST_1" | "LIST_2" | "LIST_3"
ACTIVE_SYMBOL_LIST = "LIST_2"

# List 1: 5 large-cap stocks
SYMBOL_LIST_1 = [
    "NVDA",   # Nvidia
    "AAPL",   # Apple
    "MSFT",   # Microsoft
    "AMZN",   # Amazon
    "TSLA",   # Tesla
]

# List 2: current full ticker set (previous ACTIVE_SYMBOLS)
SYMBOL_LIST_2 = [
    # Tech giants & growth
    "SPY",    # S&P 500 ETF benchmark
    "NVDA",   # Nvidia
    "AAPL",   # Apple
    "PLTR",   # Palantir
    "AMD",    # Advanced Micro Devices
    "MSTR",   # MicroStrategy (Bitcoin proxy)
    "MSFT",   # Microsoft
    "TSLA",   # Tesla

    # Materials & Mining
    "MP",     # MP Materials (rare earths)

    # Defense
    "NOC",    # Northrop Grumman
    "LMT",    # Lockheed Martin

    # International
    "NVO",    # Novo Nordisk (Denmark)

    # --- ETFs / Commodity ETFs ---
    "GLD",    # Gold
    "SLV",    # Silver
    "PPLT",   # Platinum
    "COPX",   # Copper miners
    "JO",     # Coffee
    "LIT",    # Lithium & Battery Tech
    "URTH",   # MSCI World
    "GDXJ",   # Junior gold miners
    "SIL",    # Silver miners
    "REMX",   # Rare earth / critical metals
    "PICK",   # Global metals & mining
]

# List 3: intentionally empty for custom manual additions
SYMBOL_LIST_3 = []

SYMBOL_LISTS = {
    "LIST_1": SYMBOL_LIST_1,
    "LIST_2": SYMBOL_LIST_2,
    "LIST_3": SYMBOL_LIST_3,
}

if ACTIVE_SYMBOL_LIST not in SYMBOL_LISTS:
    raise ValueError(
        f"Unknown ACTIVE_SYMBOL_LIST='{ACTIVE_SYMBOL_LIST}'. "
        f"Use one of: {', '.join(SYMBOL_LISTS.keys())}."
    )

ACTIVE_SYMBOLS = SYMBOL_LISTS[ACTIVE_SYMBOL_LIST]

# Legacy alias for compatibility
SYMBOLS_LIST = ACTIVE_SYMBOLS

# Backwards compatibility alias: keep SYMBOLS as active trading list.
SYMBOLS = ACTIVE_SYMBOLS

__all__ = [
    "ACTIVE_SYMBOL_LIST",
    "SYMBOL_LIST_1",
    "SYMBOL_LIST_2",
    "SYMBOL_LIST_3",
    "SYMBOL_LISTS",
    "ACTIVE_SYMBOLS",
    "SYMBOLS_LIST",
    "SYMBOLS",  # Alias for backwards compatibility
]
