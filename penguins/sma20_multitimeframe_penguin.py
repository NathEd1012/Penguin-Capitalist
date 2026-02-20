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
        Make trading decision based on dynamically calculated SMA 20 levels.
        
        Strategy:
        - BUY: Price crosses above weighted SMA (support signal), only when not holding
        - SELL: Price crosses below weighted SMA (resistance signal) or take profit/stop loss
        """
        if bid <= 0 or ask <= 0:
            return "HOLD", 0
        
        if not self.data_client:
            return "HOLD", 0
        
        if len(mid_prices) < 2:
            return "HOLD", 0
        
        # Check current position
        has_position = (
            symbol in portfolio.positions and portfolio.positions[symbol].qty > 0
        )
        
        # Recalculate SMA levels dynamically
        sma_levels = self._calculate_sma_levels(symbol)
        if not sma_levels:
            return "HOLD", 0
        
        weighted_sma = self._calculate_weighted_sma(sma_levels)
        if weighted_sma == 0.0:
            return "HOLD", 0
        
        # Detect crossover using consistent price basis
        current_buy_price = ask
        current_sell_price = bid
        
        # Get previous weighted SMA (or use current if first time)
        previous_weighted_sma = self._previous_weighted_sma.get(symbol, weighted_sma)
        
        # Use mid price for crossover detection (consistent with historical data)
        current_mid = mid_prices[-1]
        previous_mid = mid_prices[-2]
        
        was_above = previous_mid > previous_weighted_sma
        is_above = current_mid > weighted_sma
        
        # Store current weighted SMA for next iteration
        self._previous_weighted_sma[symbol] = weighted_sma
        
        # === BUY SIGNALS (only when not holding) ===
        if not has_position:
            # Strong buy: Price crosses above weighted SMA
            if not was_above and is_above and current_buy_price > weighted_sma:
                print(f"    🟢 {symbol}: Price crossed ABOVE SMA (${weighted_sma:.2f}) - BUY at ${current_buy_price:.2f}")
                return "BUY", 1
            
            # Bounce from daily SMA (when weekly is supportive)
            daily_sma = sma_levels.get("daily")
            weekly_sma = sma_levels.get("weekly")
            if daily_sma and weekly_sma:
                if previous_mid <= daily_sma and current_mid > daily_sma:
                    if current_buy_price > weekly_sma * 0.95:  # Not too far below weekly
                        print(f"    🟢 {symbol}: Bounced from daily SMA (${daily_sma:.2f}) - BUY at ${current_buy_price:.2f}")
                        return "BUY", 1
        
        # === SELL SIGNALS (only when holding) ===
        if has_position:
            qty = portfolio.positions[symbol].qty
            entry_price = portfolio.positions[symbol].avg_price
            
            # Strong sell: Price crosses below weighted SMA
            if was_above and not is_above and current_sell_price < weighted_sma:
                print(f"    🔴 {symbol}: Price crossed BELOW SMA (${weighted_sma:.2f}) - SELL at ${current_sell_price:.2f}")
                return "SELL", qty
            
            # Sell if price breaks below monthly SMA significantly
            monthly_sma = sma_levels.get("monthly")
            if monthly_sma and current_sell_price < monthly_sma * 0.98:
                print(f"    🔴 {symbol}: Broke below monthly SMA (${monthly_sma:.2f}) - SELL at ${current_sell_price:.2f}")
                return "SELL", qty
            
            # Take profit: 5% gain
            profit_pct = (current_sell_price - entry_price) / entry_price * 100
            if profit_pct > 5:
                print(f"    🟡 {symbol}: Taking profit (+{profit_pct:.1f}%) - SELL at ${current_sell_price:.2f}")
                return "SELL", qty
            
            # Stop loss: -3% loss
            if profit_pct < -3:
                print(f"    🟡 {symbol}: Stop loss ({profit_pct:.1f}%) - SELL at ${current_sell_price:.2f}")
                return "SELL", qty
        
        return "HOLD", 0
