"""Active trading strategy (penguin) configuration."""

# Import all available penguin strategies
from penguins import (
    CopilotPenguin,
    MomentumPenguin,
    MinMaxSRPenguin,
    SRMultiframePenguin,
    SMA20Penguin,
    SMA20AdvancedPenguin,
    SP500,
    RSIMeanReversionPenguin,
    RSIMeanReversionPenguinStrict1,
    RSIMeanReversionPenguinStrict2,
    RSIMeanReversionAdvancedPenguin,
)
from penguins.multitimeframe_reaction_sr_penguin import MultitimeframeReactionSRPenguin

# ========== ACTIVE PENGUINS ==========
# List of penguin strategy classes to run in the backtest
# Comment out strategies you don't want to run
# Each strategy will be tested in parallel on the same data

ACTIVE_PENGUINS = [
    SP500,                              # Buy & hold S&P 500 ETF benchmark (SPY)
    RSIMeanReversionPenguin,            # Baseline RSI Mean Reversion
    RSIMeanReversionPenguinStrict1,     # RSI Mean Reversion variant 1
    RSIMeanReversionPenguinStrict2,     # RSI Mean Reversion variant 2

    # CopilotPenguin,                   # AI-assisted strategy
    # MomentumPenguin,                  # Pure momentum following
    # MinMaxSRPenguin,                  # Single timeframe S/R
    # SRMultiframePenguin,              # Multiframe S/R placeholder
    # MultitimeframeReactionSRPenguin,  # Multi-TF reaction S/R
    # SMA20Penguin,                     # SMA crossover
    # SMA20AdvancedPenguin,             # SMA crossover with sizing
    # RSIMeanReversionAdvancedPenguin,  # Advanced RSI mean reversion
]

__all__ = [
    "ACTIVE_PENGUINS",
]
