from dataclasses import dataclass
import math
from typing import List

from backtest.portfolio import Portfolio
from penguins.base_penguin import BasePenguin
from penguins.trainable_signals import average_relative_strength_return


# Manual tuning block:
TRAINABLE_PENGUIN3_BB_PERIOD = 20
TRAINABLE_PENGUIN3_BB_STDDEV = 2.0
TRAINABLE_PENGUIN3_ADX_PERIOD = 14
TRAINABLE_PENGUIN3_ADX_THRESHOLD = 25.0
TRAINABLE_PENGUIN3_MAX_CASH_FRACTION = 0.05
TRAINABLE_PENGUIN3_RS_LOOKBACK = 5
TRAINABLE_PENGUIN3_RS_SELL_THRESHOLD = 0.0
TRAINABLE_PENGUIN3_MIN_HOLD_BARS = 3
TRAINABLE_PENGUIN3_STOP_LOSS_PCT = 0.04
TRAINABLE_PENGUIN3_TAKE_PROFIT_PCT = 0.08
TRAINABLE_PENGUIN3_COOLDOWN_BARS = 10


@dataclass
class TrainablePenguin3Params:
    bb_period: int = TRAINABLE_PENGUIN3_BB_PERIOD
    bb_stddev: float = TRAINABLE_PENGUIN3_BB_STDDEV
    adx_period: int = TRAINABLE_PENGUIN3_ADX_PERIOD
    adx_threshold: float = TRAINABLE_PENGUIN3_ADX_THRESHOLD
    max_cash_fraction: float = TRAINABLE_PENGUIN3_MAX_CASH_FRACTION
    rs_lookback: int = TRAINABLE_PENGUIN3_RS_LOOKBACK
    rs_sell_threshold: float = TRAINABLE_PENGUIN3_RS_SELL_THRESHOLD
    min_hold_bars: int = TRAINABLE_PENGUIN3_MIN_HOLD_BARS
    stop_loss_pct: float = TRAINABLE_PENGUIN3_STOP_LOSS_PCT
    take_profit_pct: float = TRAINABLE_PENGUIN3_TAKE_PROFIT_PCT
    cooldown_bars: int = TRAINABLE_PENGUIN3_COOLDOWN_BARS


class TrainablePenguin3(BasePenguin):
    """Bollinger/ADX entry and sizing with a Stock/SPY relative-strength exit."""

    LOOKBACK_BARS = 120
    BENCHMARK_SYMBOL = "SPY"
    REQUIRED_CONTEXT_SYMBOLS = {BENCHMARK_SYMBOL}

    def __init__(
        self,
        name: str = "TrainablePenguin3",
        bb_period: int = TRAINABLE_PENGUIN3_BB_PERIOD,
        bb_stddev: float = TRAINABLE_PENGUIN3_BB_STDDEV,
        adx_period: int = TRAINABLE_PENGUIN3_ADX_PERIOD,
        adx_threshold: float = TRAINABLE_PENGUIN3_ADX_THRESHOLD,
        max_cash_fraction_per_trade: float = TRAINABLE_PENGUIN3_MAX_CASH_FRACTION,
        rs_lookback: int = TRAINABLE_PENGUIN3_RS_LOOKBACK,
        rs_sell_threshold: float = TRAINABLE_PENGUIN3_RS_SELL_THRESHOLD,
        min_hold_bars: int = TRAINABLE_PENGUIN3_MIN_HOLD_BARS,
        stop_loss_pct: float = TRAINABLE_PENGUIN3_STOP_LOSS_PCT,
        take_profit_pct: float = TRAINABLE_PENGUIN3_TAKE_PROFIT_PCT,
        cooldown_bars: int = TRAINABLE_PENGUIN3_COOLDOWN_BARS,
    ):
        super().__init__(name)
        self.params = TrainablePenguin3Params(
            bb_period=bb_period,
            bb_stddev=bb_stddev,
            adx_period=adx_period,
            adx_threshold=adx_threshold,
            max_cash_fraction=max_cash_fraction_per_trade,
            rs_lookback=rs_lookback,
            rs_sell_threshold=rs_sell_threshold,
            min_hold_bars=min_hold_bars,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            cooldown_bars=cooldown_bars,
        )
        self._entry_bar_index: dict[str, int] = {}

    def decide(
        self,
        symbol: str,
        mid_prices: List[float],
        bid: float,
        ask: float,
        portfolio: Portfolio,
    ) -> tuple[str, int]:
        if symbol == self.BENCHMARK_SYMBOL:
            return "HOLD", 0

        min_required = max(self.params.bb_period, self.params.adx_period) + 2
        benchmark_prices = self._market_price_history.get(self.BENCHMARK_SYMBOL, ())
        relative_strength = average_relative_strength_return(
            mid_prices,
            benchmark_prices,
            self.params.rs_lookback,
        )
        shares_owned = int(portfolio.get_position(symbol))
        if shares_owned > 0:
            current_bar = len(mid_prices)
            entry_bar = self._entry_bar_index.get(symbol)
            if entry_bar is None:
                self._entry_bar_index[symbol] = current_bar
                entry_bar = current_bar

            bars_held = max(0, current_bar - entry_bar)
            if bars_held < self.params.min_hold_bars:
                return "HOLD", 0

            avg_entry = self._get_avg_entry(portfolio, symbol)
            current_price = bid if bid > 0 else mid_prices[-1]

            stop_loss_trigger = (
                avg_entry is not None
                and current_price <= avg_entry * (1.0 - self.params.stop_loss_pct)
            )
            take_profit_trigger = (
                avg_entry is not None
                and current_price >= avg_entry * (1.0 + self.params.take_profit_pct)
            )
            relative_strength_trigger = (
                relative_strength is not None
                and relative_strength <= self.params.rs_sell_threshold
            )

            if stop_loss_trigger or take_profit_trigger or relative_strength_trigger:
                self._entry_bar_index.pop(symbol, None)
                return "SELL", shares_owned
            return "HOLD", 0

        if bid <= 0 or ask <= 0 or len(mid_prices) < min_required or relative_strength is None:
            return "HOLD", 0

        _, middle_band, lower_band = self._bollinger_bands(
            mid_prices,
            self.params.bb_period,
            self.params.bb_stddev,
        )
        adx_value = self._adx_proxy(mid_prices, self.params.adx_period)
        adx_previous = self._adx_proxy(mid_prices[:-1], self.params.adx_period)
        adx_slope = adx_value - adx_previous

        cash = float(portfolio.cash)
        current_price = mid_prices[-1]

        buy_signal = current_price <= lower_band and adx_value >= self.params.adx_threshold
        trend_confirmation = adx_slope >= 0 or current_price <= middle_band
        if buy_signal and trend_confirmation:
            strength = min(
                1.5,
                max(0.25, adx_value / max(self.params.adx_threshold, 1e-6)),
            )
            max_trade_value = cash * self.params.max_cash_fraction
            quantity = math.floor((max_trade_value * strength) / ask)
            if quantity > 0:
                self._entry_bar_index[symbol] = len(mid_prices)
                return "BUY", quantity

        return "HOLD", 0

    def _adx_proxy(self, prices: List[float], period: int) -> float:
        if len(prices) < period + 1:
            return 0.0

        directional_up = 0.0
        directional_down = 0.0
        true_range = 0.0
        start = len(prices) - period
        for index in range(start, len(prices)):
            change = prices[index] - prices[index - 1]
            true_range += abs(change)
            if change > 0:
                directional_up += change
            elif change < 0:
                directional_down -= change

        if true_range <= 0:
            return 0.0
        return 100.0 * abs(directional_up - directional_down) / true_range

    def _bollinger_bands(
        self,
        prices: List[float],
        period: int,
        num_std: float,
    ) -> tuple[float, float, float]:
        recent = prices[-period:]
        middle = sum(recent) / period
        variance = sum((price - middle) ** 2 for price in recent) / period
        std_dev = variance**0.5
        return middle + num_std * std_dev, middle, middle - num_std * std_dev

    def _get_avg_entry(self, portfolio: Portfolio, symbol: str) -> float | None:
        avg_entry = portfolio.cost_basis.get(symbol)
        if avg_entry is None or avg_entry <= 0:
            return None
        return float(avg_entry)


class TrainablePenguin3_Manual(TrainablePenguin3):
    def __init__(
        self,
        name: str = "TrainablePenguin3_Manual",
        bb_period: int = TRAINABLE_PENGUIN3_BB_PERIOD,
        bb_stddev: float = TRAINABLE_PENGUIN3_BB_STDDEV,
        adx_period: int = TRAINABLE_PENGUIN3_ADX_PERIOD,
        adx_threshold: float = TRAINABLE_PENGUIN3_ADX_THRESHOLD,
        max_cash_fraction_per_trade: float = TRAINABLE_PENGUIN3_MAX_CASH_FRACTION,
        rs_lookback: int = TRAINABLE_PENGUIN3_RS_LOOKBACK,
        rs_sell_threshold: float = TRAINABLE_PENGUIN3_RS_SELL_THRESHOLD,
        min_hold_bars: int = TRAINABLE_PENGUIN3_MIN_HOLD_BARS,
        stop_loss_pct: float = TRAINABLE_PENGUIN3_STOP_LOSS_PCT,
        take_profit_pct: float = TRAINABLE_PENGUIN3_TAKE_PROFIT_PCT,
        cooldown_bars: int = TRAINABLE_PENGUIN3_COOLDOWN_BARS,
    ):
        super().__init__(
            name=name,
            bb_period=bb_period,
            bb_stddev=bb_stddev,
            adx_period=adx_period,
            adx_threshold=adx_threshold,
            max_cash_fraction_per_trade=max_cash_fraction_per_trade,
            rs_lookback=rs_lookback,
            rs_sell_threshold=rs_sell_threshold,
            min_hold_bars=min_hold_bars,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            cooldown_bars=cooldown_bars,
        )
