from dataclasses import dataclass
from typing import List
import math

from backtest.portfolio import Portfolio
from penguins.base_penguin import BasePenguin


# Manual tuning block:
# Adjust these values here first so the strategy is easy to finetune by hand.
TRAINABLE_PENGUIN2_BB_PERIOD = 20 #20
TRAINABLE_PENGUIN2_BB_STDDEV = 2.0
TRAINABLE_PENGUIN2_ADX_PERIOD = 14
TRAINABLE_PENGUIN2_ADX_THRESHOLD = 25.0
TRAINABLE_PENGUIN2_MAX_CASH_FRACTION = 0.05
TRAINABLE_PENGUIN2_VOLUME_LOOKBACK = 20
TRAINABLE_PENGUIN2_VOLUME_MULTIPLIER = 2.0
TRAINABLE_PENGUIN2_VOLUME_CONFIRMATION_BARS = 3
TRAINABLE_PENGUIN2_FALLING_MOMENTUM_LOOKBACK = 5
TRAINABLE_PENGUIN2_FALLING_MOMENTUM_THRESHOLD = -0.002
TRAINABLE_PENGUIN2_MIN_HOLD_BARS = 3
TRAINABLE_PENGUIN2_STOP_LOSS_PCT = 0.04
TRAINABLE_PENGUIN2_TAKE_PROFIT_PCT = 0.08
TRAINABLE_PENGUIN2_COOLDOWN_BARS = 10


# Buy on Bollinger Bands plus ADX, size by ADX, and sell after a minimum hold
# on stop loss, take profit, or a confirmed multi-bar volume surge with
# falling momentum.


@dataclass
class TrainablePenguin2Params:
    bb_period: int = TRAINABLE_PENGUIN2_BB_PERIOD
    bb_stddev: float = TRAINABLE_PENGUIN2_BB_STDDEV
    adx_period: int = TRAINABLE_PENGUIN2_ADX_PERIOD
    adx_threshold: float = TRAINABLE_PENGUIN2_ADX_THRESHOLD
    max_cash_fraction: float = TRAINABLE_PENGUIN2_MAX_CASH_FRACTION
    volume_lookback: int = TRAINABLE_PENGUIN2_VOLUME_LOOKBACK
    volume_multiplier: float = TRAINABLE_PENGUIN2_VOLUME_MULTIPLIER
    volume_confirmation_bars: int = TRAINABLE_PENGUIN2_VOLUME_CONFIRMATION_BARS
    falling_momentum_lookback: int = TRAINABLE_PENGUIN2_FALLING_MOMENTUM_LOOKBACK
    falling_momentum_threshold: float = TRAINABLE_PENGUIN2_FALLING_MOMENTUM_THRESHOLD
    min_hold_bars: int = TRAINABLE_PENGUIN2_MIN_HOLD_BARS
    stop_loss_pct: float = TRAINABLE_PENGUIN2_STOP_LOSS_PCT
    take_profit_pct: float = TRAINABLE_PENGUIN2_TAKE_PROFIT_PCT
    cooldown_bars: int = TRAINABLE_PENGUIN2_COOLDOWN_BARS


class TrainablePenguin2(BasePenguin):
    LOOKBACK_BARS = 120

    def __init__(
        self,
        name: str = "TrainablePenguin2",
        bb_period: int = TRAINABLE_PENGUIN2_BB_PERIOD,
        bb_stddev: float = TRAINABLE_PENGUIN2_BB_STDDEV,
        adx_period: int = TRAINABLE_PENGUIN2_ADX_PERIOD,
        adx_threshold: float = TRAINABLE_PENGUIN2_ADX_THRESHOLD,
        max_cash_fraction_per_trade: float = TRAINABLE_PENGUIN2_MAX_CASH_FRACTION,
        volume_lookback: int = TRAINABLE_PENGUIN2_VOLUME_LOOKBACK,
        volume_multiplier: float = TRAINABLE_PENGUIN2_VOLUME_MULTIPLIER,
        volume_confirmation_bars: int = TRAINABLE_PENGUIN2_VOLUME_CONFIRMATION_BARS,
        falling_momentum_lookback: int = TRAINABLE_PENGUIN2_FALLING_MOMENTUM_LOOKBACK,
        falling_momentum_threshold: float = TRAINABLE_PENGUIN2_FALLING_MOMENTUM_THRESHOLD,
        min_hold_bars: int = TRAINABLE_PENGUIN2_MIN_HOLD_BARS,
        stop_loss_pct: float = TRAINABLE_PENGUIN2_STOP_LOSS_PCT,
        take_profit_pct: float = TRAINABLE_PENGUIN2_TAKE_PROFIT_PCT,
        cooldown_bars: int = TRAINABLE_PENGUIN2_COOLDOWN_BARS,
    ):
        super().__init__(name)
        self.params = TrainablePenguin2Params(
            bb_period=bb_period,
            bb_stddev=bb_stddev,
            adx_period=adx_period,
            adx_threshold=adx_threshold,
            max_cash_fraction=max_cash_fraction_per_trade,
            volume_lookback=volume_lookback,
            volume_multiplier=volume_multiplier,
            volume_confirmation_bars=volume_confirmation_bars,
            falling_momentum_lookback=falling_momentum_lookback,
            falling_momentum_threshold=falling_momentum_threshold,
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
        min_required = max(self.params.bb_period, self.params.adx_period) + 2
        volumes = self._market_volume_history.get(symbol, ())
        shares_owned = self._get_position(portfolio, symbol)
        current_bar = len(mid_prices)
        if shares_owned > 0:
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
            volume_reversal_trigger = self._has_confirmed_volume_reversal(
                mid_prices,
                volumes,
                self.params.volume_lookback,
                self.params.volume_multiplier,
                self.params.volume_confirmation_bars,
                self.params.falling_momentum_lookback,
                self.params.falling_momentum_threshold,
            )

            if stop_loss_trigger or take_profit_trigger or volume_reversal_trigger:
                self._entry_bar_index.pop(symbol, None)
                return "SELL", shares_owned
            return "HOLD", 0

        if (
            bid <= 0
            or ask <= 0
            or len(mid_prices) < min_required
            or len(volumes) < self.params.volume_lookback + 1
        ):
            return "HOLD", 0

        upper_band, middle_band, lower_band = self._bollinger_bands(
            mid_prices,
            self.params.bb_period,
            self.params.bb_stddev,
        )
        adx_value = self._adx_proxy(mid_prices, self.params.adx_period)
        adx_previous = self._adx_proxy(mid_prices[:-1], self.params.adx_period)
        adx_slope = adx_value - adx_previous

        cash = self._get_cash(portfolio)
        current_price = mid_prices[-1]

        buy_signal = current_price <= lower_band and adx_value >= self.params.adx_threshold
        trend_confirmation = adx_slope >= 0 or current_price <= middle_band

        if buy_signal and trend_confirmation:
            strength = min(
                1.5,
                max(0.25, adx_value / max(self.params.adx_threshold, 1e-6)),
            )
            max_trade_value = cash * self.params.max_cash_fraction
            qty = math.floor((max_trade_value * strength) / ask)
            if qty > 0:
                self._entry_bar_index[symbol] = current_bar
                return "BUY", qty

        return "HOLD", 0

    def _has_confirmed_volume_reversal(
        self,
        prices: List[float],
        volumes: List[float],
        volume_lookback: int,
        volume_multiplier: float,
        confirmation_bars: int,
        momentum_lookback: int,
        momentum_threshold: float,
    ) -> bool:
        if confirmation_bars <= 0:
            return False

        if not self._is_multi_bar_volume_explosion(
            volumes,
            volume_lookback,
            volume_multiplier,
            confirmation_bars,
        ):
            return False

        return self._has_falling_momentum(prices, momentum_lookback, momentum_threshold)

    def _is_multi_bar_volume_explosion(
        self,
        volumes: List[float],
        lookback: int,
        multiplier: float,
        confirmation_bars: int,
    ) -> bool:
        if lookback <= 0 or multiplier <= 0 or confirmation_bars <= 0:
            return False

        if len(volumes) < lookback + confirmation_bars:
            return False

        for offset in range(confirmation_bars):
            end_index = len(volumes) - offset
            current_volume = float(volumes[end_index - 1])
            previous_volumes = [
                float(value)
                for value in volumes[end_index - lookback - 1 : end_index - 1]
            ]
            average_volume = sum(previous_volumes) / lookback
            if average_volume <= 0 or current_volume < average_volume * multiplier:
                return False

        return True

    def _has_falling_momentum(
        self,
        prices: List[float],
        lookback: int,
        threshold: float,
    ) -> bool:
        if lookback <= 0 or len(prices) < lookback + 1:
            return False

        start_price = prices[-lookback - 1]
        end_price = prices[-1]

        if start_price <= 0:
            return False

        momentum_return = (end_price - start_price) / start_price
        return momentum_return <= threshold

    def _bollinger_bands(self, prices: List[float], period: int, num_std: float) -> tuple[float, float, float]:
        recent = prices[-period:]
        middle = sum(recent) / period
        variance = sum((price - middle) ** 2 for price in recent) / period
        std_dev = variance ** 0.5
        upper = middle + num_std * std_dev
        lower = middle - num_std * std_dev
        return upper, middle, lower

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

        directional_strength = abs(directional_up - directional_down) / true_range
        return 100.0 * directional_strength

    def _get_cash(self, portfolio: Portfolio) -> float:
        return float(portfolio.cash)

    def _get_position(self, portfolio: Portfolio, symbol: str) -> int:
        return int(portfolio.get_position(symbol))

    def _get_avg_entry(self, portfolio: Portfolio, symbol: str) -> float | None:
        avg_entry = portfolio.cost_basis.get(symbol)
        if avg_entry is None or avg_entry <= 0:
            return None
        return float(avg_entry)

class TrainablePenguin2_Manual(TrainablePenguin2):
    def __init__(
        self,
        name: str = "TrainablePenguin2_Manual",
        bb_period: int = TRAINABLE_PENGUIN2_BB_PERIOD,
        bb_stddev: float = TRAINABLE_PENGUIN2_BB_STDDEV,
        adx_period: int = TRAINABLE_PENGUIN2_ADX_PERIOD,
        adx_threshold: float = TRAINABLE_PENGUIN2_ADX_THRESHOLD,
        max_cash_fraction_per_trade: float = TRAINABLE_PENGUIN2_MAX_CASH_FRACTION,
        volume_lookback: int = TRAINABLE_PENGUIN2_VOLUME_LOOKBACK,
        volume_multiplier: float = TRAINABLE_PENGUIN2_VOLUME_MULTIPLIER,
        volume_confirmation_bars: int = TRAINABLE_PENGUIN2_VOLUME_CONFIRMATION_BARS,
        falling_momentum_lookback: int = TRAINABLE_PENGUIN2_FALLING_MOMENTUM_LOOKBACK,
        falling_momentum_threshold: float = TRAINABLE_PENGUIN2_FALLING_MOMENTUM_THRESHOLD,
        min_hold_bars: int = TRAINABLE_PENGUIN2_MIN_HOLD_BARS,
        stop_loss_pct: float = TRAINABLE_PENGUIN2_STOP_LOSS_PCT,
        take_profit_pct: float = TRAINABLE_PENGUIN2_TAKE_PROFIT_PCT,
        cooldown_bars: int = TRAINABLE_PENGUIN2_COOLDOWN_BARS,
    ):
        super().__init__(
            name=name,
            bb_period=bb_period,
            bb_stddev=bb_stddev,
            adx_period=adx_period,
            adx_threshold=adx_threshold,
            max_cash_fraction_per_trade=max_cash_fraction_per_trade,
            volume_lookback=volume_lookback,
            volume_multiplier=volume_multiplier,
            volume_confirmation_bars=volume_confirmation_bars,
            falling_momentum_lookback=falling_momentum_lookback,
            falling_momentum_threshold=falling_momentum_threshold,
            min_hold_bars=min_hold_bars,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            cooldown_bars=cooldown_bars,
        )
