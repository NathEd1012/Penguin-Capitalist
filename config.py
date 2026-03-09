"""Root configuration file for Penguin Capitalist.

⚠️  DEPRECATED: This file is maintained for backwards compatibility only.
    All configuration is now in the config/ folder:
    
    - config/symbols.py     - Trading symbols and categories
    - config/portfolio.py   - Portfolio capital and costs
    - config/backtest.py    - Backtest timing and execution
    - config/strategies.py  - Active trading strategies
    
    Please import from 'config' module instead:
        from config import SYMBOLS, INITIAL_CAPITAL, START_DATE, ACTIVE_PENGUINS
"""

# Re-export everything from the config module for backwards compatibility
from config import (
    # Active configuration
    SYMBOLS,
    ACTIVE_SYMBOLS,
    SYMBOLS_LIST,
    INITIAL_CAPITAL,
    TRANSACTION_COST,
    START_DATE,
    STOP_DATE,
    BINNING,
    SAVE_TO_RUN_OLD,
    ACTIVE_PENGUINS,
    
    # Symbol categorization
    SYMBOL_CATEGORIES,
    ALL_SYMBOLS,
    US_EQUITIES,
    INTERNATIONAL_EQUITIES,
    ETFS,
)

__all__ = [
    "SYMBOLS",
    "ACTIVE_SYMBOLS",
    "SYMBOLS_LIST",
    "INITIAL_CAPITAL",
    "TRANSACTION_COST",
    "START_DATE",
    "STOP_DATE",
    "BINNING",
    "SAVE_TO_RUN_OLD",
    "ACTIVE_PENGUINS",
    "SYMBOL_CATEGORIES",
    "ALL_SYMBOLS",
    "US_EQUITIES",
    "INTERNATIONAL_EQUITIES",
    "ETFS",
]
