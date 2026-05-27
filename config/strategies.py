"""Active trading strategy (penguin) configuration."""

# Import all available penguin strategies
from penguins import (
    CopilotPenguin,
    SP500,
    SP500x2,
    RSIMeanReversionSelectivePenguin,
    SmartRSIConfluencePenguin,
    BuyOneEachPenguin,
    BuyMaxEachPenguin,
    BuyEqualPriceEachPenguin,
)
# from penguins.multitimeframe_reaction_sr_penguin import MultitimeframeReactionSRPenguin

# ========== ACTIVE PENGUINS ==========
# List of penguin strategy classes to run in the backtest
# Comment out strategies you don't want to run
# Each strategy will be tested in parallel on the same data

ACTIVE_PENGUINS = [
    SP500,                              # Buy & hold S&P 500 ETF benchmark (SPY)
    SP500x2,                            # Buy & hold 2x leveraged S&P 500 ETF (SSO)
    #RSIMeanReversionPenguin,            # Baseline RSI Mean Reversion
    # RSIMeanReversionPenguinStrict1,     # RSI Mean Reversion variant 1
    # RSIMeanReversionPenguinStrict2,     # RSI Mean Reversion variant 2
    #RSIMeanReversionReducedPenguin,     # Adaptive RSI - targets 1-10 trades/day (LIST 2 symbols)
    #RSIMeanReversionMomentumPenguin,    # 3-stage momentum RSI - RISING/FALLING/HOLDING
    #RSIMeanReversionSelectivePenguin,   # Low-frequency high-quality RSI mean reversion
    SmartRSIConfluencePenguin,          # RSI + trend + momentum confluence strategy
    BuyOneEachPenguin,                  # Buy exactly 1 share for each symbol once
    BuyMaxEachPenguin,                  # Buy the same maximum share count for each symbol once
    BuyEqualPriceEachPenguin,         # Buy an equal dollar amount of each symbol once

    CopilotPenguin,                    # AI-assisted strategy
    #MomentumPenguin,                  # Pure momentum following
    # MinMaxSRPenguin,                  # Single timeframe S/R
    # SRMultiframePenguin,              # Multiframe S/R placeholder
    # MultitimeframeReactionSRPenguin,  # Multi-TF reaction S/R
    # SMA20Penguin,                     # SMA crossover
    # SMA20AdvancedPenguin,             # SMA crossover with sizing
]

__all__ = [
    "ACTIVE_PENGUINS",
]
