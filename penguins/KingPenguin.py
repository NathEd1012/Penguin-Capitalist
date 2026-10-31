from dataclasses import dataclass
import math
from typing import List

from backtest.portfolio import Portfolio
from penguins.base_penguin import BasePenguin
from penguins.decision_utils import (
    kaufman_efficiency_ratio,
    bollinger_bands,
    relative_performance,
    relative_volume,
    rsi,
    trend_quality,
)


@dataclass
class KingPenguinParams:
    rsi_period: int
    buy_rsi: float
    sell_rsi: float
    bb_period: int
    bb_stddev: float
    upper_band_buffer: float
    kaufman_efficiency_ratio_period: int
    kaufman_efficiency_ratio_threshold: float
    trend_reversal_threshold: float
    trend_negative_threshold: float
    trend_entry_threshold: float
    max_cash_fraction: float
    stop_loss_pct: float
    take_profit_pct: float
    cooldown_bars: int
    relative_performance_period: int
    relative_performance_threshold: float
    rvol_period: int
    rvol_threshold: float
    sr_low_threshhold: float
    sr_high_threshhold: float
    sr_period: int


class KingPenguin(BasePenguin):
    COVERAGE_FIXED_WINDOWS = (10, 30, 60)

    def __init__(
        self,
        name: str = "KingPenguin",
        **parameters: int | float,
    ):
        super().__init__(name)
        self._last_trade_bar: dict[str, int] = {}
        self._decision_bar: dict[str, int] = {}
        self.params = KingPenguinParams(**parameters)

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
            self.params.sr_period,
        ) + 2
        if bid <= 0 or ask <= 0 or len(mid_prices) < min_required:
            return "HOLD", 0

        rsi_value = rsi(mid_prices, self.params.rsi_period)
        upper_band, middle_band, lower_band = bollinger_bands(
            mid_prices, self.params.bb_period, self.params.bb_stddev
        )
        kaufman_efficiency_ratio_value = kaufman_efficiency_ratio(mid_prices, self.params.kaufman_efficiency_ratio_period)
        trend_score = trend_quality(mid_prices)
        previous_trend_score = trend_quality(mid_prices[:-1])
        two_bars_ago_trend_score = trend_quality(mid_prices[:-2])
        relative_performance_value = relative_performance(
            mid_prices, spy_prices, self.params.relative_performance_period
        )
        rvol = relative_volume(volumes, self.params.rvol_period)

        cash = float(portfolio.cash)
        shares_owned = int(portfolio.get_position(symbol))
        avg_entry = portfolio.cost_basis.get(symbol)
        current_price = mid_prices[-1]
        current_bar = self._decision_bar.get(symbol, 0) + 1
        self._decision_bar[symbol] = current_bar
        sr_prices = mid_prices[-self.params.sr_period - 1 : -1]
        sr_high = max(sr_prices)
        sr_low = min(sr_prices)
        sr_buy_signal = current_price > sr_high * (1 + self.params.sr_high_threshhold)
        sr_sell_signal = current_price < sr_low * (1 - self.params.sr_low_threshhold)

        if shares_owned > 0:
            loss_trigger = (
                avg_entry is not None
                and current_price <= avg_entry * (1 - self.params.stop_loss_pct)
            )
            profit_threshold_reached = (
                avg_entry is not None
                and current_price >= avg_entry * (1 + self.params.take_profit_pct)
            )

            rsi_overbought = rsi_value >= self.params.sell_rsi
            band_width = upper_band - lower_band
            upper_band_reached = (
                current_price >= upper_band
                + self.params.upper_band_buffer * band_width
            )
            weak_trend = trend_score < self.params.trend_reversal_threshold
            weak_kaufman_efficiency_ratio = kaufman_efficiency_ratio_value < self.params.kaufman_efficiency_ratio_threshold
            take_profit_trigger = (
                (profit_threshold_reached or rsi_overbought or upper_band_reached)
                and (weak_trend or weak_kaufman_efficiency_ratio)
            )
            relative_performance_exit_trigger = (
                avg_entry is not None
                and relative_performance_value < self.params.relative_performance_threshold
            )
            negative_trend = trend_score < self.params.trend_negative_threshold
            falling_trend = (
                trend_score < previous_trend_score
                and trend_score < two_bars_ago_trend_score
            )
            rvol_exit_trigger = (
                rvol > self.params.rvol_threshold
                and (negative_trend and falling_trend)
            )

            if (
                loss_trigger
                or take_profit_trigger
                or relative_performance_exit_trigger
                or rvol_exit_trigger
                or sr_sell_signal
            ):
                self._last_trade_bar[symbol] = current_bar
                return "SELL", shares_owned

        last_trade_bar = self._last_trade_bar.get(symbol)
        if (
            self.params.cooldown_bars > 0
            and last_trade_bar is not None
            and current_bar - last_trade_bar < self.params.cooldown_bars
        ):
            return "HOLD", 0

        bb_buy_signal = current_price <= lower_band
        trend_strength_signal = (
            kaufman_efficiency_ratio_value >= self.params.kaufman_efficiency_ratio_threshold
            or trend_score >= self.params.trend_entry_threshold
        )
        rsi_buy_signal = rsi_value <= self.params.buy_rsi

        if sr_buy_signal or (trend_strength_signal and (bb_buy_signal or rsi_buy_signal)):
            kaufman_efficiency_ratio_strength = kaufman_efficiency_ratio_value / self.params.kaufman_efficiency_ratio_threshold
            trend_strength = trend_score / self.params.trend_entry_threshold
            strength = min(
                1.5,
                max(0.25, kaufman_efficiency_ratio_strength, trend_strength),
            )
            qty = math.floor((cash * self.params.max_cash_fraction * strength) / ask)
            if qty > 0:
                self._last_trade_bar[symbol] = current_bar
                return "BUY", qty

        return "HOLD", 0
