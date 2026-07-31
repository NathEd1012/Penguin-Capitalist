"""Active trading strategy (penguin) configuration."""
import os
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
    ManualTuneAdvSELL_TP1,
    ManualTuneAdvSELL_TP1_Manual,
    ManualTuneAdvSELL_TP2,
    ManualTuneAdvSELL_TP2_Manual,
    ManualTuneAdvSELL_TP3,
    ManualTuneAdvSELL_TP3_Manual,
    ManualTuneAdvSELL_TP4,
    ManualTuneAdvSELL_TP4_Manual,
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

MANUAL_TUNE_ADV_SELL = [
    ManualTuneAdvSELL_TP1,
    ManualTuneAdvSELL_TP1_Manual,
    ManualTuneAdvSELL_TP2,
    ManualTuneAdvSELL_TP2_Manual,
    ManualTuneAdvSELL_TP3,
    ManualTuneAdvSELL_TP3_Manual,
    ManualTuneAdvSELL_TP4,
    ManualTuneAdvSELL_TP4_Manual,
]

ACTIVE_PENGUINSx = [
    *OG_TP,
    *ADV_SELL,
    *MANUAL_TUNE_ADV_SELL,
    SP500,                              # Buy & hold S&P 500 ETF benchmark (SPY)
    #SP500x2,                            # Buy & hold 2x leveraged S&P 500 ETF (SSO)
    SmartRSIConfluencePenguin,          # RSI + trend + momentum confluence strategy
    BuyMaxEachPenguin,                  # Buy maximum affordable shares for each symbol once
    #ThreeFoldMeanReversionTrendPenguin, # ThreeFold mean-reversion + trend
]

_STRATEGY_GROUPS = {
    "OG_TP": OG_TP,
    "ADV_SELL": ADV_SELL,
    "MANUAL_TUNE_ADV_SELL": MANUAL_TUNE_ADV_SELL,
}

_STRATEGY_CLASSES = {
    strategy.__name__: strategy
    for strategy in ACTIVE_PENGUINSx
}


def _resolve_active_penguins(raw_value):
    if raw_value is None:
        return ACTIVE_PENGUINSx

    selected = []
    seen = set()
    tokens = str(raw_value).replace("\n", ",").split(",")

    for token in tokens:
        name = token.strip()
        if not name:
            continue
        if name.startswith("*"):
            name = name[1:]

        if name in _STRATEGY_GROUPS:
            strategies = _STRATEGY_GROUPS[name]
        elif name in _STRATEGY_CLASSES:
            strategies = [_STRATEGY_CLASSES[name]]
        else:
            raise ValueError(f"Unknown ACTIVE_PENGUINS entry: {name}")

        for strategy in strategies:
            if strategy not in seen:
                selected.append(strategy)
                seen.add(strategy)

    return selected or ACTIVE_PENGUINSx


ACTIVE_PENGUINS = _resolve_active_penguins(os.getenv("ACTIVE_PENGUINS"))


__all__ = [
    "OG_TP",
    "ADV_SELL",
    "MANUAL_TUNE_ADV_SELL",
    "ACTIVE_PENGUINS",
]
