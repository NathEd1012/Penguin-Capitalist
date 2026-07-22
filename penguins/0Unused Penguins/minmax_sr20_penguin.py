# penguins/minmax_sr20_penguin.py
"""Support/Resistance Zone-based trading strategy."""
from typing import List, Tuple, Dict
from penguins.base_penguin import BasePenguin

# Change this single value to run as MinMaxSR20 / MinMaxSR50 / MinMaxSR100.
PRIMARY_SR_LOOKBACK = 50


class MinMaxSRPenguin(BasePenguin):
    """
    Support/Resistance Zone-based trading strategy.

    Uses recent rolling support/resistance levels for immediate decisions.
    """
    USES_SR_LINES = True
    REQUIRES_SR_PRECOMPUTE = False
    LOOKBACK_BARS = PRIMARY_SR_LOOKBACK
    
    def __init__(
        self,
        lookback_bars: int = PRIMARY_SR_LOOKBACK,
        atr_period: int = 14,
        stop_loss_pct: float = 0.03,
    ):
        super().__init__("MinMaxSRPenguin")
        self.lookback_bars = max(2, int(lookback_bars))
        self.atr_period = atr_period
        self.stop_loss_pct = stop_loss_pct

        # Track trailing-stop anchor as highest price seen since opening position.
        self._highest_prices_since_entry: Dict[str, float] = {}
    
    def _get_recent_levels(self, mid_prices: List[float]) -> Tuple[float, float]:
        """
        Get recent rolling-window support and resistance.
        These are used for immediate trading decisions.
        """
        lookback = min(self.lookback_bars, len(mid_prices))
        recent_prices = mid_prices[-lookback:]
        
        support = min(recent_prices)
        resistance = max(recent_prices)
        
        return support, resistance
    
    
    def decide(self, symbol: str, mid_prices: List[float], bid: float, ask: float, portfolio) -> Tuple[str, int]:
        """
        Make trading decision based on support/resistance levels.
        
        Strategy:
        - Use recent rolling-window support/resistance for immediate trading
        - BUY: Price bounces off support with upward momentum
        - SELL: Price breaks below support or reaches resistance
        """
        if bid <= 0 or ask <= 0:
            return "HOLD", 0

        if len(mid_prices) < self.lookback_bars:
            return "HOLD", 0

        current_price = mid_prices[-1]
        previous_price = mid_prices[-2] if len(mid_prices) > 1 else current_price

        # Get recent rolling-window support and resistance for immediate trading
        support, resistance = self._get_recent_levels(mid_prices)
        
        if support >= resistance:
            return "HOLD", 0
        
        # Portfolio stores positions as symbol -> int quantity.
        position_qty = portfolio.get_position(symbol)
        has_position = position_qty > 0
        
        # Calculate price zones
        price_range = resistance - support
        distance_to_support = (current_price - support) / price_range if price_range > 0 else 0.5
        
        # Calculate momentum
        recent_prices = mid_prices[-5:]
        momentum = (recent_prices[-1] - recent_prices[0]) / recent_prices[0] if recent_prices[0] != 0 else 0
        
        # === BUY SIGNALS ===
        # Allow adding to an existing position on repeated buy signals.
        near_support = distance_to_support < 0.20  # Within 20% of support
        bouncing_up = current_price > previous_price
        has_momentum = momentum > 0.0001

        # Keep trailing stop state aligned with observed position state.
        if not has_position:
            self._highest_prices_since_entry.pop(symbol, None)
        else:
            prev_high = self._highest_prices_since_entry.get(symbol, current_price)
            self._highest_prices_since_entry[symbol] = max(prev_high, current_price)
        
        if near_support and bouncing_up and has_momentum:
            if portfolio.cash >= ask:
                prev_high = self._highest_prices_since_entry.get(symbol, current_price)
                self._highest_prices_since_entry[symbol] = max(prev_high, current_price)
                return "BUY", 1
        
        # === SELL SIGNALS ===
        if has_position:
            qty = position_qty
            highest_price = self._highest_prices_since_entry.get(symbol, current_price)
            
            # Sell on break below support
            if current_price < support and previous_price >= support:
                self._highest_prices_since_entry.pop(symbol, None)
                return "SELL", qty
            
            # Sell on resistance.
            if current_price >= resistance:
                self._highest_prices_since_entry.pop(symbol, None)
                return "SELL", qty
            
            # Trailing stop at stop_loss_pct below highest price since entry.
            trailing_stop_price = highest_price * (1.0 - self.stop_loss_pct)
            if bid <= trailing_stop_price:
                self._highest_prices_since_entry.pop(symbol, None)
                return "SELL", qty
        
        return "HOLD", 0

