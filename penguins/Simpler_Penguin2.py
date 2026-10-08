from dataclasses import dataclass
import math
from typing import List

from backtest.portfolio import Portfolio
from penguins.base_penguin import BasePenguin
from penguins.decision_utils import (
    bollinger_bands,
    relative_strength,
    relative_volume,
    trend_quality,
)


@dataclass
class Simpler_Penguin2Params:
    bb_period: int
    bb_stddev: float
    upper_band_buffer: float
    max_cash_fraction: float
    stop_loss_pct: float
    take_profit_pct: float
    relative_strength_period: int
    relative_strength_threshold: float
    rvol_period: int
    rvol_threshold: float
    trend_reversal_threshold: float
    trend_negative_threshold: float
    trend_entry_threshold: float


class Simpler_Penguin2(BasePenguin):
    LOOKBACK_BARS = 120

    def __init__(
        self,
        name: str = "Simpler_Penguin",
        **parameters: int | float,
    ):
        super().__init__(name)
        self.params = Simpler_Penguin2Params(**parameters)

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
            self.params.relative_strength_period,
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
        relative_strength_value = relative_strength(
            mid_prices, spy_prices, self.params.relative_strength_period
        )
        rvol = relative_volume(volumes, self.params.rvol_period)

        cash = float(portfolio.cash)
        shares_owned = int(portfolio.get_position(symbol))
        avg_entry = portfolio.cost_basis.get(symbol)
        current_price = mid_prices[-1]

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
            #rel Strength
            relative_strength_exit_trigger = (
                avg_entry is not None
                and relative_strength_value < self.params.relative_strength_threshold
            )
            #Rel Volume
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
                or relative_strength_exit_trigger
                or rvol_exit_trigger
            ):
                return "SELL", shares_owned

        # ============================== BUY AMOUNT =============================
        if (
            shares_owned == 0
            and current_price <= lower_band
            and trend_score > self.params.trend_entry_threshold
        ):
            strength = min(
                1.5,
                max(0.25, trend_score /self.params.trend_entry_threshold),
            )
            qty = math.floor((cash * self.params.max_cash_fraction * strength) / ask)
            if qty > 0:
                return "BUY", qty

        return "HOLD", 0
