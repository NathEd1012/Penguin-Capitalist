"""Active trading strategy (penguin) configuration."""

from penguins import (
    BuyEqualPriceEachPenguin,
    BuyMaxEachPenguin,
    OG_TP1,
    OG_TP1_Manual,
    OG_TP2,
    OG_TP2_Manual,
    OG_TP3,
    OG_TP3_Manual,
    OG_TP4,
    OG_TP4_Manual,
    SP500,
    SP500x2,
    SmartRSIConfluencePenguin,
    ThreeFoldMeanReversionTrendPenguin,
    Adv_SELL_TP1,
    Adv_SELL_TP1_Manual,
    Adv_SELL_TP2,
    Adv_SELL_TP2_Manual,
    Adv_SELL_TP3,
    Adv_SELL_TP3_Manual,
    Adv_SELL_TP4,
    Adv_SELL_TP4_Manual,
)

# from penguins.multitimeframe_reaction_sr_penguin import MultitimeframeReactionSRPenguin

# ========== ACTIVE PENGUINS ==========
# List of penguin strategy classes to run in the backtest.

OG_TP = [
    OG_TP1,
    OG_TP1_Manual,
    OG_TP2,
    OG_TP2_Manual,
    OG_TP3,
    OG_TP3_Manual,
    OG_TP4,
    OG_TP4_Manual,
]

ADV_SELL = [
    Adv_SELL_TP1,
    Adv_SELL_TP1_Manual,
    Adv_SELL_TP2,
    Adv_SELL_TP2_Manual,
    Adv_SELL_TP3,
    Adv_SELL_TP3_Manual,
    Adv_SELL_TP4,
    Adv_SELL_TP4_Manual,
]

ACTIVE_PENGUINS = [
    *OG_TP,
    *ADV_SELL,
    SP500,                              # Buy & hold S&P 500 ETF benchmark (SPY)
    #SP500x2,                            # Buy & hold 2x leveraged S&P 500 ETF (SSO)
    SmartRSIConfluencePenguin,          # RSI + trend + momentum confluence strategy
    BuyMaxEachPenguin,                  # Buy maximum affordable shares for each symbol once
    #ThreeFoldMeanReversionTrendPenguin, # ThreeFold mean-reversion + trend
]

__all__ = [
    "OG_TP",
    "ADV_SELL",
    "ACTIVE_PENGUINS",
]
