from .base_penguin import BasePenguin
from .momentum_penguin import MomentumPenguin
from .rsi_mr_penguin import (
    RSIMeanReversionPenguin,
    RSIMeanReversionPenguinStrict1,
    RSIMeanReversionPenguinStrict2,
)
from .rsi_mr_reduced_penguin import RSIMeanReversionReducedPenguin
from .rsi_mr_momentum_penguin import RSIMeanReversionMomentumPenguin
from .rsi_mr_selective import RSIMeanReversionSelectivePenguin
from .smart_rsi_confluence_penguin import SmartRSIConfluencePenguin
from .copilot_penguin import CopilotPenguin
from .minmax_sr20_penguin import MinMaxSRPenguin
from .sr_multiframe_penguin import SRMultiframePenguin
from .sma20_penguin import SMA20AdvancedPenguin, SMA20Penguin
from .SP500 import SP500
from .SP500x2 import SP500x2
from .buy_one_each_penguin import BuyOneEachPenguin
from .buy_max_each_penguin import BuyMaxEachPenguin

__all__ = [
    "BasePenguin",
    "MomentumPenguin",
    "RSIMeanReversionPenguin",
    "RSIMeanReversionPenguinStrict1",
    "RSIMeanReversionPenguinStrict2",
    "RSIMeanReversionReducedPenguin",
    "RSIMeanReversionMomentumPenguin",
    "RSIMeanReversionSelectivePenguin",
    "SmartRSIConfluencePenguin",
    "CopilotPenguin",
    "MinMaxSRPenguin",
    "SRMultiframePenguin",
    "SMA20AdvancedPenguin",
    "SMA20Penguin",
    "SP500",
    "SP500x2",
    "BuyOneEachPenguin",
    "BuyMaxEachPenguin",
]
