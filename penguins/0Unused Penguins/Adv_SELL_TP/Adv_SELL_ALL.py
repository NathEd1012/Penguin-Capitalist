from dataclasses import dataclass
import math
from typing import List

from backtest.portfolio import Portfolio
from indicators.market_context import relative_performance, relative_volume
from penguins.base_penguin import BasePenguin


RSI_PERIOD = 13
BUY_RSI = 30.0
SELL_RSI = 70.0
BB_PERIOD = 20
BB_STDDEV = 2.0
KAUFMAN_EFFICIENCY_RATIO_PERIOD = 14
KAUFMAN_EFFICIENCY_RATIO_THRESHOLD = 25.0
MAX_CASH_FRACTION = 0.05
STOP_LOSS_PCT = 0.04
TAKE_PROFIT_PCT = 0.08
COOLDOWN_BARS = 10
RELATIVE_PERFORMANCE_PERIOD = 20
RELATIVE_PERFORMANCE_THRESHOLD = 0.0
RVOL_PERIOD = 20
RVOL_THRESHOLD = 2.0


@dataclass
class Adv_SELL_ALLParams:
    rsi_period: int = RSI_PERIOD
    buy_rsi: float = BUY_RSI
    sell_rsi: float = SELL_RSI
    bb_period: int = BB_PERIOD
    bb_stddev: float = BB_STDDEV
    kaufman_efficiency_ratio_period: int = KAUFMAN_EFFICIENCY_RATIO_PERIOD
    kaufman_efficiency_ratio_threshold: float = KAUFMAN_EFFICIENCY_RATIO_THRESHOLD
    max_cash_fraction: float = MAX_CASH_FRACTION
    stop_loss_pct: float = STOP_LOSS_PCT
    take_profit_pct: float = TAKE_PROFIT_PCT
    cooldown_bars: int = COOLDOWN_BARS
    relative_performance_period: int = RELATIVE_PERFORMANCE_PERIOD
    relative_performance_threshold: float = RELATIVE_PERFORMANCE_THRESHOLD
    rvol_period: int = RVOL_PERIOD
    rvol_threshold: float = RVOL_THRESHOLD


class Adv_SELL_ALL(BasePenguin):
    LOOKBACK_BARS = 120
    TRAINABLE = True

    def __init__(
        self,
        name: str = "Adv_SELL_ALL",
        rsi_period: int = RSI_PERIOD,
        buy_rsi: float = BUY_RSI,
        sell_rsi: float = SELL_RSI,
        bb_period: int = BB_PERIOD,
        bb_stddev: float = BB_STDDEV,
        kaufman_efficiency_ratio_period: int = KAUFMAN_EFFICIENCY_RATIO_PERIOD,
        kaufman_efficiency_ratio_threshold: float = KAUFMAN_EFFICIENCY_RATIO_THRESHOLD,
        max_cash_fraction: float = MAX_CASH_FRACTION,
        stop_loss_pct: float = STOP_LOSS_PCT,
        take_profit_pct: float = TAKE_PROFIT_PCT,
        cooldown_bars: int = COOLDOWN_BARS,
        relative_performance_period: int = RELATIVE_PERFORMANCE_PERIOD,
        relative_performance_threshold: float = RELATIVE_PERFORMANCE_THRESHOLD,
        rvol_period: int = RVOL_PERIOD,
        rvol_threshold: float = RVOL_THRESHOLD,
    ):
        super().__init__(name)
        self.params = Adv_SELL_ALLParams(
            rsi_period=rsi_period,
            buy_rsi=buy_rsi,
            sell_rsi=sell_rsi,
            bb_period=bb_period,
            bb_stddev=bb_stddev,
            kaufman_efficiency_ratio_period=kaufman_efficiency_ratio_period,
            kaufman_efficiency_ratio_threshold=kaufman_efficiency_ratio_threshold,
            max_cash_fraction=max_cash_fraction,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            cooldown_bars=cooldown_bars,
            relative_performance_period=relative_performance_period,
            relative_performance_threshold=relative_performance_threshold,
            rvol_period=rvol_period,
            rvol_threshold=rvol_threshold,
        )

    def decide(
        self,
        symbol: str,
        mid_prices: List[float],
        bid: float,
        ask: float,
        portfolio: Portfolio,
        spy_prices: List[float] | None = None,
        volumes: List[float] | None = None,
    ) -> tuple[str, int]:
        min_required = max(
            60,
            self.params.rsi_period,
            self.params.bb_period,
            self.params.kaufman_efficiency_ratio_period,
            self.params.relative_performance_period,
            self.params.rvol_period,
        ) + 2
        if bid <= 0 or ask <= 0 or len(mid_prices) < min_required:
            return "HOLD", 0

        rsi = self._rsi(mid_prices, self.params.rsi_period)
        upper_band, middle_band, lower_band = self._bollinger_bands(
            mid_prices, self.params.bb_period, self.params.bb_stddev
        )
        kaufman_efficiency_ratio_value = self._kaufman_efficiency_ratio(mid_prices, self.params.kaufman_efficiency_ratio_period)
        kaufman_efficiency_ratio_slope = kaufman_efficiency_ratio_value - self._kaufman_efficiency_ratio(mid_prices[:-1], self.params.kaufman_efficiency_ratio_period)
        trend_score = self._trend_quality(mid_prices)
        previous_trend_score = self._trend_quality(mid_prices[:-1])
        two_bars_ago_trend_score = self._trend_quality(mid_prices[:-2])
        relative_performance_value = relative_performance(
            mid_prices, spy_prices, self.params.relative_performance_period
        )
        rvol = relative_volume(volumes, self.params.rvol_period)

        cash = float(portfolio.cash)
        shares_owned = int(portfolio.get_position(symbol))
        avg_entry = portfolio.cost_basis.get(symbol)
        current_price = mid_prices[-1]

        if shares_owned > 0:
            is_profitable = avg_entry is not None and current_price > avg_entry
            loss_trigger = (
                avg_entry is not None
                and current_price <= avg_entry * (1 - self.params.stop_loss_pct)
            )
            profit_reversal_trigger = (
                avg_entry is not None
                and current_price >= avg_entry * (1 + self.params.take_profit_pct)
                and rsi > 60
                and trend_score < 0.3
            )
            upper_band_take_profit = (
                current_price >= upper_band
                and avg_entry is not None
                and current_price >= avg_entry * (1 + self.params.take_profit_pct)
            )
            kaufman_efficiency_ratio_exit_trigger = upper_band_take_profit and (
                (kaufman_efficiency_ratio_slope < 0 and kaufman_efficiency_ratio_value < self.params.kaufman_efficiency_ratio_threshold)
                or kaufman_efficiency_ratio_value < self.params.kaufman_efficiency_ratio_threshold * 0.85
            )
            overbought_breakdown_trigger = (
                rsi >= self.params.sell_rsi and trend_score < 0.15
            )
            relative_performance_exit_trigger = (
                is_profitable
                and relative_performance_value < self.params.relative_performance_threshold
            )
            negative_trend = trend_score < 0.15
            falling_trend = (
                trend_score < previous_trend_score < two_bars_ago_trend_score
            )
            rvol_exit_trigger = (
                is_profitable
                and rvol > self.params.rvol_threshold
                and (negative_trend or falling_trend)
            )

            if (
                loss_trigger
                or profit_reversal_trigger
                or kaufman_efficiency_ratio_exit_trigger
                or overbought_breakdown_trigger
                or relative_performance_exit_trigger
                or rvol_exit_trigger
            ):
                return "SELL", shares_owned
        else:
            bb_buy_signal = (
                current_price <= lower_band
                and kaufman_efficiency_ratio_value >= self.params.kaufman_efficiency_ratio_threshold
                and (kaufman_efficiency_ratio_slope >= 0 or current_price <= middle_band)
            )
            rsi_buy_signal = rsi <= self.params.buy_rsi and kaufman_efficiency_ratio_value >= self.params.kaufman_efficiency_ratio_threshold

            if bb_buy_signal or rsi_buy_signal:
                strength = min(
                    1.5,
                    max(0.25, kaufman_efficiency_ratio_value / max(self.params.kaufman_efficiency_ratio_threshold, 1e-6)),
                )
                qty = math.floor((cash * self.params.max_cash_fraction * strength) / ask)
                if qty > 0:
                    return "BUY", qty

        return "HOLD", 0

    def _rsi(self, prices: List[float], period: int) -> float:
        gain_sum = 0.0
        loss_sum = 0.0
        for index in range(len(prices) - period, len(prices)):
            delta = prices[index] - prices[index - 1]
            if delta > 0:
                gain_sum += delta
            elif delta < 0:
                loss_sum -= delta
        if loss_sum == 0:
            return 100.0
        return 100 - (100 / (1 + gain_sum / loss_sum))

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

    def _bollinger_bands(
        self, prices: List[float], period: int, num_std: float
    ) -> tuple[float, float, float]:
        recent = prices[-period:]
        middle = sum(recent) / period
        variance = sum((price - middle) ** 2 for price in recent) / period
        std_dev = variance ** 0.5
        return middle + num_std * std_dev, middle, middle - num_std * std_dev

    def _kaufman_efficiency_ratio(self, prices: List[float], period: int) -> float:
        if len(prices) < period + 1:
            return 0.0
        total_upward_change = 0.0
        total_downward_change = 0.0
        total_price_movement = 0.0
        for index in range(len(prices) - period, len(prices)):
            change = prices[index] - prices[index - 1]
            total_price_movement += abs(change)
            if change > 0:
                total_upward_change += change
            elif change < 0:
                total_downward_change -= change
        if total_price_movement <= 0:
            return 0.0
        return 100.0 * abs(total_upward_change - total_downward_change) / total_price_movement