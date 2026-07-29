from .base_penguin import BasePenguin
from .OG_TP.OG_TP1 import OG_TP1
from .OG_TP.OG_TP1 import OG_TP1_Manual
from .OG_TP.OG_TP2 import OG_TP2
from .OG_TP.OG_TP2 import OG_TP2_Manual
from .OG_TP.OG_TP3 import OG_TP3
from .OG_TP.OG_TP3 import OG_TP3_Manual
from .OG_TP.OG_TP4 import OG_TP4
from .OG_TP.OG_TP4 import OG_TP4_Manual
from .Adv_SELL_TP.Adv_SELL_TP1 import Adv_SELL_TP1
from .Adv_SELL_TP.Adv_SELL_TP2 import Adv_SELL_TP2
from .Adv_SELL_TP.Adv_SELL_TP3 import Adv_SELL_TP3
from .Adv_SELL_TP.Adv_SELL_TP4 import Adv_SELL_TP4
from .Adv_SELL_TP.Adv_SELL_TP1 import Adv_SELL_TP1_Manual
from .Adv_SELL_TP.Adv_SELL_TP2 import Adv_SELL_TP2_Manual
from .Adv_SELL_TP.Adv_SELL_TP3 import Adv_SELL_TP3_Manual
from .Adv_SELL_TP.Adv_SELL_TP4 import Adv_SELL_TP4_Manual
from .ManualTune_Adv_SELL_TP.ManualTune_Adv_SELL_TP1 import ManualTuneAdvSELL_TP1, ManualTuneAdvSELL_TP1_Manual
from .ManualTune_Adv_SELL_TP.ManualTune_Adv_SELL_TP2 import ManualTuneAdvSELL_TP2, ManualTuneAdvSELL_TP2_Manual
from .ManualTune_Adv_SELL_TP.ManualTune_Adv_SELL_TP3 import ManualTuneAdvSELL_TP3, ManualTuneAdvSELL_TP3_Manual
from .ManualTune_Adv_SELL_TP.ManualTune_Adv_SELL_TP4 import ManualTuneAdvSELL_TP4, ManualTuneAdvSELL_TP4_Manual
from .smart_rsi_confluence_penguin import SmartRSIConfluencePenguin
from .SP500 import SP500
from .SP500x2 import SP500x2
from .ThreeFoldMeanReversionTrendPenguin import ThreeFoldMeanReversionTrendPenguin
from .buy_max_each_penguin import BuyMaxEachPenguin
from .buy_equal_price_each_penguin import BuyEqualPriceEachPenguin

__all__ = [
    "BasePenguin",
    "OG_TP1",
    "OG_TP1_Manual",
    "OG_TP2",
    "OG_TP2_Manual",
    "OG_TP3",
    "OG_TP3_Manual",
    "OG_TP4",
    "OG_TP4_Manual",
    "TrainablePenguin1",
    "TrainablePenguin1_Manual",
    "TrainablePenguin2",
    "TrainablePenguin2_Manual",
    "TrainablePenguin3",
    "TrainablePenguin3_Manual",
    "TrainablePenguin4",
    "TrainablePenguin4_Manual",
    "Adv_SELL_TP1",
    "Adv_SELL_TP1_Manual",
    "Adv_SELL_TP2",
    "Adv_SELL_TP2_Manual",
    "Adv_SELL_TP3",
    "Adv_SELL_TP3_Manual",
    "Adv_SELL_TP4",
    "Adv_SELL_TP4_Manual",
    "ManualTuneAdvSELL_TP1",
    "ManualTuneAdvSELL_TP1_Manual",
    "ManualTuneAdvSELL_TP2",
    "ManualTuneAdvSELL_TP2_Manual",
    "ManualTuneAdvSELL_TP3",
    "ManualTuneAdvSELL_TP3_Manual",
    "ManualTuneAdvSELL_TP4",
    "ManualTuneAdvSELL_TP4_Manual",
    "SmartRSIConfluencePenguin",
    "ThreeFoldMeanReversionTrendPenguin",
    "SP500",
    "SP500x2",
    "BuyMaxEachPenguin",
    "BuyEqualPriceEachPenguin",
]

# Backward-compatible aliases for older registry names.
TrainablePenguin1 = Adv_SELL_TP1
TrainablePenguin1_Manual = Adv_SELL_TP1_Manual
TrainablePenguin2 = Adv_SELL_TP2
TrainablePenguin2_Manual = Adv_SELL_TP2_Manual
TrainablePenguin3 = Adv_SELL_TP3
TrainablePenguin3_Manual = Adv_SELL_TP3_Manual
TrainablePenguin4 = Adv_SELL_TP4
TrainablePenguin4_Manual = Adv_SELL_TP4_Manual
