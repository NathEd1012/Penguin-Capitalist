"""Configuration module for Penguin Capitalist.

This module consolidates all configuration settings from:
- config/symbols.py - Trading symbols and symbol categories
- config/portfolio.py - Portfolio capital and transaction costs
- config/backtest.py - Backtest timing and execution settings
- config/strategies.py - Active trading strategies (penguins)

Import from this module anywhere in the codebase:
    from config import SYMBOLS, INITIAL_CAPITAL, START_DATE, ACTIVE_PENGUINS
"""

# ========== SYMBOL CONFIGURATION ==========
from config.symbols import (
    ACTIVE_SYMBOLS,
    SYMBOLS_LIST,
    SYMBOL_CATEGORIES,
    SYMBOLS,  # Alias for SYMBOL_CATEGORIES
    ALL_SYMBOLS,
    US_EQUITIES,
    INTERNATIONAL_EQUITIES,
    ETFS,
)

# Legacy alias: SYMBOLS refers to the active list for backtesting
# Override the dict from symbols.py with the active list for compatibility
SYMBOLS = ACTIVE_SYMBOLS

# ========== PORTFOLIO CONFIGURATION ==========
from config.portfolio import (
    INITIAL_CAPITAL,
    TRANSACTION_COST,
)

# ========== BACKTEST CONFIGURATION ==========
from config.backtest import (
    START_DATE,
    STOP_DATE,
    BINNING,
    SAVE_TO_RUN_OLD,
    ENABLE_ADDITIONAL_PLOTS,
    SMA_WINDOWS,
    SMA_PRE_SMOOTH_WINDOW,
    SMA_EXTREMA_CLUSTER_THRESHOLD_PCT,
    SMA_EXTREMA_MIN_TOUCHES,
    SMA_EXTREMA_MERGE_BAR_GAP,
)

# ========== STRATEGY CONFIGURATION ==========
from config.strategies import (
    ACTIVE_PENGUINS,
)

# ========== EXPORTS ==========
__all__ = [
    # Active trading configuration
    "SYMBOLS",              # Active symbols list for backtesting
    "ACTIVE_SYMBOLS",       # Explicit active symbols
    "SYMBOLS_LIST",         # Alias
    "INITIAL_CAPITAL",      # Starting capital (USD)
    "TRANSACTION_COST",     # Cost per trade (USD)
    "START_DATE",           # Backtest start datetime
    "STOP_DATE",            # Backtest end datetime
    "BINNING",              # Timeframe ("1m", "5m", "15m", "1h", "1d")
    "SAVE_TO_RUN_OLD",      # Archive completed runs
    "ENABLE_ADDITIONAL_PLOTS",  # Toggle optional extra plots
    "SMA_WINDOWS",          # SMA windows exported for each symbol
    "SMA_PRE_SMOOTH_WINDOW",  # Pre-smoothing window applied before SMA_WINDOWS
    "SMA_EXTREMA_CLUSTER_THRESHOLD_PCT",  # SMA extrema clustering tolerance
    "SMA_EXTREMA_MIN_TOUCHES",  # Minimum extrema touches for horizontal levels
    "SMA_EXTREMA_MERGE_BAR_GAP",  # Merge nearby extrema into one touch event
    "ACTIVE_PENGUINS",      # List of active strategy classes
    
    # Symbol categorization
    "SYMBOL_CATEGORIES",    # Dict of symbol categories
    "ALL_SYMBOLS",          # All available symbols flattened
    "US_EQUITIES",          # US equity symbols
    "INTERNATIONAL_EQUITIES",  # International equity symbols
    "ETFS",                 # ETF symbols
]
