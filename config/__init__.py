"""Configuration module for Penguin Capitalist.

This module consolidates all configuration settings from:
- config/symbols.py - Trading symbols and active list selection
- config/portfolio.py - Portfolio capital and transaction costs
- config/backtest.py - Backtest timing and execution settings
- config/strategies.py - Active trading strategies (penguins)

Import from this module anywhere in the codebase:
    from config import SYMBOLS, INITIAL_CAPITAL, START_DATE, ACTIVE_PENGUINS
"""

# ========== SYMBOL CONFIGURATION ==========
from config.symbols import (
    ACTIVE_SYMBOL_LIST,
    SYMBOL_LIST_1,
    SYMBOL_LIST_2,
    SYMBOL_LIST_3,
    SYMBOL_LISTS,
    ACTIVE_SYMBOLS,
    SYMBOLS_LIST,
    SYMBOLS,
)

# Keep alias explicit at package level for compatibility.
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
    EXTREMA_WINDOWS,
    FIT_PRE_SMOOTH_WINDOW,
    EXTREMA_CLUSTER_THRESHOLD_PCT,
    EXTREMA_MIN_TOUCHES,
    EXTREMA_MERGE_BAR_GAP,
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
    "ACTIVE_SYMBOL_LIST",   # Selected list key (LIST_1/LIST_2/LIST_3)
    "SYMBOL_LIST_1",        # Small-cap list
    "SYMBOL_LIST_2",        # Full list
    "SYMBOL_LIST_3",        # Custom list
    "SYMBOL_LISTS",         # Mapping of selectable lists
    "ACTIVE_SYMBOLS",       # Explicit active symbols
    "SYMBOLS_LIST",         # Alias
    "INITIAL_CAPITAL",      # Starting capital (USD)
    "TRANSACTION_COST",     # Cost per trade (USD)
    "START_DATE",           # Backtest start datetime
    "STOP_DATE",            # Backtest end datetime
    "BINNING",              # Timeframe ("1m", "5m", "15m", "1h", "1d")
    "SAVE_TO_RUN_OLD",      # Archive completed runs
    "ENABLE_ADDITIONAL_PLOTS",  # Toggle optional extra plots
    "EXTREMA_WINDOWS",      # Window widths for local-extrema fitting
    "FIT_PRE_SMOOTH_WINDOW",  # Optional pre-smooth window for fit exports
    "EXTREMA_CLUSTER_THRESHOLD_PCT",  # Extrema clustering tolerance
    "EXTREMA_MIN_TOUCHES",  # Minimum extrema touches for horizontal levels
    "EXTREMA_MERGE_BAR_GAP",  # Merge nearby extrema into one touch event
    "SMA_WINDOWS",          # Legacy alias for EXTREMA_WINDOWS
    "SMA_PRE_SMOOTH_WINDOW",  # Legacy alias for FIT_PRE_SMOOTH_WINDOW
    "SMA_EXTREMA_CLUSTER_THRESHOLD_PCT",  # Legacy alias for EXTREMA_CLUSTER_THRESHOLD_PCT
    "SMA_EXTREMA_MIN_TOUCHES",  # Legacy alias for EXTREMA_MIN_TOUCHES
    "SMA_EXTREMA_MERGE_BAR_GAP",  # Legacy alias for EXTREMA_MERGE_BAR_GAP
    "ACTIVE_PENGUINS",      # List of active strategy classes
    
]
