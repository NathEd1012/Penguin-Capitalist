# penguins/sma20_multitimeframe_penguin.py
from typing import List, Tuple, Dict
from penguins.base_penguin import BasePenguin


class SMA20MultiTimeframePenguin(BasePenguin):
    """
    SMA 20 Multi-Timeframe Trading Strategy
    
    Analyzes SMA 20 from historical data at 3 timeframes (daily, weekly, monthly)
    Uses SMA lines as support/resistance levels:
    - Above SMA: Price supported, expect bounce up (HOPE for support)
    - Below SMA: Price below resistance, expect push down (FEAR resistance)
    
    Trading Logic:
    - BUY: Price crosses above any SMA line (support signal)
    - SELL: Price crosses below any SMA line (resistance signal) or take profit
    """
    
    def __init__(self):
        super().__init__("SMA20MultiTimeframePenguin")
        
        # Store SMA lines from historical analysis
        self.sma_levels: Dict[str, Dict[str, float]] = {}  # {symbol: {timeframe: sma_value}}
        self._initialized = False
        self._last_positions: Dict[str, bool] = {}  # Track if we were above/below SMA
        
    def initialize_sma_levels(self, symbols: List[str], data_client):
        """
        Initialize SMA 20 levels from historical data at multiple timeframes.
        Call this once at the start of the simulation.
        """
        if self._initialized:
            return
        
        print(f"\n📊 {self.name}: Analyzing SMA 20 from multi-timeframe historical data...")
        
        for symbol in symbols:
            print(f"  Fetching historical data for {symbol}...")
            
            # Fetch historical data at multiple timeframes
            hist_data = data_client.get_multi_timeframe_history(symbol)
            
            self.sma_levels[symbol] = {}
            
            # Calculate SMA 20 for each timeframe
            for timeframe, prices in hist_data.items():
                if not prices or len(prices) < 20:
                    print(f"    ⚠️ {timeframe}: Insufficient data ({len(prices)} bars, need 20+)")
                    self.sma_levels[symbol][timeframe] = None
                    continue
                
                # Calculate SMA 20 (last 20 values)
                sma_20 = sum(prices[-20:]) / 20
                self.sma_levels[symbol][timeframe] = sma_20
                
                current_price = prices[-1]
                position = "ABOVE" if current_price > sma_20 else "BELOW"
                distance_pct = abs(current_price - sma_20) / sma_20 * 100
                
                print(f"    ✓ {timeframe}: SMA20=${sma_20:.2f}, Current=${current_price:.2f} ({position}, {distance_pct:.1f}%)")
                self._last_positions[f"{symbol}_{timeframe}"] = current_price > sma_20
        
        self._initialized = True
        print(f"✓ SMA 20 initialization complete\n")
    
    def decide(self, symbol: str, mid_prices: List[float], bid: float, ask: float, portfolio) -> Tuple[str, int]:
        """
        Make trading decision based on price position relative to SMA 20 levels.
        
        Strategy:
        - BUY: Price is above all SMA lines (support from all timeframes)
        - SELL: Price is below any critical SMA line (resistance signal)
        """
        if not self._initialized or symbol not in self.sma_levels:
            return "HOLD", 0
        
        if len(mid_prices) < 2:
            return "HOLD", 0
        
        current_price = mid_prices[-1]
        previous_price = mid_prices[-2]
        sma_data = self.sma_levels[symbol]
        
        # Collect valid SMA levels for this symbol
        valid_smas = {tf: sma for tf, sma in sma_data.items() if sma is not None}
        
        if not valid_smas:
            return "HOLD", 0
        
        # Get the strongest support/resistance (combination of all timeframes)
        # Weight: daily (40%), weekly (35%), monthly (25%)
        weights = {"daily": 0.40, "weekly": 0.35, "monthly": 0.25}
        weighted_sma = sum(
            sma * weights.get(tf, 0)
            for tf, sma in valid_smas.items()
        ) / sum(weights.get(tf, 0) for tf in valid_smas.keys())
        
        # Check position relative to weighted SMA
        was_above = previous_price > weighted_sma
        is_above = current_price > weighted_sma
        
        # Check position relative to each timeframe
        daily_sma = valid_smas.get("daily")
        weekly_sma = valid_smas.get("weekly")
        monthly_sma = valid_smas.get("monthly")
        
        # === BUY SIGNALS ===
        # Strong buy: Price crosses above the weighted SMA from below
        if not was_above and is_above:
            print(f"    🟢 {symbol}: Price crossed ABOVE SMA (support) from ${previous_price:.2f} to ${current_price:.2f}")
            return "BUY", 1
        
        # Medium buy: Price bounces from daily SMA
        if daily_sma and current_price > daily_sma and previous_price <= daily_sma:
            if weekly_sma and current_price > weekly_sma * 0.95:  # Not too far below weekly
                print(f"    🟢 {symbol}: Price bounced from daily SMA (${daily_sma:.2f})")
                return "BUY", 1
        
        # === SELL SIGNALS ===
        # Check if we have a position
        has_position = (
            symbol in portfolio.positions and portfolio.positions[symbol].qty > 0
        )
        
        if has_position:
            # Get entry price
            entry_price = portfolio.positions[symbol].avg_price
            
            # Strong sell: Price crosses below weighted SMA
            if was_above and not is_above:
                print(f"    🔴 {symbol}: Price crossed BELOW SMA (resistance) from ${previous_price:.2f} to ${current_price:.2f}")
                qty = portfolio.positions[symbol].qty
                return "SELL", qty
            
            # Sell if price breaks below monthly SMA significantly
            if monthly_sma and current_price < monthly_sma * 0.98:
                qty = portfolio.positions[symbol].qty
                print(f"    🔴 {symbol}: Price broke below monthly SMA (${monthly_sma:.2f})")
                return "SELL", qty
            
            # Take profit: If price is significantly above entry
            profit_pct = (current_price - entry_price) / entry_price * 100
            if profit_pct > 5:  # 5% profit target
                qty = portfolio.positions[symbol].qty
                print(f"    🟡 {symbol}: Taking profit (+{profit_pct:.1f}%)")
                return "SELL", qty
            
            # Stop loss: If price is significantly below entry
            loss_pct = (current_price - entry_price) / entry_price * 100
            if loss_pct < -3:  # 3% stop loss
                qty = portfolio.positions[symbol].qty
                print(f"    🟡 {symbol}: Stopping loss ({loss_pct:.1f}%)")
                return "SELL", qty
        
        return "HOLD", 0
