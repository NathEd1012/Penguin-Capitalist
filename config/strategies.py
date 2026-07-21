"""Active trading strategy (penguin) configuration."""

# Import all available penguin strategies
from penguins import (
    CopilotPenguin,
    SP500,
    SP500x2,
    TrainablePenguin1,
    TrainablePenguin1_Manual,
    TrainablePenguin2,
    TrainablePenguin2_Manual,
    TrainablePenguin3,
    TrainablePenguin3_Manual,
    TrainablePenguin4,
    TrainablePenguin4_Manual,
    TrainablePenguin5,
    TrainablePenguin5_Manual,
    RSIMeanReversionSelectivePenguin,
    RSIConfluencePenguin,
    BuyOneEachPenguin,
    BuyMaxEachPenguin,
    BuyEqualPriceEachPenguin,
)

from penguins.ThreeFold_MeanRev_Peng import ThreeFoldMeanReversionTrendPenguin

# from penguins.multitimeframe_reaction_sr_penguin import MultitimeframeReactionSRPenguin

# ========== ACTIVE PENGUINS ==========
# List of penguin strategy classes to run in the backtest
# Comment out strategies you don't want to run
# Each strategy will be tested in parallel on the same data

ACTIVE_PENGUINS = [
    TrainablePenguin1,                  # RSI/trend buy; volume-explosion sell
    TrainablePenguin1_Manual,           # Hand-tuned variant of TrainablePenguin1
    TrainablePenguin2,                  # Bollinger/ADX buy; volume-explosion sell
    TrainablePenguin2_Manual,           # Hand-tuned variant of TrainablePenguin2
    TrainablePenguin3,                  # Bollinger/ADX buy; Stock/SPY RS sell
    TrainablePenguin3_Manual,           # Manual variant of TP3
    TrainablePenguin4,                  # RSI/trend buy; Stock/SPY RS sell
    TrainablePenguin4_Manual,           # Manual variant of TP4
    TrainablePenguin5,                  # TP1-style refined entry/exit with minimum hold
    TrainablePenguin5_Manual,           # Hand-tuned variant of TrainablePenguin5

    SP500,                              # Buy & hold S&P 500 ETF benchmark (SPY)
    #SP500x2,                            # Buy & hold 2x leveraged S&P 500 ETF (SSO)
    #RSIMeanReversionPenguin,            # Baseline RSI Mean Reversion
    # RSIMeanReversionPenguinStrict1,     # RSI Mean Reversion variant 1
    # RSIMeanReversionPenguinStrict2,     # RSI Mean Reversion variant 2
    #RSIMeanReversionReducedPenguin,     # Adaptive RSI - targets 1-10 trades/day (LIST 2 symbols)
    #RSIMeanReversionMomentumPenguin,    # 3-stage momentum RSI - RISING/FALLING/HOLDING
    #RSIMeanReversionSelectivePenguin,   # Low-frequency high-quality RSI mean reversion
    RSIConfluencePenguin,          # RSI + trend + momentum confluence strategy
    #BuyOneEachPenguin,                  # Buy exactly 1 share for each symbol once
    BuyMaxEachPenguin,                  # Buy maximum affordable shares for each symbol once

    #CopilotPenguin,                    # AI-assisted strategy
    #ThreeFoldMeanReversionTrendPenguin, # ThreeFold mean-reversion + trend
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
