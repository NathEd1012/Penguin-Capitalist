from .base_penguin import BasePenguin
from .TrainablePenguin1 import TrainablePenguin1
from .TrainablePenguin2 import TrainablePenguin2
from .rsi_mr_selective import RSIMeanReversionSelectivePenguin
from .smart_rsi_confluence_penguin import SmartRSIConfluencePenguin
from .copilot_penguin import CopilotPenguin
from .SP500 import SP500
from .SP500x2 import SP500x2
from .buy_one_each_penguin import BuyOneEachPenguin
from .buy_max_each_penguin import BuyMaxEachPenguin
from .buy_equal_price_each_penguin import BuyEqualPriceEachPenguin

__all__ = [
    "BasePenguin",
    "TrainablePenguin1",
    "TrainablePenguin2",
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
    "BuyEqualPriceEachPenguin",
]
