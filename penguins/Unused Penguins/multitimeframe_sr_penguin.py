"""Multi-timeframe Support/Resistance strategy (decision layer only)."""

from typing import Dict, List, Optional, Tuple

from indicators.multitimeframe_sr import (
    DEFAULT_TIMEFRAMES,
    get_range_sr_signals,
    record_range_sr_snapshot,
    update_range_sr_cache,
)
from penguins.base_penguin import BasePenguin


class MultitimeframeRangeSRPenguin(BasePenguin):
    """Decision model using range-based multi-timeframe S/R levels from indicators."""
    USES_SR_LINES = True
    LOOKBACK_BARS = 100000  # Needs full history for multi-year timeframes (1y max)
    
    def __init__(
        self,
        recalc_threshold_pct: float = 0.20,
    ):
        super().__init__("MultitimeframeRangeSRPenguin")
        self.recalc_threshold_pct = recalc_threshold_pct
        self.record_history = True
        self.timeframes = dict(DEFAULT_TIMEFRAMES)
        self.cache: Dict[str, Dict] = {}
        self.sr_history: Dict[str, List[Dict[str, Optional[float]]]] = {}

    def export_sr_history(self) -> Dict[str, List[Dict[str, Optional[float]]]]:
        return self.sr_history
    
    def decide(
        self, 
        symbol: str, 
        mid_prices: List[float], 
        bid: float, 
        ask: float, 
        portfolio
    ) -> Tuple[str, int]:
        """
        Make trading decision based on multi-timeframe S/R lines.
        
        Strategy:
        - BUY when price is near support on multiple timeframes with upward momentum
        - SELL when price is near resistance on multiple timeframes or stops are hit
        - Updates S/R lines adaptively based on recalc_threshold_pct
        """
        if bid <= 0 or ask <= 0:
            return "HOLD", 0

        if len(mid_prices) < 50:  # Minimum data required
            return "HOLD", 0

        current_price = mid_prices[-1]
        previous_price = mid_prices[-2] if len(mid_prices) > 1 else current_price
        
        update_range_sr_cache(
            cache=self.cache,
            symbol=symbol,
            mid_prices=mid_prices,
            timeframes=self.timeframes,
            recalc_threshold_pct=self.recalc_threshold_pct,
        )
        if self.record_history:
            record_range_sr_snapshot(
                cache=self.cache,
                sr_history=self.sr_history,
                symbol=symbol,
                current_price=current_price,
                timeframes=self.timeframes,
            )

        signals = get_range_sr_signals(self.cache, symbol, current_price)
        
        if not signals:
            return "HOLD", 0
        
        # Check position status
        has_position = portfolio.get_position(symbol) > 0
        
        # Calculate momentum
        recent_prices = mid_prices[-5:]
        momentum = (recent_prices[-1] - recent_prices[0]) / recent_prices[0] if recent_prices[0] != 0 else 0
        
        # === BUY SIGNALS ===
        # Allow adding to an existing position on repeated buy signals.
        near_support_count = sum(1 for sig in signals.values() if sig in ["NEAR_S", "NEAR_S_BELOW"])
        
        # Buy if:
        # 1. Price is near support on at least 2 timeframes
        # 2. Has positive momentum (bouncing)
        # 3. Not broken below support on longer timeframes
        
        longer_tf_broken = any(
            sig == "BELOW_S" 
            for tf, sig in signals.items() 
            if tf in ["1y", "3m", "1m"]
        )
        
        if (near_support_count >= 2 and 
            momentum > 0.0001 and 
            not longer_tf_broken):
            
            if portfolio.cash >= ask:
                return "BUY", 1
        
        # === SELL SIGNALS ===
        if has_position:
            qty = portfolio.get_position(symbol)
            entry_price = portfolio.cost_basis.get(symbol, current_price)
            profit_pct = (current_price - entry_price) / entry_price * 100 if entry_price != 0 else 0
            
            # Count how many timeframes show price near/above resistance
            near_resistance_count = sum(
                1 for sig in signals.values() 
                if sig in ["NEAR_R", "NEAR_R_ABOVE", "ABOVE_R"]
            )
            
            # Sell if:
            # 1. Price near resistance on multiple timeframes
            # 2. Profit target hit (7%)
            # 3. Stop loss hit (-3%)
            # 4. Break below support on 2+ timeframes
            
            below_support_count = sum(
                1 for sig in signals.values() 
                if sig in ["BELOW_S", "NEAR_S_BELOW"]
            )
            
            if near_resistance_count >= 2 and profit_pct > 2:
                return "SELL", qty
            
            if profit_pct > 7:
                return "SELL", qty
            
            if profit_pct < -3:
                return "SELL", qty
            
            if below_support_count >= 2:
                return "SELL", qty
        
        return "HOLD", 0


# Backward compatibility: old name kept as alias.
MultitimeframeSRPenguin = MultitimeframeRangeSRPenguin
