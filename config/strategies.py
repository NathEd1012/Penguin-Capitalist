"""Active trading strategy (penguin) configuration."""

# Import all available penguin strategies
from penguins import (
    SP500,
    RSIMeanReversionPenguin,
    RSIMeanReversionPenguinStrict1,
    RSIMeanReversionPenguinStrict2,
)

# ========== ACTIVE PENGUINS ==========
# List of penguin strategy classes to run in the backtest
# Comment out strategies you don't want to run
# Each strategy will be tested in parallel on the same data

ACTIVE_PENGUINS = [
    SP500,                              # Buy & hold S&P 500 ETF benchmark (SPY)
    RSIMeanReversionPenguin,            # Baseline RSI Mean Reversion
    RSIMeanReversionPenguinStrict1,     # Strict RSI with crossing + cooldown
    RSIMeanReversionPenguinStrict2,     # Very strict RSI with longer cooldown
]

__all__ = [
    "ACTIVE_PENGUINS",
]
