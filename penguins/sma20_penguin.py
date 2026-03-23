# penguins/sma20_penguin.py
from typing import Dict, List, Tuple
from penguins.base_penguin import BasePenguin

# Change this single value to run as SMA20 / SMA50 / SMA100 strategy.
PRIMARY_SMA_LENGTH = 20
TREND_SMA_MULTIPLIER = 2.5


class SMA20Penguin(BasePenguin):
    """
    Improved SMA(20) crossover strategy with light robustness filters.

    Core idea remains unchanged:
    - BUY when price crosses above fast SMA while flat
    - SELL when price crosses below fast SMA while in position

    Improvements:
    - Trend filter with SMA(50) for long entries
    - Two-bar crossover confirmation
    - Minimum distance from fast SMA on entry
    - Trailing stop loss based on highest price since entry
    """

    def __init__(
        self,
        fast_sma_length: int = PRIMARY_SMA_LENGTH,
        trend_sma_length: int = None,
        min_distance_pct: float = 0.002,
        stop_loss_pct: float = 0.03,
    ):
        super().__init__("SMA20Penguin")
        self.fast_sma_length = fast_sma_length
        self.trend_sma_length = (
            trend_sma_length
            if trend_sma_length is not None
            else max(self.fast_sma_length + 1, int(round(self.fast_sma_length * TREND_SMA_MULTIPLIER)))
        )
        self.min_distance_pct = min_distance_pct
        self.stop_loss_pct = stop_loss_pct

        # Fallback entry tracking when portfolio does not expose average entry price.
        self._entry_prices: Dict[str, float] = {}
        self._highest_prices_since_entry: Dict[str, float] = {}

    def _compute_sma(self, prices: List[float], length: int) -> float:
        return sum(prices[-length:]) / length

    def _crossed_up_confirmed(self, prices: List[float], sma_length: int) -> bool:
        """Two-bar confirmation: <= SMA, then > SMA, then still > SMA."""
        if len(prices) < sma_length + 2:
            return False

        p_two_back = prices[-3]
        p_one_back = prices[-2]
        p_now = prices[-1]

        sma_two_back = sum(prices[-(sma_length + 2):-2]) / sma_length
        sma_one_back = sum(prices[-(sma_length + 1):-1]) / sma_length
        sma_now = self._compute_sma(prices, sma_length)

        return (
            p_two_back <= sma_two_back
            and p_one_back > sma_one_back
            and p_now > sma_now
        )

    def _crossed_down_confirmed(self, prices: List[float], sma_length: int) -> bool:
        """Practical bearish confirmation used for exits."""
        if len(prices) < sma_length + 2:
            return False

        p_two_back = prices[-3]
        p_one_back = prices[-2]
        p_now = prices[-1]

        sma_two_back = sum(prices[-(sma_length + 2):-2]) / sma_length
        sma_one_back = sum(prices[-(sma_length + 1):-1]) / sma_length
        sma_now = self._compute_sma(prices, sma_length)

        return (
            p_two_back >= sma_two_back
            and p_one_back < sma_one_back
            and p_now < sma_now
        )

    def _hit_stop_loss(self, highest_price_since_entry: float, current_exit_price: float) -> bool:
        stop_price = highest_price_since_entry * (1.0 - self.stop_loss_pct)
        return current_exit_price <= stop_price

    def _passes_trend_filter(self, current_price: float, trend_sma: float) -> bool:
        return current_price > trend_sma

    def _passes_distance_filter(self, current_price: float, signal_sma: float) -> bool:
        if signal_sma <= 0:
            return False
        distance_pct = (current_price - signal_sma) / signal_sma
        return distance_pct >= self.min_distance_pct

    def decide(self, symbol: str, mid_prices: List[float], bid: float, ask: float, portfolio) -> Tuple[str, int]:
        """Return (action, quantity) based on robust SMA crossover logic."""
        if bid <= 0 or ask <= 0:
            return "HOLD", 0

        min_required = max(self.trend_sma_length, self.fast_sma_length + 2)
        if len(mid_prices) < min_required:
            return "HOLD", 0

        position_qty = portfolio.get_position(symbol)
        has_position = position_qty > 0

        current_mid = mid_prices[-1]
        fast_sma_now = self._compute_sma(mid_prices, self.fast_sma_length)
        trend_sma_now = self._compute_sma(mid_prices, self.trend_sma_length)

        # Keep entry bookkeeping aligned if we detect an external flat position.
        if not has_position and symbol in self._entry_prices:
            self._entry_prices.pop(symbol, None)
            self._highest_prices_since_entry.pop(symbol, None)

        if has_position and symbol not in self._entry_prices:
            # Best-effort fallback if strategy state was reset mid-run.
            self._entry_prices[symbol] = current_mid
            self._highest_prices_since_entry[symbol] = current_mid

        if has_position:
            previous_high = self._highest_prices_since_entry.get(symbol, current_mid)
            current_high = max(previous_high, current_mid)
            self._highest_prices_since_entry[symbol] = current_high

            if self._hit_stop_loss(current_high, bid):
                self._entry_prices.pop(symbol, None)
                self._highest_prices_since_entry.pop(symbol, None)
                return "SELL", position_qty

            if self._crossed_down_confirmed(mid_prices, self.fast_sma_length):
                self._entry_prices.pop(symbol, None)
                self._highest_prices_since_entry.pop(symbol, None)
                return "SELL", position_qty

            return "HOLD", 0

        crossed_up_confirmed = self._crossed_up_confirmed(mid_prices, self.fast_sma_length)
        passes_trend = self._passes_trend_filter(current_mid, trend_sma_now)
        passes_distance = self._passes_distance_filter(current_mid, fast_sma_now)

        if crossed_up_confirmed and passes_trend and passes_distance:
            self._entry_prices[symbol] = ask
            self._highest_prices_since_entry[symbol] = current_mid
            return "BUY", 1

        return "HOLD", 0



class SMA20AdvancedPenguin(SMA20Penguin):
    """
    Advanced SMA20 strategy with strength-based position sizing.

    Keeps the same robust entry/exit logic as SMA20Penguin, but when a bullish
    crossover is especially strong it buys more than one share.
    """

    def __init__(
        self,
        fast_sma_length: int = PRIMARY_SMA_LENGTH,
        trend_sma_length: int = None,
        min_distance_pct: float = 0.002,
        stop_loss_pct: float = 0.03,
        max_buy_qty: int = 4,
        reserve_cash_pct: float = 0.15,
        strong_distance_pct: float = 0.008,
    ):
        super().__init__(
            fast_sma_length=fast_sma_length,
            trend_sma_length=trend_sma_length,
            min_distance_pct=min_distance_pct,
            stop_loss_pct=stop_loss_pct,
        )
        self.name = "SMA20AdvancedPenguin"
        self.max_buy_qty = max_buy_qty
        self.reserve_cash_pct = reserve_cash_pct
        self.strong_distance_pct = strong_distance_pct

    def _compute_fast_sma_previous(self, prices: List[float]) -> float:
        return sum(prices[-(self.fast_sma_length + 1):-1]) / self.fast_sma_length

    def _entry_strength_score(
        self,
        current_mid: float,
        fast_sma_now: float,
        trend_sma_now: float,
        fast_sma_prev: float,
    ) -> int:
        score = 0

        if fast_sma_now > 0:
            dist_fast = (current_mid - fast_sma_now) / fast_sma_now
            if dist_fast >= self.min_distance_pct:
                score += 1
            if dist_fast >= self.strong_distance_pct:
                score += 1

        if trend_sma_now > 0:
            dist_trend = (current_mid - trend_sma_now) / trend_sma_now
            if dist_trend >= 0.005:
                score += 1
            if dist_trend >= 0.012:
                score += 1

        if fast_sma_prev > 0:
            fast_sma_slope = (fast_sma_now - fast_sma_prev) / fast_sma_prev
            if fast_sma_slope > 0:
                score += 1
            if fast_sma_slope >= 0.002:
                score += 1

        return score

    def _target_buy_qty(self, score: int) -> int:
        if score >= 5:
            return min(self.max_buy_qty, 4)
        if score >= 3:
            return min(self.max_buy_qty, 3)
        if score >= 2:
            return min(self.max_buy_qty, 2)
        return 1

    def decide(self, symbol: str, mid_prices: List[float], bid: float, ask: float, portfolio) -> Tuple[str, int]:
        """Return (action, quantity) using robust SMA logic with dynamic buy size."""
        if bid <= 0 or ask <= 0:
            return "HOLD", 0

        min_required = max(self.trend_sma_length, self.fast_sma_length + 2)
        if len(mid_prices) < min_required:
            return "HOLD", 0

        position_qty = portfolio.get_position(symbol)
        has_position = position_qty > 0

        current_mid = mid_prices[-1]
        fast_sma_now = self._compute_sma(mid_prices, self.fast_sma_length)
        trend_sma_now = self._compute_sma(mid_prices, self.trend_sma_length)

        if not has_position and symbol in self._entry_prices:
            self._entry_prices.pop(symbol, None)
            self._highest_prices_since_entry.pop(symbol, None)

        if has_position and symbol not in self._entry_prices:
            self._entry_prices[symbol] = current_mid
            self._highest_prices_since_entry[symbol] = current_mid

        if has_position:
            previous_high = self._highest_prices_since_entry.get(symbol, current_mid)
            current_high = max(previous_high, current_mid)
            self._highest_prices_since_entry[symbol] = current_high

            if self._hit_stop_loss(current_high, bid):
                self._entry_prices.pop(symbol, None)
                self._highest_prices_since_entry.pop(symbol, None)
                return "SELL", position_qty

            if self._crossed_down_confirmed(mid_prices, self.fast_sma_length):
                self._entry_prices.pop(symbol, None)
                self._highest_prices_since_entry.pop(symbol, None)
                return "SELL", position_qty

            return "HOLD", 0

        crossed_up_confirmed = self._crossed_up_confirmed(mid_prices, self.fast_sma_length)
        passes_trend = self._passes_trend_filter(current_mid, trend_sma_now)
        passes_distance = self._passes_distance_filter(current_mid, fast_sma_now)

        if crossed_up_confirmed and passes_trend and passes_distance:
            fast_sma_prev = self._compute_fast_sma_previous(mid_prices)
            score = self._entry_strength_score(
                current_mid=current_mid,
                fast_sma_now=fast_sma_now,
                trend_sma_now=trend_sma_now,
                fast_sma_prev=fast_sma_prev,
            )

            target_qty = self._target_buy_qty(score)
            available_cash = max(0.0, portfolio.cash)
            deployable_cash = available_cash * (1.0 - self.reserve_cash_pct)
            affordable_qty = int(deployable_cash // ask)

            buy_qty = min(target_qty, affordable_qty)
            if buy_qty <= 0:
                return "HOLD", 0

            self._entry_prices[symbol] = ask
            self._highest_prices_since_entry[symbol] = current_mid
            return "BUY", buy_qty

        return "HOLD", 0