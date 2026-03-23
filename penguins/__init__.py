from .base_penguin import BasePenguin
from .momentum_penguin import MomentumPenguin
from .rsi_mr_penguin import RSIMeanReversionPenguin
from .rsi_mr_advanced_penguin import RSIMeanReversionAdvancedPenguin
from .copilot_penguin import CopilotPenguin
from .minmax_sr20_penguin import MinMaxSRPenguin
from .sr_multiframe_penguin import SRMultiframePenguin
from .sma20_penguin import SMA20AdvancedPenguin, SMA20Penguin
from .SP500_penguin import SP500Penguin

__all__ = [
    "BasePenguin",
    "MomentumPenguin",
    "RSIMeanReversionPenguin",
    "RSIMeanReversionAdvancedPenguin",
    "CopilotPenguin",
    "MinMaxSRPenguin",
    "SRMultiframePenguin",
    "SMA20AdvancedPenguin",
    "SMA20Penguin",
    "SP500Penguin",
]
