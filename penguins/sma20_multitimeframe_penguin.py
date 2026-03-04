# penguins/sma20_multitimeframe_penguin.py
from typing import List, Tuple, Dict
from penguins.base_penguin import BasePenguin


class SMA20MultiTimeframePenguin(BasePenguin):
    """
    SMA 20 Multi-Timeframe Trading Strategy
    
    Dynamically analyzes SMA 20 from historical data at 3 timeframes (daily, weekly, monthly).
    Uses SMA lines as support/resistance levels:
    - Above SMA: Price supported, expect bounce up (support signal)
    - Below SMA: Price resistance, expect rejection down (resistance signal)
    
    Trading Logic:
    - BUY: Price crosses above weighted SMA (support signal), only when not holding
    - SELL: Price crosses below weighted SMA (resistance signal) or take profit/stop loss
    """
    
    def __init__(self):
        super().__init__("SMA20MultiTimeframePenguin")
        self.timeframe_steps = {
            "base": 1,
            "mid": 3,
            "long": 6,
        }
        self.cross_tolerance = 0.0015
        self.sma_length = 12
    
    def _calculate_weighted_sma(self, sma_levels: Dict[str, float]) -> float:
        """Calculate weighted average of SMA levels across timeframes."""
        if not sma_levels:
            return 0.0

        weights = {"base": 0.55, "mid": 0.30, "long": 0.15}
        
        weighted_sum = sum(
            sma * weights.get(tf, 0)
            for tf, sma in sma_levels.items()
        )
        total_weight = sum(weights.get(tf, 0) for tf in sma_levels.keys())
        
        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def _calculate_sma_levels(self, prices: List[float]) -> Dict[str, float]:
        """Calculate SMA20 levels on multiple compressed timeframes from one price series."""
        sma_levels: Dict[str, float] = {}

        for timeframe_name, step in self.timeframe_steps.items():
            needed = self.sma_length * step
            if len(prices) < needed:
                continue

            window = prices[-needed:]
            compressed = window[step - 1::step]
            if len(compressed) >= self.sma_length:
                sma_levels[timeframe_name] = sum(compressed[-self.sma_length:]) / self.sma_length

        return sma_levels
    
    def decide(self, symbol: str, mid_prices: List[float], bid: float, ask: float, portfolio) -> Tuple[str, int]:
        """
        Make trading decision based on SMA 20 levels.
        
        Strategy:
        - BUY: Price crosses above SMA 20 (support signal)
        - SELL: Price crosses below SMA 20 (resistance signal) or take profit/stop loss
        """
        if bid <= 0 or ask <= 0:
            return "HOLD", 0
        
        max_step = max(self.timeframe_steps.values())
        min_required = self.sma_length * max_step + 1
        if len(mid_prices) < min_required:
            return "HOLD", 0
        
        # Check current position
        has_position = (
            symbol in portfolio.positions and portfolio.positions[symbol].qty > 0
        )
        
        # Calculate weighted multi-timeframe SMA (current and previous bar context)
        sma_levels_current = self._calculate_sma_levels(mid_prices)
        sma_levels_previous = self._calculate_sma_levels(mid_prices[:-1])

        if not sma_levels_current or not sma_levels_previous:
            return "HOLD", 0

        weighted_sma = self._calculate_weighted_sma(sma_levels_current)
        previous_weighted_sma = self._calculate_weighted_sma(sma_levels_previous)
        
        # Use mid price for crossover detection
        current_mid = mid_prices[-1]
        previous_mid = mid_prices[-2] if len(mid_prices) >= 2 else mid_prices[-1]
        
        upper_prev = previous_weighted_sma * (1 + self.cross_tolerance)
        lower_prev = previous_weighted_sma * (1 - self.cross_tolerance)
        upper_now = weighted_sma * (1 + self.cross_tolerance)
        lower_now = weighted_sma * (1 - self.cross_tolerance)

        was_above = previous_mid > upper_prev
        was_below = previous_mid < lower_prev
        is_above = current_mid > upper_now
        is_below = current_mid < lower_now
        
        short_momentum = (current_mid - previous_mid) / previous_mid if previous_mid > 0 else 0

        # === BUY SIGNALS (only when not holding) ===
        if not has_position:
            # Buy: either clean cross-up OR already above MTF trend with positive momentum
            cross_up = was_below and is_above
            trend_follow_entry = current_mid > weighted_sma and short_momentum > 0.0005
            if cross_up or trend_follow_entry:
                if ask > weighted_sma:  # Confirm buy above weighted trend level
                    return "BUY", 1
        
        # === SELL SIGNALS (only when holding) ===
        if has_position:
            qty = portfolio.positions[symbol].qty
            entry_price = portfolio.positions[symbol].avg_price
            
            # Sell: Price crosses below SMA 20
            cross_down = was_above and is_below
            trend_break = current_mid < weighted_sma and short_momentum < -0.0005
            if cross_down or trend_break:
                return "SELL", qty
            
            # Take profit: 5% gain
            profit_pct = (bid - entry_price) / entry_price * 100
            if profit_pct > 5:
                return "SELL", qty
            
            # Stop loss: -3% loss
            if profit_pct < -3:
                return "SELL", qty
        
        return "HOLD", 0
