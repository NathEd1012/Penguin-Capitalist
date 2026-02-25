# penguins/support_resistance_penguin.py
"""Simplified Support/Resistance Zone-based trading strategy."""
from typing import List, Tuple, Dict
from penguins.base_penguin import BasePenguin


class SupportResistancePenguin(BasePenguin):
    """
    Simplified Support/Resistance Zone-based trading strategy.
    
    Identifies support and resistance from recent highs and lows,
    trades on bounces and breaks.
    """
    
    def __init__(
        self,
        lookback: int = 20,
        atr_period: int = 14,
    ):
        super().__init__("SupportResistancePenguin")
        self.lookback = lookback  # How many bars to look at for S/R
        self.atr_period = atr_period  # ATR period for volatility
        
    def _compute_atr(self, prices: List[float]) -> float:
        """Compute Average True Range."""
        if len(prices) < 2:
            return 0
        
        tr_values = []
        for i in range(len(prices) - 1, max(len(prices) - self.atr_period - 1, -1), -1):
            if i == 0:
                tr = prices[i]
            else:
                high_low = prices[i] - min(prices[i], prices[i-1])
                tr = high_low
            tr_values.append(tr)
        
        return sum(tr_values) / len(tr_values) if tr_values else 0
    
    def decide(self, symbol: str, mid_prices: List[float], bid: float, ask: float, portfolio) -> Tuple[str, int]:
        """
        Make trading decision based on support/resistance zones.
        
        Strategy:
        - BUY: Price bounces off recent support
        - SELL: Price breaks below support or takes profit
        """
        if bid <= 0 or ask <= 0:
            return "HOLD", 0

        if len(mid_prices) < self.lookback + 2:
            return "HOLD", 0

        # Get recent prices
        recent_prices = mid_prices[-self.lookback:]
        current_price = mid_prices[-1]
        previous_price = mid_prices[-2]
        
        # Calculate support and resistance levels
        support = min(recent_prices)
        resistance = max(recent_prices)
        mid_level = (support + resistance) / 2
        
        # ATR for volatility adjustment
        atr = self._compute_atr(mid_prices)
        
        # Check position status
        has_position = (
            symbol in portfolio.positions and
            portfolio.positions[symbol].qty > 0
        )
        
        # === BUY SIGNALS ===
        if not has_position:
            # Buy on bounce from support (price near support + moving up)
            near_support = abs(current_price - support) < atr * 0.5
            bouncing_up = current_price > previous_price
            
            if near_support and bouncing_up:
                if portfolio.cash >= ask:
                    return "BUY", 1
        
        # === SELL SIGNALS ===
        if has_position:
            qty = portfolio.positions[symbol].qty
            entry_price = portfolio.positions[symbol].avg_price
            
            # Sell on break below support
            if current_price < support and previous_price >= support:
                return "SELL", qty
            
            # Sell on resistance or take profit (5%)
            profit_pct = (current_price - entry_price) / entry_price * 100
            if current_price > resistance or profit_pct > 5:
                return "SELL", qty
            
            # Stop loss at -3%
            if profit_pct < -3:
                return "SELL", qty
        
        return "HOLD", 0
