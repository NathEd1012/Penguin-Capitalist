from .base_penguin import BasePenguin
from .momentum_penguin import MomentumPenguin
from .rsi_mr_improved_penguin import MeanReversionPenguin
from .breakout_penguin import BreakoutPenguin
from .copilot_penguin import CopilotPenguin
from .minmax_sr20_penguin import MinMaxSRPenguin, SupportResistancePenguin
from .multitimeframe_sr_penguin import MultitimeframeSRPenguin
from .multitimeframe_sr_penguin import MultitimeframeRangeSRPenguin
from .multitimeframe_reaction_sr_penguin import MultitimeframeReactionSRPenguin
from .moving_average_crossover_penguin import MovingAverageCrossoverPenguin
from .rsi_mr_penguin import RSIMeanReversionPenguin
from .sma20_penguin import SMA20MultiTimeframePenguin, SMA20Penguin
from .volatility_breakout_penguin import VolatilityBreakoutPenguin
from .SP500_penguin import SP500Penguin, MSCIWorldPenguin

__all__ = [
    "BasePenguin",
    "MomentumPenguin",
    "MeanReversionPenguin",
    "BreakoutPenguin",
    "CopilotPenguin",
    "MinMaxSRPenguin",
    "SupportResistancePenguin",
    "MultitimeframeSRPenguin",
    "MultitimeframeRangeSRPenguin",
    "MultitimeframeReactionSRPenguin",
    "MovingAverageCrossoverPenguin",
    "RSIMeanReversionPenguin",
    "SMA20MultiTimeframePenguin",
    "SMA20Penguin",
    "VolatilityBreakoutPenguin",
    "SP500Penguin",
    "MSCIWorldPenguin",
]
