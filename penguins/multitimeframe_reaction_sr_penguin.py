# penguins/multitimeframe_reaction_sr_penguin.py
"""Multi-timeframe reaction-based Support/Resistance line strategy."""
from typing import Dict, List, Optional, Tuple
from penguins.base_penguin import BasePenguin


class MultitimeframeReactionSRPenguin(BasePenguin):
    """
    Multi-timeframe S/R strategy based on frequently reacting price levels.

    Unlike simple min/max range levels, this strategy:
    - detects local pivot highs/lows,
    - clusters nearby pivots into reaction zones,
    - keeps the strongest (most touched) lines per timeframe.
    """

    def __init__(
        self,
        recalc_threshold_pct: float = 0.20,
        cluster_tolerance_pct: float = 0.006,
        touch_tolerance_pct: float = 0.003,
        max_levels_per_timeframe: int = 3,
    ):
        super().__init__("MultitimeframeReactionSRPenguin")
        self.recalc_threshold_pct = recalc_threshold_pct
        self.cluster_tolerance_pct = cluster_tolerance_pct
        self.touch_tolerance_pct = touch_tolerance_pct
        self.max_levels_per_timeframe = max_levels_per_timeframe

        # Assuming 1-minute input bars.
        self.timeframes = {
            "1y": (252 * 390, 390),
            "3m": (63 * 390, 390),
            "1m": (21 * 390, 390),
            "1w": (5 * 390, 60),
            "1d": (390, 15),
        }

        # {symbol: {"levels": {tf: [line_prices]}, "last_bar_count": {tf: int}}}
        self.cache: Dict[str, Dict] = {}

        # Per-symbol history for plotting.
        self.sr_history: Dict[str, List[Dict[str, Optional[float]]]] = {}
        
        # Track when positions were entered (for time-based exit)
        self._position_entry_bar: Dict[str, int] = {}

    def _resample_to_candles(self, prices: List[float], candle_size: int) -> List[Tuple[float, float, float, float]]:
        if candle_size == 1 or len(prices) < candle_size:
            return [(p, p, p, p) for p in prices]

        candles = []
        for i in range(0, len(prices), candle_size):
            chunk = prices[i:i + candle_size]
            if not chunk:
                continue
            candles.append((chunk[0], max(chunk), min(chunk), chunk[-1]))
        return candles

    def _extract_pivots(self, candles: List[Tuple[float, float, float, float]], window: int = 2) -> List[float]:
        if len(candles) < (window * 2 + 1):
            return []

        highs = [c[1] for c in candles]
        lows = [c[2] for c in candles]
        pivots: List[float] = []

        for i in range(window, len(candles) - window):
            left_h = highs[i - window:i]
            right_h = highs[i + 1:i + 1 + window]
            left_l = lows[i - window:i]
            right_l = lows[i + 1:i + 1 + window]

            if highs[i] >= max(left_h) and highs[i] >= max(right_h):
                pivots.append(highs[i])
            if lows[i] <= min(left_l) and lows[i] <= min(right_l):
                pivots.append(lows[i])

        return pivots

    def _cluster_levels(self, raw_levels: List[float]) -> List[Tuple[float, int]]:
        if not raw_levels:
            return []

        levels = sorted(raw_levels)
        clusters: List[List[float]] = [[levels[0]]]

        for level in levels[1:]:
            center = sum(clusters[-1]) / len(clusters[-1])
            if center <= 0:
                continue
            if abs(level - center) / center <= self.cluster_tolerance_pct:
                clusters[-1].append(level)
            else:
                clusters.append([level])

        clustered = []
        for cluster in clusters:
            center = sum(cluster) / len(cluster)
            touches = len(cluster)
            clustered.append((center, touches))

        # Most reacted lines first.
        clustered.sort(key=lambda x: (-x[1], x[0]))
        return clustered

    def _compute_reaction_levels(self, prices: List[float], candle_size: int) -> List[float]:
        if len(prices) < 20:
            return []

        candles = self._resample_to_candles(prices, candle_size)
        if len(candles) < 7:
            return []

        pivots = self._extract_pivots(candles, window=2)
        clustered = self._cluster_levels(pivots)

        if not clustered:
            return []

        top = clustered[:self.max_levels_per_timeframe]
        return sorted([lvl for lvl, _ in top])

    def _should_recalculate(self, current_bar_count: int, last_bar_count: int, lookback_bars: int) -> bool:
        bars_passed = current_bar_count - last_bar_count
        threshold = lookback_bars * self.recalc_threshold_pct
        return bars_passed >= threshold

    def _update_levels_for_symbol(self, symbol: str, mid_prices: List[float]) -> None:
        if symbol not in self.cache:
            self.cache[symbol] = {"levels": {}, "last_bar_count": {}}

        current_bar_count = len(mid_prices)

        for tf_name, (lookback_bars, candle_size) in self.timeframes.items():
            last_bar_count = self.cache[symbol]["last_bar_count"].get(tf_name, 0)
            if last_bar_count != 0 and not self._should_recalculate(current_bar_count, last_bar_count, lookback_bars):
                continue

            prices_for_tf = mid_prices[-lookback_bars:] if current_bar_count >= lookback_bars else mid_prices
            levels = self._compute_reaction_levels(prices_for_tf, candle_size)
            if levels:
                self.cache[symbol]["levels"][tf_name] = levels
                self.cache[symbol]["last_bar_count"][tf_name] = current_bar_count

    def _record_sr_snapshot(self, symbol: str, current_price: float) -> None:
        if symbol not in self.sr_history:
            self.sr_history[symbol] = []

        row: Dict[str, Optional[float]] = {"price": current_price}
        symbol_levels = self.cache.get(symbol, {}).get("levels", {})

        for tf_name in self.timeframes.keys():
            levels = symbol_levels.get(tf_name, [])
            for i in range(self.max_levels_per_timeframe):
                key = f"{tf_name}_line_{i+1}"
                row[key] = levels[i] if i < len(levels) else None

        self.sr_history[symbol].append(row)

    def export_sr_history(self) -> Dict[str, List[Dict[str, Optional[float]]]]:
        return self.sr_history

    def _nearest_line(self, symbol: str, current_price: float) -> Optional[float]:
        symbol_levels = self.cache.get(symbol, {}).get("levels", {})
        all_levels: List[float] = []
        for tf_levels in symbol_levels.values():
            all_levels.extend(tf_levels)

        if not all_levels:
            return None

        return min(all_levels, key=lambda lvl: abs(lvl - current_price))

    def _get_fallback_sr(self, mid_prices: List[float]) -> Tuple[Optional[float], Optional[float]]:
        """Fallback: simple 20-bar min/max if reaction levels not available."""
        if len(mid_prices) < 20:
            return None, None
        recent = mid_prices[-20:]
        return min(recent), max(recent)

    def decide(self, symbol: str, mid_prices: List[float], bid: float, ask: float, portfolio) -> Tuple[str, int]:
        if bid <= 0 or ask <= 0:
            return "HOLD", 0
        if len(mid_prices) < 50:
            return "HOLD", 0

        current_price = mid_prices[-1]
        previous_price = mid_prices[-2]

        self._update_levels_for_symbol(symbol, mid_prices)
        self._record_sr_snapshot(symbol, current_price)

        nearest_line = self._nearest_line(symbol, current_price)
        
        # Fallback to simple recent min/max if reaction levels not available
        if nearest_line is None or nearest_line <= 0:
            fallback_support, fallback_resistance = self._get_fallback_sr(mid_prices)
            if fallback_support is None or fallback_resistance is None:
                return "HOLD", 0
            # Use fallback: treat support/resistance as two target lines
            if current_price < (fallback_support + fallback_resistance) / 2:
                nearest_line = fallback_support
            else:
                nearest_line = fallback_resistance

        dist_now = abs(current_price - nearest_line) / nearest_line if nearest_line > 0 else 999
        dist_prev = abs(previous_price - nearest_line) / nearest_line if nearest_line > 0 else 999
        near_line_now = dist_now <= self.touch_tolerance_pct
        just_touched = near_line_now and dist_prev > self.touch_tolerance_pct

        has_position = symbol in portfolio.positions and portfolio.positions[symbol].qty > 0

        # Entry: reaction touch with upward bounce
        if just_touched and current_price > previous_price and portfolio.cash >= ask:
            self._position_entry_bar[symbol] = len(mid_prices)
            return "BUY", 1

        # Entry: also buy if trending up away from recent low (momentum entry)
        if not has_position and len(mid_prices) >= 5:
            short_momentum = (current_price - mid_prices[-5]) / mid_prices[-5] if mid_prices[-5] > 0 else 0
            if short_momentum > 0.003 and portfolio.cash >= ask:  # 0.3% momentum
                self._position_entry_bar[symbol] = len(mid_prices)
                return "BUY", 1

        if has_position:
            qty = portfolio.positions[symbol].qty
            entry_price = portfolio.positions[symbol].avg_price
            profit_pct = (current_price - entry_price) / entry_price * 100 if entry_price > 0 else 0.0

            # Sell conditions: aggressive exit to enable repeated cycles
            # 1. Exit on reaction touch with downward rejection  
            if just_touched and current_price < previous_price:
                self._position_entry_bar.pop(symbol, None)
                return "SELL", qty
            
            # 2. Profit target (lower threshold for more frequent exits)
            if profit_pct >= 4:
                self._position_entry_bar.pop(symbol, None)
                return "SELL", qty
            
            # 3. Stop loss
            if profit_pct <= -4:
                self._position_entry_bar.pop(symbol, None)
                return "SELL", qty
            
            # 4. Time-based exit: if held >200 bars without profit, sell
            if symbol in self._position_entry_bar:
                bars_held = len(mid_prices) - self._position_entry_bar[symbol]
                if bars_held > 200 and profit_pct > -2:
                    self._position_entry_bar.pop(symbol, None)
                    return "SELL", qty

        return "HOLD", 0
