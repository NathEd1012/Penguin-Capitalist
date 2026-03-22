"""Active trading strategy (penguin) configuration."""

# Import all available penguin strategies
from penguins import (
    CopilotPenguin,
    MeanReversionPenguin,
    MultitimeframeRangeSRPenguin,
    MultitimeframeReactionSRPenguin,
    MinMaxSRPenguin,
    MomentumPenguin,
    SP500Penguin,
    RSIMeanReversionPenguin,
    SMA20AdvancedPenguin,
    SMA20Penguin,
)

# ========== ACTIVE PENGUINS ==========
# List of penguin strategy classes to run in the backtest
# Comment out strategies you don't want to run
# Each strategy will be tested in parallel on the same data

ACTIVE_PENGUINS = [
    MultitimeframeRangeSRPenguin,      # Multi-TF range-based S/R
    MultitimeframeReactionSRPenguin,   # Multi-TF reaction-based S/R
    SP500Penguin,                      # Buy & hold S&P 500 ETF benchmark (SPY)
]

__all__ = [
    "ACTIVE_PENGUINS",
]
