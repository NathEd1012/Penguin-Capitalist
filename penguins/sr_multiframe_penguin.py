"""Placeholder penguin for multiframe plotting without S/R decision logic."""

from typing import Dict, List, Optional, Tuple

from penguins.base_penguin import BasePenguin


class SRMultiframePenguin(BasePenguin):
    """Trigger multiframe pipeline and record price snapshots only."""

    USES_SR_LINES = True
    REQUIRES_SR_PRECOMPUTE = False
    LOOKBACK_BARS = 100

    def __init__(self):
        super().__init__("SR_Multiframe_Penguin")
        self.record_history = True
        self.sr_history: Dict[str, List[Dict[str, Optional[float]]]] = {}
        self._current_timestamp = None

    def _advance_bar(self) -> None:
        """Compatibility hook used by runner for S/R penguins."""
        return None

    def set_current_timestamp(self, timestamp) -> None:
        """Store current bar timestamp for plotting snapshots."""
        self._current_timestamp = timestamp

    def export_sr_history(self) -> Dict[str, List[Dict[str, Optional[float]]]]:
        return self.sr_history

    def decide(self, symbol: str, mid_prices: List[float], bid: float, ask: float, portfolio) -> Tuple[str, int]:
        """Record stock price for plots and do not trade yet."""
        if not mid_prices:
            return "HOLD", 0

        if self.record_history:
            if symbol not in self.sr_history:
                self.sr_history[symbol] = []
            self.sr_history[symbol].append(
                {
                    "price": float(mid_prices[-1]),
                    "timestamp": self._current_timestamp,
                }
            )

        return "HOLD", 0
