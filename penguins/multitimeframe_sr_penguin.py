# penguins/multitimeframe_sr_penguin.py
"""Multi-timeframe Support/Resistance Line-based trading strategy with adaptive recalculation."""
from typing import List, Tuple, Dict, Optional
from penguins.base_penguin import BasePenguin


class MultitimeframeRangeSRPenguin(BasePenguin):
    """
    Multi-timeframe Support/Resistance Line-based trading strategy.
    
    Maintains S/R lines across multiple time horizons:
    - 1 year (1-day candles)
    - 3 months (1-day candles)
    - 1 month (1-day candles)
    - 1 week (1-hour candles)
    - 1 day (15-minute candles)
    
    S/R lines are recomputed only when a configurable threshold (default 20%) 
    of the timeframe period has passed since the last computation.
    """
    
    def __init__(
        self,
        recalc_threshold_pct: float = 0.20,  # Recalculate when 20% of timeframe has passed
    ):
        super().__init__("MultitimeframeRangeSRPenguin")
        self.recalc_threshold_pct = recalc_threshold_pct
        
        # Multi-timeframe configuration
        # Format: {name: (lookback_bars, bar_size_minutes)}
        # Assuming data comes in 1-minute bars
        self.timeframes = {
            "1y": (252 * 390, 390),      # 1 year: ~252 trading days, use daily (390 min) candles
            "3m": (63 * 390, 390),       # 3 months: ~63 trading days, use daily candles
            "1m": (21 * 390, 390),       # 1 month: ~21 trading days, use daily candles
            "1w": (5 * 390, 60),         # 1 week: 5 trading days, use hourly (60 min) candles
            "1d": (390, 15),             # 1 day: 390 minutes, use 15-minute candles
        }
        
        # Cache structure per symbol:
        # {symbol: {
        #     "lines": {timeframe: {"support": float, "resistance": float}},
        #     "last_bar_count": {timeframe: int},  # Bar count when last computed
        # }}
        self.cache: Dict[str, Dict] = {}

        # Per-symbol history of S/R lines captured each decision step.
        # Format: {symbol: [{"price": float, "1y_support": float|None, ...}, ...]}
        self.sr_history: Dict[str, List[Dict[str, Optional[float]]]] = {}

    def _record_sr_snapshot(self, symbol: str, current_price: float) -> None:
        """Record current multi-timeframe S/R lines for plotting after the run."""
        if symbol not in self.sr_history:
            self.sr_history[symbol] = []

        symbol_lines = self.cache.get(symbol, {}).get("lines", {})
        snapshot: Dict[str, Optional[float]] = {"price": current_price}

        for tf_name in self.timeframes.keys():
            tf_lines = symbol_lines.get(tf_name, {})
            snapshot[f"{tf_name}_support"] = tf_lines.get("support")
            snapshot[f"{tf_name}_resistance"] = tf_lines.get("resistance")

        self.sr_history[symbol].append(snapshot)

    def export_sr_history(self) -> Dict[str, List[Dict[str, Optional[float]]]]:
        """Return captured S/R line history for all symbols."""
        return self.sr_history
    
    def _resample_to_candles(
        self, 
        prices: List[float], 
        candle_size: int
    ) -> List[Tuple[float, float, float, float]]:
        """
        Resample 1-minute price data into larger candles.
        
        Args:
            prices: List of 1-minute prices
            candle_size: Size of candle in minutes
            
        Returns:
            List of (open, high, low, close) tuples
        """
        if candle_size == 1 or len(prices) < candle_size:
            # Return as-is if already at target resolution or insufficient data
            return [(p, p, p, p) for p in prices]
        
        candles = []
        for i in range(0, len(prices), candle_size):
            chunk = prices[i:i + candle_size]
            if not chunk:
                continue
            
            open_price = chunk[0]
            high_price = max(chunk)
            low_price = min(chunk)
            close_price = chunk[-1]
            
            candles.append((open_price, high_price, low_price, close_price))
        
        return candles
    
    def _compute_sr_lines(
        self, 
        prices: List[float], 
        candle_size: int
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Compute support and resistance lines for a given price history.
        
        Uses a simple approach:
        - Support = lowest low in the period
        - Resistance = highest high in the period
        
        Args:
            prices: List of 1-minute prices
            candle_size: Size of candle in minutes for analysis
            
        Returns:
            (support_line, resistance_line) or (None, None) if insufficient data
        """
        if len(prices) < 10:
            return None, None
        
        # Resample to appropriate candle size
        candles = self._resample_to_candles(prices, candle_size)
        
        if not candles:
            return None, None
        
        # Extract highs and lows
        highs = [c[1] for c in candles]  # High is index 1
        lows = [c[2] for c in candles]   # Low is index 2
        
        support = min(lows)
        resistance = max(highs)
        
        return support, resistance
    
    def _should_recalculate(
        self, 
        timeframe_name: str, 
        current_bar_count: int, 
        last_bar_count: int,
        lookback_bars: int
    ) -> bool:
        """
        Check if enough time has passed to warrant recalculation.
        
        Args:
            timeframe_name: Name of the timeframe
            current_bar_count: Current number of bars
            last_bar_count: Bar count at last calculation
            lookback_bars: Total bars in this timeframe
            
        Returns:
            True if recalculation should happen
        """
        bars_passed = current_bar_count - last_bar_count
        threshold = lookback_bars * self.recalc_threshold_pct
        
        return bars_passed >= threshold
    
    def _update_lines_for_symbol(
        self, 
        symbol: str, 
        mid_prices: List[float]
    ) -> None:
        """
        Update S/R lines for a symbol across all timeframes.
        Only recalculates when the threshold percentage of the timeframe has passed.
        """
        if symbol not in self.cache:
            self.cache[symbol] = {
                "lines": {},
                "last_bar_count": {},
            }
        
        current_bar_count = len(mid_prices)
        
        for tf_name, (lookback_bars, candle_size) in self.timeframes.items():
            # Check if we need to recalculate
            last_bar_count = self.cache[symbol]["last_bar_count"].get(tf_name, 0)
            
            # First time or enough time has passed
            if last_bar_count == 0 or self._should_recalculate(
                tf_name, current_bar_count, last_bar_count, lookback_bars
            ):
                # Check if we have enough data for this timeframe
                if current_bar_count < lookback_bars:
                    # Use all available data if we don't have full lookback yet
                    prices_for_tf = mid_prices
                else:
                    prices_for_tf = mid_prices[-lookback_bars:]
                
                # Compute S/R lines
                support, resistance = self._compute_sr_lines(prices_for_tf, candle_size)
                
                if support is not None and resistance is not None:
                    self.cache[symbol]["lines"][tf_name] = {
                        "support": support,
                        "resistance": resistance,
                    }
                    self.cache[symbol]["last_bar_count"][tf_name] = current_bar_count
    
    def _get_trading_signals(
        self, 
        symbol: str, 
        current_price: float
    ) -> Dict[str, str]:
        """
        Analyze current price position relative to S/R lines across timeframes.
        
        Returns:
            Dict mapping timeframe names to signals: "ABOVE_R", "NEAR_R", "BETWEEN", "NEAR_S", "BELOW_S"
        """
        if symbol not in self.cache or not self.cache[symbol]["lines"]:
            return {}
        
        signals = {}
        
        for tf_name, lines in self.cache[symbol]["lines"].items():
            support = lines["support"]
            resistance = lines["resistance"]
            
            if support >= resistance:
                continue
            
            range_size = resistance - support
            
            # Determine position
            if current_price > resistance:
                # Price above resistance (breakout)
                distance_pct = (current_price - resistance) / range_size * 100
                if distance_pct < 5:
                    signals[tf_name] = "NEAR_R_ABOVE"
                else:
                    signals[tf_name] = "ABOVE_R"
            elif current_price < support:
                # Price below support (breakdown)
                distance_pct = (support - current_price) / range_size * 100
                if distance_pct < 5:
                    signals[tf_name] = "NEAR_S_BELOW"
                else:
                    signals[tf_name] = "BELOW_S"
            else:
                # Price between support and resistance
                distance_to_support = (current_price - support) / range_size
                
                if distance_to_support < 0.15:
                    signals[tf_name] = "NEAR_S"
                elif distance_to_support > 0.85:
                    signals[tf_name] = "NEAR_R"
                else:
                    signals[tf_name] = "BETWEEN"
        
        return signals
    
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
        
        # Update S/R lines (adaptive recalculation)
        self._update_lines_for_symbol(symbol, mid_prices)

        # Record lines for visualization across the entire run.
        self._record_sr_snapshot(symbol, current_price)
        
        # Get signals from all timeframes
        signals = self._get_trading_signals(symbol, current_price)
        
        if not signals:
            return "HOLD", 0
        
        # Check position status
        has_position = (
            symbol in portfolio.positions and
            portfolio.positions[symbol].qty > 0
        )
        
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
            qty = portfolio.positions[symbol].qty
            entry_price = portfolio.positions[symbol].avg_price
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
