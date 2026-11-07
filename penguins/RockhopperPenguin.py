from dataclasses import dataclass
import math
from typing import List

from backtest.portfolio import Portfolio
from penguins.base_penguin import BasePenguin
from penguins.decision_utils import (
    bollinger_bands,
    relative_performance,
    relative_volume,
    trend_quality,
)






@dataclass
class RockhopperPenguinParams:
    bb_period: int
    bb_stddev: float
    upper_band_buffer: float
    max_cash_fraction: float
    stop_loss_pct: float
    take_profit_pct: float
    relative_performance_period: int
    relative_performance_threshold: float
    rvol_period: int
    rvol_threshold: float
    trend_reversal_threshold: float
    trend_entry_threshold: float
    cooldown_bars: int = 0


class RockhopperPenguin(BasePenguin):
    COVERAGE_FIXED_WINDOWS = (10, 30, 60)  # trend_quality's fixed moving averages.

    def __init__(
        self,
        name: str = "RockhopperPenguin",
        **parameters: int | float,
    ):
        super().__init__(name)
        self._last_trade_bar: dict[str, int] = {}
        self._decision_bar: dict[str, int] = {}
        self.params = RockhopperPenguinParams(**parameters)

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
            self.params.bb_period,
            self.params.relative_performance_period,
            self.params.rvol_period,
        ) + 2
        if bid <= 0 or ask <= 0 or len(mid_prices) < min_required:
            return "HOLD", 0

        upper_band, middle_band, lower_band = bollinger_bands(
            mid_prices, self.params.bb_period, self.params.bb_stddev
        )
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

        # ================================ SELL ================================
        if shares_owned > 0:
            #Stop loss
            loss_trigger = (
                avg_entry is not None
                and current_price <= avg_entry * (1 - self.params.stop_loss_pct)
            )
            #Take profit
            profit_threshold_reached = (
                avg_entry is not None
                and current_price >= avg_entry * (1 + self.params.take_profit_pct)
            )
            band_width = upper_band - lower_band

            upper_band_reached = (
                current_price >= upper_band
                + self.params.upper_band_buffer * band_width
            )
            
            weak_trend = trend_score < self.params.trend_reversal_threshold

            take_profit_trigger = (
                (profit_threshold_reached or upper_band_reached)
                and
                (weak_trend)
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
            rvol_exit_trigger = (
                rvol > self.params.rvol_threshold
                and (weak_trend and falling_trend)
            )

            if (
                loss_trigger
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

        if (
            shares_owned == 0
            and current_price <= lower_band
            and trend_score > self.params.trend_entry_threshold
        ):
            strength = min(
                2.0,
                max(0.25, trend_score /self.params.trend_entry_threshold),
            )
            qty = math.floor((cash * self.params.max_cash_fraction * strength) / ask)
            if qty > 0:
                self._last_trade_bar[symbol] = current_bar
                return "BUY", qty

        return "HOLD", 0
