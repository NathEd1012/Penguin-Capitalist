"""Configuration module for Penguin Capitalist.

This module consolidates all configuration settings from:
- config/symbols.py - Trading symbols and active list selection
- config/backtest.py - Backtest timing, portfolio capital, and execution settings
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
    SYMBOL_LIST_4,
    SYMBOL_LISTS,
    ACTIVE_SYMBOLS,
    SYMBOLS_LIST,
    SYMBOLS,
)

# Keep alias explicit at package level for compatibility.
SYMBOLS = ACTIVE_SYMBOLS

# ========== BACKTEST CONFIGURATION ==========
from config.backtest import (
    START_DATE,
    STOP_DATE,
    BINNING,
    SAVE_TO_RUN_OLD,
    INITIAL_CAPITAL,
    EXEC_TRANSACTION_COST,
)

# ========== STRATEGY CONFIGURATION ==========
from config.strategies import (
    ACTIVE_PENGUINS,
)

# ========== TRAINING STEP CONFIGURATION ==========
from config.training_step import (
    TRAINING_STEP_ENABLED,
    TRAINING_ITERATIONS,
    TRAINING_SUBSET_MONTHS,
    TRAINING_SUBSET_STOCKS,
    TRAINING_RELATIVE_TO,
    TRAINING_RANDOM_SEED,
    DIFFERENT_TRAINING_TIME,
    TRAINING_START_DATE,
    TRAINING_STOP_DATE,
    Manual,
    TRAINING_PENGUINS as TRAINABLE_PENGUINS,
    TRAINING_MANUAL_PENGUINS,
    TRAINING_RESULTS_FILENAME,
    TRAINING_LOG_FILENAME,
    TRAINING_PARAMETER_LOG_FILENAME,
    TRAINING_PARAMETER_DELTA_FILENAME,
    TRAINING_TRANSACTION_COST,
    PLOT_PARETO,
    TRAINING_PARETO_FILENAME,
)

# ========== EXPORTS ==========
__all__ = [
    # Active trading configuration
    "SYMBOLS",              # Active symbols list for backtesting
    "ACTIVE_SYMBOL_LIST",   # Selected list key (LIST_1/LIST_2/LIST_3/LIST_4)
    "SYMBOL_LIST_1",        # Small-cap list
    "SYMBOL_LIST_2",        # Full list
    "SYMBOL_LIST_3",        # Custom list
    "SYMBOL_LIST_4",        # Expanded universe list
    "SYMBOL_LISTS",         # Mapping of selectable lists
    "ACTIVE_SYMBOLS",       # Explicit active symbols
    "SYMBOLS_LIST",         # Alias
    "INITIAL_CAPITAL",      # Starting capital (USD)
    "EXEC_TRANSACTION_COST",     # Cost per trade (USD)
    "START_DATE",           # Backtest start datetime
    "STOP_DATE",            # Backtest end datetime
    "BINNING",              # Timeframe ("1m", "5m", "15m", "1h", "1d")
    "SAVE_TO_RUN_OLD",      # Archive completed runs
    "ACTIVE_PENGUINS",      # List of active strategy classes
    "TRAINING_STEP_ENABLED",
    "TRAINING_ITERATIONS",
    "TRAINING_SUBSET_MONTHS",
    "TRAINING_SUBSET_STOCKS",
    "TRAINING_RELATIVE_TO",
    "TRAINING_RANDOM_SEED",
    "DIFFERENT_TRAINING_TIME",
    "TRAINING_START_DATE",
    "TRAINING_STOP_DATE",
    "Manual",
    "TRAINABLE_PENGUINS",
    "TRAINING_MANUAL_PENGUINS",
    "TRAINING_RESULTS_FILENAME",
    "TRAINING_LOG_FILENAME",
    "TRAINING_PARAMETER_LOG_FILENAME",
    "TRAINING_PARAMETER_DELTA_FILENAME",
    "TRAINING_TRANSACTION_COST",
    "PLOT_PARETO",
    "TRAINING_PARETO_FILENAME",
    "EXEC_TRANSACTION_COST",
    
]
