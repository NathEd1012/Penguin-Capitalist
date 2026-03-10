# penguins/support_resistance_penguin.py
"""Multi-timeframe Support/Resistance Zone-based trading strategy."""
from typing import List, Tuple, Dict, Optional
from statistics import mean, stdev
from penguins.base_penguin import BasePenguin


class SupportResistancePenguin(BasePenguin):
    """
    Multi-timeframe Support/Resistance Zone-based trading strategy.
    
    Identifies and maintains support/resistance levels across multiple time horizons:
    - 1 year, 3 months, 1 month, 1 week, 1 day
    Levels persist and are reused, not recalculated every bar.
    """
    USES_SR_LINES = True
    
    def __init__(
        self,
        atr_period: int = 14,
    ):
        super().__init__("SupportResistancePenguin")
        self.atr_period = atr_period
        
        # Multi-timeframe configuration (1-minute bars)
        # Assumes ~390 bars per trading day (6.5 hours × 60 minutes)
        self.timeframe_bars = {
            "1d": 390,           # 1 day
            "1w": 390 * 5,       # 1 week (5 trading days)
            "1m": 390 * 21,      # ~1 month (21 trading days)
            "3m": 390 * 63,      # ~3 months (63 trading days)
            "1y": 390 * 252,     # ~1 year (252 trading days)
        }
        
        # Cache for persisted S/R levels per symbol
        # Format: {symbol: {timeframe: {"support": [...], "resistance": [...]}}}
        self.level_cache: Dict[str, Dict[str, Dict[str, List[float]]]] = {}
    
    def _identify_sr_zones(self, prices: List[float]) -> Tuple[List[float], List[float]]:
        """
        Identify support and resistance zones using Donchian channels.
        """
        if len(prices) < 10:
            return [], []
        
        support = min(prices)
        resistance = max(prices)
        
        return [support], [resistance]
    
    def _get_recent_levels(self, mid_prices: List[float]) -> Tuple[float, float]:
        """
        Get recent (20-bar rolling window) support and resistance.
        These are used for immediate trading decisions.
        """
        lookback = min(20, len(mid_prices))
        recent_prices = mid_prices[-lookback:]
        
        support = min(recent_prices)
        resistance = max(recent_prices)
        
        return support, resistance
    
    def _update_levels_for_symbol(self, symbol: str, mid_prices: List[float]) -> None:
        """
        Update S/R levels for a symbol across all timeframes.
        Uses persisted cache to track levels across multiple decision steps.
        """
        if symbol not in self.level_cache:
            self.level_cache[symbol] = {}
        
        # Update levels for each timeframe
        for timeframe, num_bars in self.timeframe_bars.items():
            if num_bars > len(mid_prices):
                # Not enough data for this timeframe yet
                continue
            
            prices_for_tf = mid_prices[-num_bars:]
            supports, resistances = self._identify_sr_zones(prices_for_tf)
            
            self.level_cache[symbol][timeframe] = {
                "support": supports,
                "resistance": resistances,
            }
    
    def _get_relevant_levels(self, symbol: str, current_price: float) -> Tuple[Optional[float], Optional[float]]:
        """
        Get the most relevant support and resistance levels using multi-timeframe data.
        
        Strategy:
        - Support = average of the lowest supports across timeframes
        - Resistance = average of the highest resistances across timeframes
        - Ensures meaningful zones around the current price
        """
        if symbol not in self.level_cache or not self.level_cache[symbol]:
            return None, None
        
        # Collect support/resistance data from all timeframes
        all_supports = []
        all_resistances = []
        
        for timeframe, data in self.level_cache[symbol].items():
            supports = data.get("support", [])
            resistances = data.get("resistance", [])
            if supports:
                all_supports.extend(supports)
            if resistances:
                all_resistances.extend(resistances)
        
        if not all_supports or not all_resistances:
            return None, None
        
        # Use the geometric mean of supports (favors most conservative/strongest)
        # and resistances from all timeframes
        support = min(all_supports) if all_supports else None
        resistance = max(all_resistances) if all_resistances else None
        
        if support is None or resistance is None or support >= resistance:
            return None, None
        
        return support, resistance
    
    def decide(self, symbol: str, mid_prices: List[float], bid: float, ask: float, portfolio) -> Tuple[str, int]:
        """
        Make trading decision based on support/resistance levels.
        
        Strategy:
        - Use recent (20-bar) support/resistance for immediate trading
        - Maintain multi-timeframe context (updated in background)
        - BUY: Price bounces off support with upward momentum
        - SELL: Price breaks below support or reaches resistance
        """
        if bid <= 0 or ask <= 0:
            return "HOLD", 0

        if len(mid_prices) < 20:  # Minimum for 20-bar lookback
            return "HOLD", 0

        current_price = mid_prices[-1]
        previous_price = mid_prices[-2] if len(mid_prices) > 1 else current_price
        
        # Update multi-timeframe levels (for context, persisted across calls)
        if len(mid_prices) >= 100:  # Only update if we have enough historical data
            self._update_levels_for_symbol(symbol, mid_prices)
        
        # Get recent (20-bar) support and resistance for immediate trading
        support, resistance = self._get_recent_levels(mid_prices)
        
        if support >= resistance:
            return "HOLD", 0
        
        # Check position status
        has_position = (
            symbol in portfolio.positions and
            portfolio.positions[symbol].qty > 0
        )
        
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
        
        if near_support and bouncing_up and has_momentum:
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
            profit_pct = (current_price - entry_price) / entry_price * 100 if entry_price != 0 else 0
            if current_price >= resistance or profit_pct > 5:
                return "SELL", qty
            
            # Stop loss at -3%
            if profit_pct < -3:
                return "SELL", qty
        
        return "HOLD", 0
