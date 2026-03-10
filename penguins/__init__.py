from .base_penguin import BasePenguin
from .momentum_penguin import MomentumPenguin
from .mean_reversion_penguin import MeanReversionPenguin
from .breakout_penguin import BreakoutPenguin
from .random_penguin import RandomPenguin
from .random_penguin2 import RandomPenguin2
from .trend_penguin import TrendPenguin
from .careful_trend_penguin import CarefulTrendPenguin
from .copilot_penguin import CopilotPenguin
from .support_resistance_penguin import SupportResistancePenguin
from .multitimeframe_sr_penguin import MultitimeframeSRPenguin
from .multitimeframe_sr_penguin import MultitimeframeRangeSRPenguin
from .multitimeframe_reaction_sr_penguin import MultitimeframeReactionSRPenguin
from .moving_average_crossover_penguin import MovingAverageCrossoverPenguin
from .rsi_mean_reversion_penguin import RSIMeanReversionPenguin
from .sma20_multitimeframe_penguin import SMA20MultiTimeframePenguin
from .volatility_breakout_penguin import VolatilityBreakoutPenguin
from .msci_world_penguin import SP500Penguin, MSCIWorldPenguin

__all__ = [
    "BasePenguin",
    "MomentumPenguin",
    "MeanReversionPenguin",
    "BreakoutPenguin",
    "RandomPenguin",
    "RandomPenguin2",
    "TrendPenguin",
    "CarefulTrendPenguin",
    "CopilotPenguin",
    "SupportResistancePenguin",
    "MultitimeframeSRPenguin",
    "MultitimeframeRangeSRPenguin",
    "MultitimeframeReactionSRPenguin",
    "MovingAverageCrossoverPenguin",
    "RSIMeanReversionPenguin",
    "SMA20MultiTimeframePenguin",
    "VolatilityBreakoutPenguin",
    "SP500Penguin",
    "MSCIWorldPenguin",
]
