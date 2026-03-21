# penguins/sma20_penguin.py
from typing import Dict, List, Tuple
from penguins.base_penguin import BasePenguin


class SMA20MultiTimeframePenguin(BasePenguin):
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
        fast_sma_length: int = 20,
        trend_sma_length: int = 50,
        min_distance_pct: float = 0.002,
        stop_loss_pct: float = 0.03,
    ):
        super().__init__("SMA20MultiTimeframePenguin")
        self.fast_sma_length = fast_sma_length
        self.trend_sma_length = trend_sma_length
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


class SMA20Penguin(SMA20MultiTimeframePenguin):
    """Compatibility alias for existing imports/configuration."""

    pass
