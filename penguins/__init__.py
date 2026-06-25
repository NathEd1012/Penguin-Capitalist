from .base_penguin import BasePenguin
from .TrainablePenguin1 import TrainablePenguin1
from .TrainablePenguin1 import TrainablePenguin1_Manual
from .TrainablePenguin2 import TrainablePenguin2
from .TrainablePenguin2 import TrainablePenguin2_Manual
from .TrainablePenguin3 import TrainablePenguin3
from .TrainablePenguin3 import TrainablePenguin3_Manual
from .TrainablePenguin4 import TrainablePenguin4
from .TrainablePenguin4 import TrainablePenguin4_Manual
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
    "TrainablePenguin1_Manual",
    "TrainablePenguin2",
    "TrainablePenguin2_Manual",
    "TrainablePenguin3",
    "TrainablePenguin3_Manual",
    "TrainablePenguin4",
    "TrainablePenguin4_Manual",
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
