from dataclasses import dataclass
from typing import List
import math

from backtest.portfolio import Portfolio
from penguins.base_penguin import BasePenguin


# Manual tuning block:
# Adjust these values here first so the strategy is easy to finetune by hand.
BB_PERIOD = 20 #20
BB_STDDEV = 2.0
ADX_PERIOD = 14
ADX_THRESHOLD = 25.0
MAX_CASH_FRACTION = 0.05
STOP_LOSS_PCT = 0.04
TAKE_PROFIT_PCT = 0.08
COOLDOWN_BARS = 10
STRENGTH_CAP = 1.5


# Trainable Penguin, with Buy condition based on Bollinger Bands
# and the Amount by ADX compared between different Stocks,
# and Sell condition based on ADX trend reversal and taking profit at the upper Bollinger Band.


@dataclass
class OG_TP2Params:
    bb_period: int = BB_PERIOD
    bb_stddev: float = BB_STDDEV
    adx_period: int = ADX_PERIOD
    adx_threshold: float = ADX_THRESHOLD
    max_cash_fraction: float = MAX_CASH_FRACTION
    stop_loss_pct: float = STOP_LOSS_PCT
    take_profit_pct: float = TAKE_PROFIT_PCT
    cooldown_bars: int = COOLDOWN_BARS
    strength_cap: float = STRENGTH_CAP


class OG_TP2(BasePenguin):
    LOOKBACK_BARS = 120
    TRAINABLE = True

    def __init__(
        self,
        name: str = "TrainablePenguin2",
        bb_period: int = BB_PERIOD,
        bb_stddev: float = BB_STDDEV,
        adx_period: int = ADX_PERIOD,
        adx_threshold: float = ADX_THRESHOLD,
        max_cash_fraction_per_trade: float = MAX_CASH_FRACTION,
        stop_loss_pct: float = STOP_LOSS_PCT,
        take_profit_pct: float = TAKE_PROFIT_PCT,
        cooldown_bars: int = COOLDOWN_BARS,
        strength_cap: float = STRENGTH_CAP,
    ):
        super().__init__(name)
        self.params = OG_TP2Params(
            bb_period=bb_period,
            bb_stddev=bb_stddev,
            adx_period=adx_period,
            adx_threshold=adx_threshold,
            max_cash_fraction=max_cash_fraction_per_trade,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            cooldown_bars=cooldown_bars,
            strength_cap=strength_cap,
        )

    def decide(
        self,
        symbol: str,
        mid_prices: List[float],
        bid: float,
        ask: float,
        portfolio: Portfolio,
    ) -> tuple[str, int]:
        min_required = max(self.params.bb_period, self.params.adx_period) + 2
        if bid <= 0 or ask <= 0 or len(mid_prices) < min_required:
            return "HOLD", 0

        upper_band, middle_band, lower_band = self._bollinger_bands(
            mid_prices,
            self.params.bb_period,
            self.params.bb_stddev,
        )
        adx_value = self._adx_proxy(mid_prices, self.params.adx_period)
        adx_previous = self._adx_proxy(mid_prices[:-1], self.params.adx_period)
        adx_slope = adx_value - adx_previous

        cash = self._get_cash(portfolio)
        shares_owned = self._get_position(portfolio, symbol)
        avg_entry = self._get_avg_entry(portfolio, symbol)
        current_price = mid_prices[-1]

        if shares_owned > 0:
            # SELL part
            loss_trigger = (
                avg_entry is not None
                and current_price <= avg_entry * (1 - self.params.stop_loss_pct)
            )
            upper_band_take_profit = (
                current_price >= upper_band
                and avg_entry is not None
                and current_price >= avg_entry * (1 + self.params.take_profit_pct)
            )
            adx_trend_reversal = adx_slope < 0 and adx_value < self.params.adx_threshold

            if loss_trigger or (upper_band_take_profit and adx_trend_reversal) or (
                upper_band_take_profit and adx_value < self.params.adx_threshold * 0.85
            ):
                return "SELL", shares_owned
        else:
            # BUY part
            buy_signal = current_price <= lower_band and adx_value >= self.params.adx_threshold
            trend_confirmation = adx_slope >= 0 or current_price <= middle_band

            if buy_signal and trend_confirmation:
                # AMOUNT part
                strength = min(
                    self.params.strength_cap,
                    max(0.25, adx_value / max(self.params.adx_threshold, 1e-6)),
                )
                max_trade_value = cash * self.params.max_cash_fraction
                qty = math.floor((max_trade_value * strength) / ask)
                if qty > 0:
                    return "BUY", qty

        return "HOLD", 0

    def _bollinger_bands(self, prices: List[float], period: int, num_std: float) -> tuple[float, float, float]:
        recent = prices[-period:]
        middle = sum(recent) / period
        variance = sum((price - middle) ** 2 for price in recent) / period
        std_dev = variance ** 0.5
        upper = middle + num_std * std_dev
        lower = middle - num_std * std_dev
        return upper, middle, lower

    def _adx_proxy(self, prices: List[float], period: int) -> float:
        if len(prices) < period + 1:
            return 0.0

        directional_up = 0.0
        directional_down = 0.0
        true_range = 0.0

        start = len(prices) - period
        for index in range(start, len(prices)):
            change = prices[index] - prices[index - 1]
            true_range += abs(change)
            if change > 0:
                directional_up += change
            elif change < 0:
                directional_down -= change

        if true_range <= 0:
            return 0.0

        directional_strength = abs(directional_up - directional_down) / true_range
        return 100.0 * directional_strength

    def _get_cash(self, portfolio: Portfolio) -> float:
        return float(portfolio.cash)

    def _get_position(self, portfolio: Portfolio, symbol: str) -> int:
        return int(portfolio.get_position(symbol))

    def _get_avg_entry(self, portfolio: Portfolio, symbol: str) -> float | None:
        return portfolio.cost_basis.get(symbol)


class OG_TP2_Manual(OG_TP2):
    TRAINABLE = False

    def __init__(
        self,
        name: str = "TrainablePenguin2_Manual",
        bb_period: int = BB_PERIOD,
        bb_stddev: float = BB_STDDEV,
        adx_period: int = ADX_PERIOD,
        adx_threshold: float = ADX_THRESHOLD,
        max_cash_fraction_per_trade: float = MAX_CASH_FRACTION,
        stop_loss_pct: float = STOP_LOSS_PCT,
        take_profit_pct: float = TAKE_PROFIT_PCT,
        cooldown_bars: int = COOLDOWN_BARS,
        strength_cap: float = STRENGTH_CAP,
    ):
        super().__init__(
            name=name,
            bb_period=bb_period,
            bb_stddev=bb_stddev,
            adx_period=adx_period,
            adx_threshold=adx_threshold,
            max_cash_fraction_per_trade=max_cash_fraction_per_trade,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            cooldown_bars=cooldown_bars,
            strength_cap=strength_cap,
        )