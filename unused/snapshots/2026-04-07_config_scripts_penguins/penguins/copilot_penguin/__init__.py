"""
CopilotPenguin: Modular trend-following trading strategy with decision logging.
"""
from penguins.copilot_penguin.copilot_penguin import CopilotPenguin
from penguins.copilot_penguin.decision_logger import DecisionLogger, get_logger
from penguins.copilot_penguin.tactics import BaseTactic, TacticV1

__all__ = ["CopilotPenguin", "DecisionLogger", "get_logger", "BaseTactic", "TacticV1"]
