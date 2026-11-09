from dataclasses import dataclass
import math
from typing import List

from backtest.portfolio import Portfolio
from penguins.base_penguin import BasePenguin
from penguins.decision_utils import (
    ker,
    rsi,
    relative_performance,
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
    relative_performance_period: int
    relative_performance_threshold: float
    rvol_period: int
    rvol_threshold: float
    ker_period: int
    ker_reversal_threshold: float
    ker_entry_threshold: float
    cooldown_bars: int = 0


class GentooPenguin(BasePenguin):
    def __init__(
        self,
        name: str = "GentooPenguin",
        **parameters: int | float,
    ):
        super().__init__(name)
        self._last_trade_bar: dict[str, int] = {}
        self._decision_bar: dict[str, int] = {}
        self.params = GentooPenguinParams(**parameters)

    def decide(
        self,
        symbol: str,
        mid_prices: List[float],
        low_price: float,
        high_price: float,
        portfolio: Portfolio,
        spy_prices: List[float] | None = None,
        volumes: List[float] | None = None,
    ) -> tuple[str, int]:
        min_required = max(
            60,
            self.params.rsi_period,
            self.params.relative_performance_period,
            self.params.rvol_period,
            self.params.ker_period,
        ) + 2
        if low_price <= 0 or high_price <= 0 or len(mid_prices) < min_required:
            return "HOLD", 0

        rsi_value = rsi(mid_prices, self.params.rsi_period)
        ker_value = ker(mid_prices, self.params.ker_period)
        previous_ker_value = ker(mid_prices[:-1], self.params.ker_period)
        two_bars_ago_ker_value = ker(mid_prices[:-2], self.params.ker_period)
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

            rsi_overbought = rsi_value >= self.params.sell_rsi

            weak_ker = ker_value < self.params.ker_reversal_threshold

            take_profit_trigger = (
                (profit_threshold_reached or rsi_overbought)
                and
                (weak_ker)
            )

            # Relative performance
            relative_performance_exit_trigger = (
                avg_entry is not None
                and relative_performance_value < self.params.relative_performance_threshold
            )

            #Rel Volume            
            falling_ker = (
                ker_value < previous_ker_value
                and ker_value < two_bars_ago_ker_value
           )
            rvol_exit_trigger = (
                rvol > self.params.rvol_threshold
                and (weak_ker and falling_ker)
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

        rsi_buy_signal = rsi_value <= self.params.buy_rsi
        if (
            shares_owned == 0
            and rsi_buy_signal
            and ker_value >= self.params.ker_entry_threshold
        ):
            strength = min(
                2.0,
                max(0.25, ker_value / self.params.ker_entry_threshold),
            )
            qty = math.floor((cash * self.params.max_cash_fraction * strength) / high_price)
            if qty > 0:
                self._last_trade_bar[symbol] = current_bar
                return "BUY", qty

        return "HOLD", 0
