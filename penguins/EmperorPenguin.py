from dataclasses import dataclass
import math
from typing import List

from backtest.portfolio import Portfolio
from penguins.base_penguin import BasePenguin
from penguins.decision_utils import (
    ker,
    bollinger_bands,
    relative_performance,
    relative_volume,
    rsi,
    trend_quality,
)




@dataclass
class EmperorPenguinParams:
    rsi_period: int
    buy_rsi: float
    sell_rsi: float
    bb_period: int
    bb_stddev: float
    upper_band_buffer: float
    ker_period: int
    ker_reversal_threshold: float
    ker_entry_threshold: float
    trend_reversal_threshold: float
    trend_entry_threshold: float
    max_cash_fraction: float
    stop_loss_pct: float
    take_profit_pct: float
    cooldown_bars: int
    relative_performance_period: int
    relative_performance_threshold: float
    rvol_period: int
    rvol_threshold: float


class EmperorPenguin(BasePenguin):
    COVERAGE_FIXED_WINDOWS = (10, 30, 60)

    def __init__(
        self,
        name: str = "EmperorPenguin",
        **parameters: int | float,
    ):
        super().__init__(name)
        self._last_trade_bar: dict[str, int] = {}
        self._decision_bar: dict[str, int] = {}
        self.params = EmperorPenguinParams(**parameters)

    def decide(
        self,
        symbol: str,
        mid_prices: List[float],
        low_price: float,
        high_price: float,
        portfolio: Portfolio,
        spy_prices: List[float] | None = None, 
        volumes: List[float] | None = None,
    ) -> tuple[str, float]:
        min_required = max(
            60,
            self.params.rsi_period,
            self.params.bb_period,
            self.params.ker_period,
            self.params.relative_performance_period,
            self.params.rvol_period,
        ) + 2
        if low_price <= 0 or high_price <= 0 or len(mid_prices) < min_required:
            return "HOLD", 0

        rsi_value = rsi(mid_prices, self.params.rsi_period)
        upper_band, middle_band, lower_band = bollinger_bands(
            mid_prices, self.params.bb_period, self.params.bb_stddev
        )
        ker_value = ker(mid_prices, self.params.ker_period)
        previous_ker_value = ker(
            mid_prices[:-1], self.params.ker_period
        )
        two_bars_ago_ker_value = ker(
            mid_prices[:-2], self.params.ker_period
        )
        trend_score = trend_quality(mid_prices)
        previous_trend_score = trend_quality(mid_prices[:-1])
        two_bars_ago_trend_score = trend_quality(mid_prices[:-2])
        relative_performance_value = relative_performance(
            mid_prices, spy_prices, self.params.relative_performance_period
        )
        rvol = relative_volume(volumes, self.params.rvol_period)

        cash = float(portfolio.cash)
        shares_owned = portfolio.get_position(symbol)
        avg_entry = portfolio.cost_basis.get(symbol)
        current_price = mid_prices[-1]
        current_bar = self._decision_bar.get(symbol, 0) + 1
        self._decision_bar[symbol] = current_bar

        # ================================ SELL ================================
        if shares_owned > 0:
            #Stop loss
            loss_trigger = (
                avg_entry is not None
                and current_price <= avg_entry * (1 - self.params.stop_loss_pct)
            )
            #Take profit
            take_profit_trigger = (
                avg_entry is not None
                and current_price >= avg_entry * (1 + self.params.take_profit_pct)
            )

            # BB and RSI dependent on trend and KER

            rsi_overbought = rsi_value >= self.params.sell_rsi

            band_width = upper_band - lower_band

            upper_band_reached = (
                current_price >= upper_band
                + self.params.upper_band_buffer * band_width
            )
            weak_trend = trend_score < self.params.trend_reversal_threshold

            weak_ker = ker_value < self.params.ker_reversal_threshold

            sell_profit_trigger = (
                (rsi_overbought or upper_band_reached)
                and
                (weak_trend or weak_ker)
            )
            # Relative performance
            relative_performance_exit_trigger = (
                avg_entry is not None
                and relative_performance_value < self.params.relative_performance_threshold
            )
            #Rel Volume
            falling_trend = (
                trend_score < previous_trend_score
                and trend_score < two_bars_ago_trend_score
            )
            falling_ker = (
                ker_value < previous_ker_value
                and ker_value < two_bars_ago_ker_value
            )
            # Accept either Gentoo's ER signal or Rockhopper's TrendQuality signal.
            rvol_exit_trigger = (
                rvol > self.params.rvol_threshold
                and (
                    (weak_ker and falling_ker)
                    or (weak_trend and falling_trend)
                )
            )


            if (
                loss_trigger
                or sell_profit_trigger
                or take_profit_trigger
                or relative_performance_exit_trigger
                or rvol_exit_trigger
            ):
                self._last_trade_bar[symbol] = current_bar
                return "SELL", shares_owned

        # ============================== BUY AMOUNT =============================
        last_trade_bar = self._last_trade_bar.get(symbol)
        if (
            self.params.cooldown_bars > 0
            and last_trade_bar is not None
            and current_bar - last_trade_bar < self.params.cooldown_bars
        ):
            return "HOLD", 0

        bb_buy_signal = (
            current_price <= lower_band
        )
        trend_strength_signal = (
            ker_value >= self.params.ker_entry_threshold
            or trend_score >= self.params.trend_entry_threshold
        )
        rsi_buy_signal = rsi_value <= self.params.buy_rsi

        if trend_strength_signal and (bb_buy_signal or rsi_buy_signal):
            ker_strength = ker_value / self.params.ker_entry_threshold
            trend_strength = trend_score / self.params.trend_entry_threshold
            strength = min(
                2.0,
                max(0.25, ker_strength, trend_strength),
            )
            qty = math.floor((cash * self.params.max_cash_fraction * strength) / high_price)
            if qty > 0:
                self._last_trade_bar[symbol] = current_bar
                return "BUY", qty

        return "HOLD", 0
