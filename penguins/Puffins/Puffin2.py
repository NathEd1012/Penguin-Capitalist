from dataclasses import dataclass
import math
from typing import List

from backtest.portfolio import Portfolio
from indicators.market_context import relative_strength, relative_volume
from .Puffin1 import (
    BB_PERIOD,
    BB_STDDEV,
    BUY_RSI,
    COOLDOWN_BARS,
    MAX_CASH_FRACTION,
    RELATIVE_STRENGTH_PERIOD,
    RELATIVE_STRENGTH_THRESHOLD,
    RSI_PERIOD,
    SELL_RSI,
    STOP_LOSS_PCT,
    TAKE_PROFIT_PCT,
    RVOL_PERIOD,
    RVOL_THRESHOLD,
    Puffin1,
)


ADX_PERIOD = 14
ADX_THRESHOLD = 25.0


@dataclass
class Puffin2Params:
    rsi_period: int = RSI_PERIOD
    buy_rsi: float = BUY_RSI
    sell_rsi: float = SELL_RSI
    bb_period: int = BB_PERIOD
    bb_stddev: float = BB_STDDEV
    adx_period: int = ADX_PERIOD
    adx_threshold: float = ADX_THRESHOLD
    max_cash_fraction: float = MAX_CASH_FRACTION
    stop_loss_pct: float = STOP_LOSS_PCT
    take_profit_pct: float = TAKE_PROFIT_PCT
    cooldown_bars: int = COOLDOWN_BARS
    relative_strength_period: int = RELATIVE_STRENGTH_PERIOD
    relative_strength_threshold: float = RELATIVE_STRENGTH_THRESHOLD
    rvol_period: int = RVOL_PERIOD
    rvol_threshold: float = RVOL_THRESHOLD


class Puffin2(Puffin1):
    def __init__(
        self,
        name: str = "Puffin2",
        rsi_period: int = RSI_PERIOD,
        buy_rsi: float = BUY_RSI,
        sell_rsi: float = SELL_RSI,
        bb_period: int = BB_PERIOD,
        bb_stddev: float = BB_STDDEV,
        adx_period: int = ADX_PERIOD,
        adx_threshold: float = ADX_THRESHOLD,
        max_cash_fraction: float = MAX_CASH_FRACTION,
        stop_loss_pct: float = STOP_LOSS_PCT,
        take_profit_pct: float = TAKE_PROFIT_PCT,
        cooldown_bars: int = COOLDOWN_BARS,
        relative_strength_period: int = RELATIVE_STRENGTH_PERIOD,
        relative_strength_threshold: float = RELATIVE_STRENGTH_THRESHOLD,
        rvol_period: int = RVOL_PERIOD,
        rvol_threshold: float = RVOL_THRESHOLD,
    ):
        super().__init__(name)
        self._last_trade_bar: dict[str, int] = {}
        self._decision_bar: dict[str, int] = {}
        self.params = Puffin2Params(
            rsi_period=rsi_period,
            buy_rsi=buy_rsi,
            sell_rsi=sell_rsi,
            bb_period=bb_period,
            bb_stddev=bb_stddev,
            adx_period=adx_period,
            adx_threshold=adx_threshold,
            max_cash_fraction=max_cash_fraction,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            cooldown_bars=cooldown_bars,
            relative_strength_period=relative_strength_period,
            relative_strength_threshold=relative_strength_threshold,
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
            self.params.adx_period,
            self.params.relative_strength_period,
            self.params.rvol_period,
        ) + 2
        if bid <= 0 or ask <= 0 or len(mid_prices) < min_required:
            return "HOLD", 0

        rsi = self._rsi(mid_prices, self.params.rsi_period)
        upper_band, _, lower_band = self._bollinger_bands(
            mid_prices, self.params.bb_period, self.params.bb_stddev
        )
        adx_value = self._adx_proxy(mid_prices, self.params.adx_period)
        previous_adx = self._adx_proxy(mid_prices[:-1], self.params.adx_period)
        two_bars_ago_adx = self._adx_proxy(mid_prices[:-2], self.params.adx_period)
        weak_adx_threshold = self.params.adx_threshold * 0.85
        relative_strength_value = relative_strength(
            mid_prices, spy_prices, self.params.relative_strength_period
        )
        rvol = relative_volume(volumes, self.params.rvol_period)

        cash = float(portfolio.cash)
        shares_owned = int(portfolio.get_position(symbol))
        avg_entry = portfolio.cost_basis.get(symbol)
        current_price = mid_prices[-1]
        current_bar = self._decision_bar.get(symbol, 0) + 1
        self._decision_bar[symbol] = current_bar

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
                and adx_value < self.params.adx_threshold
            )
            upper_band_take_profit = (
                current_price >= upper_band
                and avg_entry is not None
                and current_price >= avg_entry * (1 + self.params.take_profit_pct)
            )
            adx_exit_trigger = upper_band_take_profit and (
                (
                    adx_value < previous_adx
                    and adx_value < self.params.adx_threshold
                )
                or adx_value < weak_adx_threshold
            )
            overbought_breakdown_trigger = (
                rsi >= self.params.sell_rsi and adx_value < weak_adx_threshold
            )
            relative_strength_exit_trigger = (
                is_profitable
                and relative_strength_value < self.params.relative_strength_threshold
            )
            falling_adx = adx_value < previous_adx < two_bars_ago_adx
            rvol_exit_trigger = (
                is_profitable
                and rvol > self.params.rvol_threshold
                and (adx_value < weak_adx_threshold or falling_adx)
            )

            if (
                loss_trigger
                or profit_reversal_trigger
                or adx_exit_trigger
                or overbought_breakdown_trigger
                or relative_strength_exit_trigger
                or rvol_exit_trigger
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

        bb_buy_signal = (
            current_price <= lower_band
            and adx_value > self.params.adx_threshold
        )
        rsi_buy_signal = (
            rsi <= self.params.buy_rsi
            and adx_value >= self.params.adx_threshold
        )

        if bb_buy_signal or rsi_buy_signal:
            strength = min(
                1.5,
                max(
                    0.25,
                    adx_value / max(self.params.adx_threshold, 1e-6),
                ),
            )
            qty = math.floor((cash * self.params.max_cash_fraction * strength) / ask)
            if qty > 0:
                self._last_trade_bar[symbol] = current_bar
                return "BUY", qty

        return "HOLD", 0

    def _adx_proxy(self, prices: List[float], period: int) -> float:
        if len(prices) < period + 1:
            return 0.0
        directional_up = 0.0
        directional_down = 0.0
        true_range = 0.0
        for index in range(len(prices) - period, len(prices)):
            change = prices[index] - prices[index - 1]
            true_range += abs(change)
            if change > 0:
                directional_up += change
            elif change < 0:
                directional_down -= change
        if true_range <= 0:
            return 0.0
        return 100.0 * abs(directional_up - directional_down) / true_range