from .base_penguin import BasePenguin
from .momentum_penguin import MomentumPenguin
from .rsi_mr_advanced_penguin import MeanReversionPenguin
from .copilot_penguin import CopilotPenguin
from .minmax_sr20_penguin import MinMaxSRPenguin, SupportResistancePenguin
from .multitimeframe_sr_penguin import MultitimeframeSRPenguin
from .multitimeframe_sr_penguin import MultitimeframeRangeSRPenguin
from .multitimeframe_reaction_sr_penguin import MultitimeframeReactionSRPenguin
from .rsi_mr_advanced_penguin import RSIMeanReversionPenguin
from .sma20_penguin import SMA20AdvancedPenguin, SMA20MultiTimeframePenguin, SMA20Penguin
from .SP500_penguin import SP500Penguin

__all__ = [
    "BasePenguin",
    "MomentumPenguin",
    "MeanReversionPenguin",
    "CopilotPenguin",
    "MinMaxSRPenguin",
    "SupportResistancePenguin",
    "MultitimeframeSRPenguin",
    "MultitimeframeRangeSRPenguin",
    "MultitimeframeReactionSRPenguin",
    "RSIMeanReversionPenguin",
    "SMA20AdvancedPenguin",
    "SMA20MultiTimeframePenguin",
    "SMA20Penguin",
    "SP500Penguin",
]
