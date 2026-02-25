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
        self.data_client = None
        self._previous_weighted_sma: Dict[str, float] = {}
        
    def initialize_sma_levels(self, symbols: List[str], data_client):
        """
        Store data client reference for dynamic SMA calculation.
        Call this once at the start of the simulation.
        """
        self.data_client = data_client
        print(f"\n📊 {self.name}: Initialized for dynamic multi-timeframe SMA calculation\n")
    
    def _calculate_sma_levels(self, symbol: str) -> Dict[str, float]:
        """Calculate current SMA 20 levels from fresh historical data."""
        if not self.data_client:
            return {}
        
        try:
            hist_data = self.data_client.get_multi_timeframe_history(symbol)
        except Exception:
            return {}
        
        sma_levels = {}
        for timeframe, prices in hist_data.items():
            if prices and len(prices) >= 20:
                sma_levels[timeframe] = sum(prices[-20:]) / 20
        
        return sma_levels
    
    def _calculate_weighted_sma(self, sma_levels: Dict[str, float]) -> float:
        """Calculate weighted average of SMA levels across timeframes."""
        if not sma_levels:
            return 0.0
        
        weights = {"daily": 0.40, "weekly": 0.35, "monthly": 0.25}
        
        weighted_sum = sum(
            sma * weights.get(tf, 0)
            for tf, sma in sma_levels.items()
        )
        total_weight = sum(weights.get(tf, 0) for tf in sma_levels.keys())
        
        return weighted_sum / total_weight if total_weight > 0 else 0.0
    
    def decide(self, symbol: str, mid_prices: List[float], bid: float, ask: float, portfolio) -> Tuple[str, int]:
        """
        Make trading decision based on SMA 20 levels.
        
        Strategy:
        - BUY: Price crosses above SMA 20 (support signal)
        - SELL: Price crosses below SMA 20 (resistance signal) or take profit/stop loss
        """
        if bid <= 0 or ask <= 0:
            return "HOLD", 0
        
        if len(mid_prices) < 21:  # Need 20 bars to calculate SMA + 1 for current
            return "HOLD", 0
        
        # Check current position
        has_position = (
            symbol in portfolio.positions and portfolio.positions[symbol].qty > 0
        )
        
        # Calculate SMA 20 from available price data
        sma_20 = sum(mid_prices[-20:]) / 20
        
        # Get previous SMA 20 (or use current if first time)
        previous_sma_20 = self._previous_weighted_sma.get(symbol, sma_20)
        
        # Use mid price for crossover detection
        current_mid = mid_prices[-1]
        previous_mid = mid_prices[-2] if len(mid_prices) >= 2 else mid_prices[-1]
        
        was_above = previous_mid > previous_sma_20
        is_above = current_mid > sma_20
        
        # Store current SMA 20 for next iteration
        self._previous_weighted_sma[symbol] = sma_20
        
        # === BUY SIGNALS (only when not holding) ===
        if not has_position:
            # Buy: Price crosses above SMA 20
            if not was_above and is_above:
                if ask > sma_20:  # Confirm we can buy above SMA
                    return "BUY", 1
        
        # === SELL SIGNALS (only when holding) ===
        if has_position:
            qty = portfolio.positions[symbol].qty
            entry_price = portfolio.positions[symbol].avg_price
            
            # Sell: Price crosses below SMA 20
            if was_above and not is_above:
                return "SELL", qty
            
            # Take profit: 5% gain
            profit_pct = (bid - entry_price) / entry_price * 100
            if profit_pct > 5:
                return "SELL", qty
            
            # Stop loss: -3% loss
            if profit_pct < -3:
                return "SELL", qty
        
        return "HOLD", 0
