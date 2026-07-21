from dataclasses import dataclass
import math
from typing import List

from backtest.portfolio import Portfolio
from penguins.base_penguin import BasePenguin


# Manual tuning block:
# Adjust these values here first so the strategy is easy to finetune by hand.
TRAINABLE_PENGUIN1_RSI_PERIOD = 12  # 14
TRAINABLE_PENGUIN1_BUY_RSI = 30.0
TRAINABLE_PENGUIN1_MAX_CASH_FRACTION = 0.05
TRAINABLE_PENGUIN1_VOLUME_LOOKBACK = 20
TRAINABLE_PENGUIN1_VOLUME_MULTIPLIER = 2.0
TRAINABLE_PENGUIN1_VOLUME_CONFIRMATION_BARS = 2
TRAINABLE_PENGUIN1_FALLING_MOMENTUM_LOOKBACK = 5
TRAINABLE_PENGUIN1_FALLING_MOMENTUM_THRESHOLD = -0.002
TRAINABLE_PENGUIN1_MIN_HOLD_BARS = 3
TRAINABLE_PENGUIN1_STOP_LOSS_PCT = 0.04
TRAINABLE_PENGUIN1_TAKE_PROFIT_PCT = 0.08
TRAINABLE_PENGUIN1_COOLDOWN_BARS = 10
TRAINABLE_PENGUIN1_ATR_PERIOD = 14
TRAINABLE_PENGUIN1_ATR_TRAILING_MULTIPLIER = 2.5
TRAINABLE_PENGUIN1_ATR_STOP_MULTIPLIER = 2.0
TRAINABLE_PENGUIN1_MAX_PRICE_EXTENSION_FROM_SMA30 = 0.06


# Buy on RSI plus trend quality; sell after a minimum hold on ATR-based risk
# exits, a trailing ATR-like stop, or a confirmed bearish volume reversal.


@dataclass
class TrainablePenguin1Params:
    rsi_period: int = TRAINABLE_PENGUIN1_RSI_PERIOD
    buy_rsi: float = TRAINABLE_PENGUIN1_BUY_RSI
    max_cash_fraction: float = TRAINABLE_PENGUIN1_MAX_CASH_FRACTION
    volume_lookback: int = TRAINABLE_PENGUIN1_VOLUME_LOOKBACK
    volume_multiplier: float = TRAINABLE_PENGUIN1_VOLUME_MULTIPLIER
    volume_confirmation_bars: int = TRAINABLE_PENGUIN1_VOLUME_CONFIRMATION_BARS
    falling_momentum_lookback: int = TRAINABLE_PENGUIN1_FALLING_MOMENTUM_LOOKBACK
    falling_momentum_threshold: float = TRAINABLE_PENGUIN1_FALLING_MOMENTUM_THRESHOLD
    min_hold_bars: int = TRAINABLE_PENGUIN1_MIN_HOLD_BARS
    stop_loss_pct: float = TRAINABLE_PENGUIN1_STOP_LOSS_PCT
    take_profit_pct: float = TRAINABLE_PENGUIN1_TAKE_PROFIT_PCT
    cooldown_bars: int = TRAINABLE_PENGUIN1_COOLDOWN_BARS
    atr_period: int = TRAINABLE_PENGUIN1_ATR_PERIOD
    atr_trailing_multiplier: float = TRAINABLE_PENGUIN1_ATR_TRAILING_MULTIPLIER
    atr_stop_multiplier: float = TRAINABLE_PENGUIN1_ATR_STOP_MULTIPLIER
    max_price_extension_from_sma30: float = TRAINABLE_PENGUIN1_MAX_PRICE_EXTENSION_FROM_SMA30


class TrainablePenguin1(BasePenguin):
    LOOKBACK_BARS = 120

    def __init__(
        self,
        name: str = "TrainablePenguin1",
        rsi_period: int = TRAINABLE_PENGUIN1_RSI_PERIOD,
        buy_rsi: float = TRAINABLE_PENGUIN1_BUY_RSI,
        max_cash_fraction_per_trade: float = TRAINABLE_PENGUIN1_MAX_CASH_FRACTION,
        volume_lookback: int = TRAINABLE_PENGUIN1_VOLUME_LOOKBACK,
        volume_multiplier: float = TRAINABLE_PENGUIN1_VOLUME_MULTIPLIER,
        volume_confirmation_bars: int = TRAINABLE_PENGUIN1_VOLUME_CONFIRMATION_BARS,
        falling_momentum_lookback: int = TRAINABLE_PENGUIN1_FALLING_MOMENTUM_LOOKBACK,
        falling_momentum_threshold: float = TRAINABLE_PENGUIN1_FALLING_MOMENTUM_THRESHOLD,
        min_hold_bars: int = TRAINABLE_PENGUIN1_MIN_HOLD_BARS,
        stop_loss_pct: float = TRAINABLE_PENGUIN1_STOP_LOSS_PCT,
        take_profit_pct: float = TRAINABLE_PENGUIN1_TAKE_PROFIT_PCT,
        cooldown_bars: int = TRAINABLE_PENGUIN1_COOLDOWN_BARS,
        atr_period: int = TRAINABLE_PENGUIN1_ATR_PERIOD,
        atr_trailing_multiplier: float = TRAINABLE_PENGUIN1_ATR_TRAILING_MULTIPLIER,
        atr_stop_multiplier: float = TRAINABLE_PENGUIN1_ATR_STOP_MULTIPLIER,
        max_price_extension_from_sma30: float = TRAINABLE_PENGUIN1_MAX_PRICE_EXTENSION_FROM_SMA30,
    ):
        super().__init__(name)
        self.params = TrainablePenguin1Params(
            rsi_period=rsi_period,
            buy_rsi=buy_rsi,
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
            atr_period=atr_period,
            atr_trailing_multiplier=atr_trailing_multiplier,
            atr_stop_multiplier=atr_stop_multiplier,
            max_price_extension_from_sma30=max_price_extension_from_sma30,
        )
        self._position_entry_bar_index: dict[str, int] = {}
        self._entry_bar_index = self._position_entry_bar_index
        self._position_highest_price: dict[str, float] = {}
        self._last_sell_bar_index: dict[str, int] = {}

    def decide(
        self,
        symbol: str,
        mid_prices: List[float],
        bid: float,
        ask: float,
        portfolio: Portfolio,
    ) -> tuple[str, int]:
        volumes = self._market_volume_history.get(symbol, ())
        shares_owned = self._get_position(portfolio, symbol)
        current_bar = len(mid_prices)

        if shares_owned <= 0:
            self._clear_position_state(symbol)
        else:
            current_price = self._current_price(bid, mid_prices)
            if current_price is not None:
                self._position_highest_price[symbol] = max(
                    self._position_highest_price.get(symbol, current_price),
                    current_price,
                )

        if shares_owned > 0:
            entry_bar = self._position_entry_bar_index.get(symbol)
            if entry_bar is None:
                self._position_entry_bar_index[symbol] = current_bar
                entry_bar = current_bar

            bars_held = max(0, current_bar - entry_bar)
            if bars_held < self.params.min_hold_bars:
                return "HOLD", 0

            current_price = self._current_price(bid, mid_prices)
            if current_price is None:
                return "HOLD", 0

            avg_entry = self._get_avg_entry(portfolio, symbol)
            atr_value = self._mid_price_atr_like_proxy(mid_prices, self.params.atr_period)
            highest_price = self._position_highest_price.get(symbol, current_price)
            sma_10, sma_30, _, _ = self._trend_snapshot(mid_prices)

            # Initial ATR-based stop from the average entry price.
            stop_loss_trigger = False
            if avg_entry is not None and atr_value is not None:
                initial_stop = avg_entry - atr_value * self.params.atr_stop_multiplier
                stop_loss_trigger = current_price <= initial_stop

            # ATR-like trailing exit based on the highest mid/bid seen since entry.
            trailing_stop_trigger = False
            if atr_value is not None:
                trailing_exit = highest_price - atr_value * self.params.atr_trailing_multiplier
                trailing_stop_trigger = current_price <= trailing_exit

            volume_reversal_trigger = self._has_confirmed_volume_reversal(
                prices=mid_prices,
                volumes=volumes,
                volume_lookback=self.params.volume_lookback,
                volume_multiplier=self.params.volume_multiplier,
                confirmation_bars=self.params.volume_confirmation_bars,
                momentum_lookback=self.params.falling_momentum_lookback,
                momentum_threshold=self.params.falling_momentum_threshold,
                current_price=current_price,
                sma_10=sma_10,
                sma_30=sma_30,
            )

            if stop_loss_trigger or trailing_stop_trigger or volume_reversal_trigger:
                self._register_exit(symbol, current_bar)
                return "SELL", shares_owned

            return "HOLD", 0

        if (
            bid <= 0
            or ask <= 0
            or len(mid_prices) < max(60, self.params.rsi_period + 2)
            or len(volumes) < self.params.volume_lookback + 1
            or self._is_in_cooldown(symbol, current_bar)
        ):
            return "HOLD", 0

        current_price = mid_prices[-1]
        rsi = self._rsi(mid_prices, self.params.rsi_period)
        trend_score = self._trend_quality(mid_prices)

        cash = self._get_cash(portfolio)

        if rsi <= self.params.buy_rsi and trend_score > 0.5:
            max_shares_to_buy = math.floor(
                (cash * self.params.max_cash_fraction) / current_price
            )
            if max_shares_to_buy > 0:
                self._position_entry_bar_index[symbol] = current_bar
                self._position_highest_price[symbol] = current_price
                return "BUY", max_shares_to_buy

        return "HOLD", 0

    def _is_in_cooldown(self, symbol: str, current_bar: int) -> bool:
        if self.params.cooldown_bars <= 0:
            return False

        last_sell_bar = self._last_sell_bar_index.get(symbol)
        if last_sell_bar is None:
            return False

        return (current_bar - last_sell_bar) < self.params.cooldown_bars

    def _register_exit(self, symbol: str, current_bar: int) -> None:
        self._last_sell_bar_index[symbol] = current_bar
        self._clear_position_state(symbol)

    def _clear_position_state(self, symbol: str) -> None:
        self._position_entry_bar_index.pop(symbol, None)
        self._position_highest_price.pop(symbol, None)

    def _has_confirmed_volume_reversal(
        self,
        prices: List[float],
        volumes: List[float],
        volume_lookback: int,
        volume_multiplier: float,
        confirmation_bars: int,
        momentum_lookback: int,
        momentum_threshold: float,
        current_price: float,
        sma_10: float | None,
        sma_30: float | None,
    ) -> bool:
        if confirmation_bars <= 0:
            return False

        if sma_10 is None or sma_30 is None:
            return False

        if not self._has_volume_surge_sequence(
            volumes,
            volume_lookback,
            volume_multiplier,
            confirmation_bars,
        ):
            return False

        if not self._has_falling_momentum(prices, momentum_lookback, momentum_threshold):
            return False

        # Require a bearish confirmation before treating the volume surge as an exit.
        bearish_confirmation = current_price < sma_10 or sma_10 < sma_30
        return bearish_confirmation

    def _has_volume_surge_sequence(
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

        start_index = len(volumes) - confirmation_bars
        for index in range(start_index, len(volumes)):
            previous_window = volumes[index - lookback : index]
            if len(previous_window) < lookback:
                return False

            average_volume = sum(float(value) for value in previous_window) / lookback
            current_volume = float(volumes[index])
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

    def _rsi(self, prices: List[float], period: int = 14) -> float:
        gain_sum = 0.0
        loss_sum = 0.0
        start = len(prices) - period

        for index in range(start, len(prices)):
            delta = prices[index] - prices[index - 1]
            if delta > 0:
                gain_sum += delta
            elif delta < 0:
                loss_sum -= delta

        avg_gain = gain_sum / period
        avg_loss = loss_sum / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _trend_quality(self, prices: List[float]) -> float:
        sma_10, sma_30, sma_60, sma_30_five_bars_ago = self._trend_snapshot(prices)
        if (
            sma_10 is None
            or sma_30 is None
            or sma_60 is None
            or sma_30_five_bars_ago is None
        ):
            return 0.0

        current_price = float(prices[-1])
        score = 0.0

        if sma_10 > sma_30:
            score += 0.25
        if sma_30 > sma_60:
            score += 0.25
        if sma_30 > sma_30_five_bars_ago:
            score += 0.20
        if current_price > sma_30:
            score += 0.15
            if current_price <= sma_30 * (1.0 + self.params.max_price_extension_from_sma30):
                score += 0.15

        return min(score, 1.0)

    def _trend_snapshot(self, prices: List[float]) -> tuple[float | None, float | None, float | None, float | None]:
        sma_10 = self._sma(prices, 10)
        sma_30 = self._sma(prices, 30)
        sma_60 = self._sma(prices, 60)
        sma_30_five_bars_ago = self._sma(prices[:-5], 30) if len(prices) >= 35 else None
        return sma_10, sma_30, sma_60, sma_30_five_bars_ago

    def _sma(self, prices: List[float], period: int) -> float | None:
        if period <= 0 or len(prices) < period:
            return None

        window = prices[-period:]
        return sum(window) / period

    def _mid_price_atr_like_proxy(self, prices: List[float], period: int) -> float | None:
        # This is an ATR-like volatility proxy derived from mid/close prices only.
        if period <= 0 or len(prices) < period + 1:
            return None

        recent_prices = prices[-(period + 1) :]
        total_abs_change = 0.0
        for index in range(1, len(recent_prices)):
            total_abs_change += abs(recent_prices[index] - recent_prices[index - 1])

        return total_abs_change / period

    def _current_price(self, bid: float, mid_prices: List[float]) -> float | None:
        if bid > 0:
            return float(bid)
        if not mid_prices:
            return None
        return float(mid_prices[-1])

    def _get_cash(self, portfolio: Portfolio) -> float:
        return float(portfolio.cash)

    def _get_position(self, portfolio: Portfolio, symbol: str) -> int:
        return int(portfolio.get_position(symbol))

    def _get_avg_entry(self, portfolio: Portfolio, symbol: str) -> float | None:
        avg_entry = portfolio.cost_basis.get(symbol)
        if avg_entry is None or avg_entry <= 0:
            return None
        return float(avg_entry)


class TrainablePenguin1_Manual(TrainablePenguin1):
    def __init__(
        self,
        name: str = "TrainablePenguin1_Manual",
        rsi_period: int = TRAINABLE_PENGUIN1_RSI_PERIOD,
        buy_rsi: float = TRAINABLE_PENGUIN1_BUY_RSI,
        max_cash_fraction_per_trade: float = TRAINABLE_PENGUIN1_MAX_CASH_FRACTION,
        volume_lookback: int = TRAINABLE_PENGUIN1_VOLUME_LOOKBACK,
        volume_multiplier: float = TRAINABLE_PENGUIN1_VOLUME_MULTIPLIER,
        volume_confirmation_bars: int = TRAINABLE_PENGUIN1_VOLUME_CONFIRMATION_BARS,
        falling_momentum_lookback: int = TRAINABLE_PENGUIN1_FALLING_MOMENTUM_LOOKBACK,
        falling_momentum_threshold: float = TRAINABLE_PENGUIN1_FALLING_MOMENTUM_THRESHOLD,
        min_hold_bars: int = TRAINABLE_PENGUIN1_MIN_HOLD_BARS,
        stop_loss_pct: float = TRAINABLE_PENGUIN1_STOP_LOSS_PCT,
        take_profit_pct: float = TRAINABLE_PENGUIN1_TAKE_PROFIT_PCT,
        cooldown_bars: int = TRAINABLE_PENGUIN1_COOLDOWN_BARS,
        atr_period: int = TRAINABLE_PENGUIN1_ATR_PERIOD,
        atr_trailing_multiplier: float = TRAINABLE_PENGUIN1_ATR_TRAILING_MULTIPLIER,
        atr_stop_multiplier: float = TRAINABLE_PENGUIN1_ATR_STOP_MULTIPLIER,
        max_price_extension_from_sma30: float = TRAINABLE_PENGUIN1_MAX_PRICE_EXTENSION_FROM_SMA30,
    ):
        super().__init__(
            name=name,
            rsi_period=rsi_period,
            buy_rsi=buy_rsi,
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
            atr_period=atr_period,
            atr_trailing_multiplier=atr_trailing_multiplier,
            atr_stop_multiplier=atr_stop_multiplier,
            max_price_extension_from_sma30=max_price_extension_from_sma30,
        )
