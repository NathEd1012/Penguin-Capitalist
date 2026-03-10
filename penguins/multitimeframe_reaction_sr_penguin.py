"""Multi-timeframe reaction-based Support/Resistance line strategy."""

from typing import Dict, List, Optional, Tuple

from indicators.multitimeframe_sr import (
    DEFAULT_TIMEFRAMES,
    compute_range_sr_lines,
    nearest_reaction_level,
    record_reaction_snapshot,
    update_reaction_level_cache,
)
from penguins.base_penguin import BasePenguin


class MultitimeframeReactionSRPenguin(BasePenguin):
    """Decision model using reaction-based S/R levels from indicators."""
    USES_SR_LINES = True

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
        self.record_history = True

        self.timeframes = dict(DEFAULT_TIMEFRAMES)

        # {symbol: {"levels": {tf: [line_prices]}, "last_bar_count": {tf: int}}}
        self.cache: Dict[str, Dict] = {}

        # Per-symbol history for plotting.
        self.sr_history: Dict[str, List[Dict[str, Optional[float]]]] = {}
        
        # Track when positions were entered (for time-based exit)
        self._position_entry_bar: Dict[str, int] = {}

    def export_sr_history(self) -> Dict[str, List[Dict[str, Optional[float]]]]:
        return self.sr_history

    def _get_fallback_sr(self, mid_prices: List[float]) -> Tuple[Optional[float], Optional[float]]:
        """Fallback: simple 20-bar min/max if reaction levels not available."""
        if len(mid_prices) < 20:
            return None, None
        return compute_range_sr_lines(mid_prices[-20:], candle_size=1)

    def decide(self, symbol: str, mid_prices: List[float], bid: float, ask: float, portfolio) -> Tuple[str, int]:
        if bid <= 0 or ask <= 0:
            return "HOLD", 0
        if len(mid_prices) < 50:
            return "HOLD", 0

        current_price = mid_prices[-1]
        previous_price = mid_prices[-2]

        update_reaction_level_cache(
            cache=self.cache,
            symbol=symbol,
            mid_prices=mid_prices,
            timeframes=self.timeframes,
            recalc_threshold_pct=self.recalc_threshold_pct,
            cluster_tolerance_pct=self.cluster_tolerance_pct,
            max_levels_per_timeframe=self.max_levels_per_timeframe,
        )
        if self.record_history:
            record_reaction_snapshot(
                cache=self.cache,
                sr_history=self.sr_history,
                symbol=symbol,
                current_price=current_price,
                timeframes=self.timeframes,
                max_levels_per_timeframe=self.max_levels_per_timeframe,
            )

        nearest_line = nearest_reaction_level(self.cache, symbol, current_price)
        
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

        has_position = portfolio.get_position(symbol) > 0

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
            qty = portfolio.get_position(symbol)
            entry_price = portfolio.cost_basis.get(symbol, current_price)
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
