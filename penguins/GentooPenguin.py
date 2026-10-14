from dataclasses import dataclass
import math
from typing import List

from backtest.portfolio import Portfolio
from penguins.base_penguin import BasePenguin
from penguins.decision_utils import (
    adx_proxy,
    rsi,
    relative_strength,
    relative_volume,
)


@dataclass
class GentooPenguinParams:
    rsi_period: int
    buy_rsi: float
    sell_rsi: float
    max_cash_fraction: float
    stop_loss_pct: float
    take_profit_pct: float
    relative_strength_period: int
    relative_strength_threshold: float
    rvol_period: int
    rvol_threshold: float
    adx_period: int
    adx_threshold: float
    adx_entry_threshold: float
    adx_negative_threshold: float


class GentooPenguin(BasePenguin):
    def __init__(
        self,
        name: str = "GentooPenguin",
        **parameters: int | float,
    ):
        super().__init__(name)
        self.params = GentooPenguinParams(**parameters)

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
            self.params.relative_strength_period,
            self.params.rvol_period,
            self.params.adx_period,
        ) + 2
        if bid <= 0 or ask <= 0 or len(mid_prices) < min_required:
            return "HOLD", 0

        rsi_value = rsi(mid_prices, self.params.rsi_period)
        adx_value = adx_proxy(mid_prices, self.params.adx_period)
        previous_adx_value = adx_proxy(mid_prices[:-1], self.params.adx_period)
        two_bars_ago_adx_value = adx_proxy(mid_prices[:-2], self.params.adx_period)
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

            rsi_overbought = rsi_value >= self.params.sell_rsi

            weak_adx = adx_value < self.params.adx_threshold

            take_profit_trigger = (
                (profit_threshold_reached or rsi_overbought)
                and
                (weak_adx)
            )

            #rel Strength
            relative_strength_exit_trigger = (
                avg_entry is not None
                and relative_strength_value < self.params.relative_strength_threshold
            )

            #Rel Volume            
            negative_adx = adx_value < self.params.adx_negative_threshold
            falling_adx = (
                adx_value < previous_adx_value
                and adx_value < two_bars_ago_adx_value
           )
            rvol_exit_trigger = (
                rvol > self.params.rvol_threshold
                and (negative_adx and falling_adx)
            )

            if (
                loss_trigger
                or take_profit_trigger
                or relative_strength_exit_trigger
                or rvol_exit_trigger
            ):
                return "SELL", shares_owned

        # ============================== BUY AMOUNT =============================
        rsi_buy_signal = rsi_value <= self.params.buy_rsi
        if (
            shares_owned == 0
            and rsi_buy_signal
            and adx_value >= self.params.adx_entry_threshold
        ):
            strength = min(
                1.5,
                max(0.25, adx_value / self.params.adx_entry_threshold),
            )
            qty = math.floor((cash * self.params.max_cash_fraction * strength) / ask)
            if qty > 0:
                return "BUY", qty

        return "HOLD", 0
