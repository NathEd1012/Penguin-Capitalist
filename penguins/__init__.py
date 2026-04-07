from .base_penguin import BasePenguin
from .momentum_penguin import MomentumPenguin
from .rsi_mr_penguin import RSIMeanReversionPenguin
from .rsi_mr_advanced_penguin import RSIMeanReversionAdvancedPenguin
from .rsi_mr_penguin import RSIMeanReversionPenguinStrict1, RSIMeanReversionPenguinStrict2
from .copilot_penguin import CopilotPenguin
from .minmax_sr20_penguin import MinMaxSRPenguin
from .sr_multiframe_penguin import SRMultiframePenguin
from .sma20_penguin import SMA20AdvancedPenguin, SMA20Penguin
from .SP500 import SP500Penguin

# Backwards-compatible alias used by config/strategies.py
SP500 = SP500Penguin

__all__ = [
    "BasePenguin",
    "MomentumPenguin",
    "RSIMeanReversionPenguin",
    "RSIMeanReversionPenguinStrict1",
    "RSIMeanReversionPenguinStrict2",
    "RSIMeanReversionAdvancedPenguin",
    "CopilotPenguin",
    "MinMaxSRPenguin",
    "SRMultiframePenguin",
    "SMA20AdvancedPenguin",
    "SMA20Penguin",
    "SP500",
    "SP500Penguin",
]
