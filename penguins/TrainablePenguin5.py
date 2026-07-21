from dataclasses import dataclass
import math
from typing import List

from backtest.portfolio import Portfolio
from penguins.base_penguin import BasePenguin


# Manual tuning block:
# Adjust these values here first so the strategy is easy to finetune by hand.
TRAINABLE_PENGUIN5_RSI_PERIOD = 12 #14
TRAINABLE_PENGUIN5_BUY_RSI = 30.0
TRAINABLE_PENGUIN5_MAX_CASH_FRACTION = 0.05
TRAINABLE_PENGUIN5_VOLUME_LOOKBACK = 20
TRAINABLE_PENGUIN5_VOLUME_MULTIPLIER = 2.0
TRAINABLE_PENGUIN5_VOLUME_CONFIRMATION_BARS = 3
TRAINABLE_PENGUIN5_FALLING_MOMENTUM_LOOKBACK = 5
TRAINABLE_PENGUIN5_FALLING_MOMENTUM_THRESHOLD = -0.002
TRAINABLE_PENGUIN5_MIN_HOLD_BARS = 3
TRAINABLE_PENGUIN5_STOP_LOSS_PCT = 0.04
TRAINABLE_PENGUIN5_TAKE_PROFIT_PCT = 0.08
TRAINABLE_PENGUIN5_COOLDOWN_BARS = 10


# Buy on RSI plus trend quality; sell after a minimum hold on stop loss,
# take profit, or a confirmed volume surge with falling momentum.


@dataclass
class TrainablePenguin5Params:
    rsi_period: int = TRAINABLE_PENGUIN5_RSI_PERIOD
    buy_rsi: float = TRAINABLE_PENGUIN5_BUY_RSI
    max_cash_fraction: float = TRAINABLE_PENGUIN5_MAX_CASH_FRACTION
    volume_lookback: int = TRAINABLE_PENGUIN5_VOLUME_LOOKBACK
    volume_multiplier: float = TRAINABLE_PENGUIN5_VOLUME_MULTIPLIER
    volume_confirmation_bars: int = TRAINABLE_PENGUIN5_VOLUME_CONFIRMATION_BARS
    falling_momentum_lookback: int = TRAINABLE_PENGUIN5_FALLING_MOMENTUM_LOOKBACK
    falling_momentum_threshold: float = TRAINABLE_PENGUIN5_FALLING_MOMENTUM_THRESHOLD
    min_hold_bars: int = TRAINABLE_PENGUIN5_MIN_HOLD_BARS
    stop_loss_pct: float = TRAINABLE_PENGUIN5_STOP_LOSS_PCT
    take_profit_pct: float = TRAINABLE_PENGUIN5_TAKE_PROFIT_PCT
    cooldown_bars: int = TRAINABLE_PENGUIN5_COOLDOWN_BARS


class TrainablePenguin5(BasePenguin):
    LOOKBACK_BARS = 120

    def __init__(
        self,
        name: str = "TrainablePenguin5",
        rsi_period: int = TRAINABLE_PENGUIN5_RSI_PERIOD,
        buy_rsi: float = TRAINABLE_PENGUIN5_BUY_RSI,
        max_cash_fraction_per_trade: float = TRAINABLE_PENGUIN5_MAX_CASH_FRACTION,
        volume_lookback: int = TRAINABLE_PENGUIN5_VOLUME_LOOKBACK,
        volume_multiplier: float = TRAINABLE_PENGUIN5_VOLUME_MULTIPLIER,
        volume_confirmation_bars: int = TRAINABLE_PENGUIN5_VOLUME_CONFIRMATION_BARS,
        falling_momentum_lookback: int = TRAINABLE_PENGUIN5_FALLING_MOMENTUM_LOOKBACK,
        falling_momentum_threshold: float = TRAINABLE_PENGUIN5_FALLING_MOMENTUM_THRESHOLD,
        min_hold_bars: int = TRAINABLE_PENGUIN5_MIN_HOLD_BARS,
        stop_loss_pct: float = TRAINABLE_PENGUIN5_STOP_LOSS_PCT,
        take_profit_pct: float = TRAINABLE_PENGUIN5_TAKE_PROFIT_PCT,
        cooldown_bars: int = TRAINABLE_PENGUIN5_COOLDOWN_BARS,
    ):
        super().__init__(name)
        self.params = TrainablePenguin5Params(
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
            or len(mid_prices) < max(60, self.params.rsi_period + 2)
            or len(volumes) < self.params.volume_lookback + 1
        ):
            return "HOLD", 0

        rsi = self._rsi(mid_prices, self.params.rsi_period)
        trend_score = self._trend_quality(mid_prices)

        cash = self._get_cash(portfolio)
        current_price = mid_prices[-1]

        if rsi <= self.params.buy_rsi and trend_score > 0.5:
            max_shares_to_buy = math.floor(
                (cash * self.params.max_cash_fraction) / current_price
            )
            if max_shares_to_buy > 0:
                self._entry_bar_index[symbol] = current_bar
                return "BUY", max_shares_to_buy

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
        sma_10 = sum(prices[-10:]) / 10
        sma_30 = sum(prices[-30:]) / 30
        sma_60 = sum(prices[-60:]) / 60

        score = 0.0

        if sma_10 > sma_30:
            score += 0.35
        if sma_30 > sma_60:
            score += 0.35
        if prices[-1] > sma_30:
            score += 0.20
        if prices[-1] > prices[-5]:
            score += 0.10

        return min(score, 1.0)

    def _get_cash(self, portfolio: Portfolio) -> float:
        return float(portfolio.cash)

    def _get_position(self, portfolio: Portfolio, symbol: str) -> int:
        return int(portfolio.get_position(symbol))

    def _get_avg_entry(self, portfolio: Portfolio, symbol: str) -> float | None:
        avg_entry = portfolio.cost_basis.get(symbol)
        if avg_entry is None or avg_entry <= 0:
            return None
        return float(avg_entry)

class TrainablePenguin5_Manual(TrainablePenguin5):
    def __init__(
        self,
        name: str = "TrainablePenguin5_Manual",
        rsi_period: int = TRAINABLE_PENGUIN5_RSI_PERIOD,
        buy_rsi: float = TRAINABLE_PENGUIN5_BUY_RSI,
        max_cash_fraction_per_trade: float = TRAINABLE_PENGUIN5_MAX_CASH_FRACTION,
        volume_lookback: int = TRAINABLE_PENGUIN5_VOLUME_LOOKBACK,
        volume_multiplier: float = TRAINABLE_PENGUIN5_VOLUME_MULTIPLIER,
        volume_confirmation_bars: int = TRAINABLE_PENGUIN5_VOLUME_CONFIRMATION_BARS,
        falling_momentum_lookback: int = TRAINABLE_PENGUIN5_FALLING_MOMENTUM_LOOKBACK,
        falling_momentum_threshold: float = TRAINABLE_PENGUIN5_FALLING_MOMENTUM_THRESHOLD,
        min_hold_bars: int = TRAINABLE_PENGUIN5_MIN_HOLD_BARS,
        stop_loss_pct: float = TRAINABLE_PENGUIN5_STOP_LOSS_PCT,
        take_profit_pct: float = TRAINABLE_PENGUIN5_TAKE_PROFIT_PCT,
        cooldown_bars: int = TRAINABLE_PENGUIN5_COOLDOWN_BARS,
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
        )
