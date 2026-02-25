# penguins/simple_sr_penguin.py
from typing import List, Tuple
from penguins.base_penguin import BasePenguin


class SimpleSRPenguin(BasePenguin):
    """
    Simplified Support/Resistance strategy:
    - BUY when price is near support
    - SELL when price is near resistance
    - No complex rejection patterns or R/R checks
    """
    
    def __init__(
        self,
        lookback: int = 20,
        zone_threshold_pct: float = 1.5,  # % distance to consider "near"
    ):
        super().__init__("SimpleSRPenguin")
        self.lookback = lookback
        self.zone_threshold_pct = zone_threshold_pct
        
    def decide(self, symbol: str, mid_prices: List[float], bid: float, ask: float, portfolio) -> Tuple[str, int]:
        """
        Simple S&R logic:
        - Support = recent low from lookback period
        - Resistance = recent high from lookback period
        - BUY if price within zone_threshold_pct of support
        - SELL if price within zone_threshold_pct of resistance
        """
        if bid <= 0 or ask <= 0:
            return "HOLD", 0

        if len(mid_prices) < self.lookback:
            return "HOLD", 0

        recent_prices = mid_prices[-self.lookback:]
        support = min(recent_prices)
        resistance = max(recent_prices)
        current_price = mid_prices[-1]
        
        # Check position status
        has_position = (
            symbol in portfolio.positions and
            portfolio.positions[symbol].qty > 0
        )
        
        # Calculate distance to support/resistance as percentage
        dist_to_support = abs(current_price - support) / support * 100
        dist_to_resistance = abs(current_price - resistance) / resistance * 100
        
        if not has_position:
            # BUY if near support
            if dist_to_support <= self.zone_threshold_pct:
                if portfolio.cash >= ask:
                    return "BUY", 1
        else:
            # SELL if near resistance or if price fell below support
            if dist_to_resistance <= self.zone_threshold_pct:
                qty = portfolio.positions[symbol].qty
                return "SELL", qty
            
            # Stop loss: if price breaks below support
            if current_price < support * 0.99:
                qty = portfolio.positions[symbol].qty
                return "SELL", qty
        
        return "HOLD", 0
