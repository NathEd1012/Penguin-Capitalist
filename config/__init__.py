"""Configuration module for Penguin Capitalist."""
import importlib.util
from pathlib import Path

# Load root config.py as a module to avoid circular import
root_config_path = Path(__file__).resolve().parent.parent / "config.py"
spec = importlib.util.spec_from_file_location("root_config", root_config_path)
root_config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(root_config)

# Re-export all config constants from root config.py
SYMBOLS = root_config.SYMBOLS
INITIAL_CAPITAL = root_config.INITIAL_CAPITAL
TRANSACTION_COST = root_config.TRANSACTION_COST
START_DATE = root_config.START_DATE
STOP_DATE = root_config.STOP_DATE
BINNING = root_config.BINNING
SAVE_TO_RUN_OLD = root_config.SAVE_TO_RUN_OLD
ACTIVE_PENGUINS = root_config.ACTIVE_PENGUINS

# Also export symbol categories from config/symbols.py
from config.symbols import (
    ALL_SYMBOLS,
    US_EQUITIES,
    INTERNATIONAL_EQUITIES,
    ETFS,
)

__all__ = [
    "SYMBOLS",
    "INITIAL_CAPITAL",
    "TRANSACTION_COST",
    "START_DATE",
    "STOP_DATE",
    "BINNING",
    "SAVE_TO_RUN_OLD",
    "ACTIVE_PENGUINS",
    "ALL_SYMBOLS",
    "US_EQUITIES",
    "INTERNATIONAL_EQUITIES",
    "ETFS",
]
