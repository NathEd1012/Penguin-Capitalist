from dataclasses import dataclass
import math
from typing import List

from backtest.portfolio import Portfolio

from .common import TrainablePenguinCommon


TRAINABLE_PENGUIN2_BB_PERIOD = 20
TRAINABLE_PENGUIN2_BB_STDDEV = 2.0
TRAINABLE_PENGUIN2_ADX_PERIOD = 14
TRAINABLE_PENGUIN2_ADX_THRESHOLD = 25.0
TRAINABLE_PENGUIN2_MAX_CASH_FRACTION = 0.05
TRAINABLE_PENGUIN2_STOP_LOSS_PCT = 0.04
TRAINABLE_PENGUIN2_TAKE_PROFIT_PCT = 0.08
TRAINABLE_PENGUIN2_COOLDOWN_BARS = 10


@dataclass
class TrainablePenguin2Params:
    bb_period: int = TRAINABLE_PENGUIN2_BB_PERIOD
    bb_stddev: float = TRAINABLE_PENGUIN2_BB_STDDEV
    adx_period: int = TRAINABLE_PENGUIN2_ADX_PERIOD
    adx_threshold: float = TRAINABLE_PENGUIN2_ADX_THRESHOLD
    max_cash_fraction: float = TRAINABLE_PENGUIN2_MAX_CASH_FRACTION
    stop_loss_pct: float = TRAINABLE_PENGUIN2_STOP_LOSS_PCT
    take_profit_pct: float = TRAINABLE_PENGUIN2_TAKE_PROFIT_PCT
    cooldown_bars: int = TRAINABLE_PENGUIN2_COOLDOWN_BARS


class TrainablePenguin2(TrainablePenguinCommon):
    LOOKBACK_BARS = 120

    def __init__(self, name: str = "TrainablePenguin2", bb_period: int = TRAINABLE_PENGUIN2_BB_PERIOD, bb_stddev: float = TRAINABLE_PENGUIN2_BB_STDDEV, adx_period: int = TRAINABLE_PENGUIN2_ADX_PERIOD, adx_threshold: float = TRAINABLE_PENGUIN2_ADX_THRESHOLD, max_cash_fraction_per_trade: float = TRAINABLE_PENGUIN2_MAX_CASH_FRACTION, stop_loss_pct: float = TRAINABLE_PENGUIN2_STOP_LOSS_PCT, take_profit_pct: float = TRAINABLE_PENGUIN2_TAKE_PROFIT_PCT, cooldown_bars: int = TRAINABLE_PENGUIN2_COOLDOWN_BARS):
        super().__init__(name)
        self.params = TrainablePenguin2Params(
            bb_period=bb_period,
            bb_stddev=bb_stddev,
            adx_period=adx_period,
            adx_threshold=adx_threshold,
            max_cash_fraction=max_cash_fraction_per_trade,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            cooldown_bars=cooldown_bars,
        )

    def decide(self, symbol: str, mid_prices: List[float], bid: float, ask: float, portfolio: Portfolio) -> tuple[str, int]:
        min_required = max(self.params.bb_period, self.params.adx_period) + 2
        if bid <= 0 or ask <= 0 or len(mid_prices) < min_required:
            return "HOLD", 0

        upper_band, middle_band, lower_band = self._bollinger_bands(mid_prices, self.params.bb_period, self.params.bb_stddev)
        adx_value = self._adx_proxy(mid_prices, self.params.adx_period)
        adx_previous = self._adx_proxy(mid_prices[:-1], self.params.adx_period)
        adx_slope = adx_value - adx_previous
        cash = self._get_cash(portfolio)
        shares_owned = self._get_position(portfolio, symbol)
        avg_entry = self._get_avg_entry(portfolio, symbol)
        current_price = mid_prices[-1]

        if shares_owned > 0:
            loss_trigger = avg_entry is not None and current_price <= avg_entry * (1 - self.params.stop_loss_pct)
            upper_band_take_profit = current_price >= upper_band and avg_entry is not None and current_price >= avg_entry * (1 + self.params.take_profit_pct)
            adx_trend_reversal = adx_slope < 0 and adx_value < self.params.adx_threshold
            if loss_trigger or (upper_band_take_profit and adx_trend_reversal) or (upper_band_take_profit and adx_value < self.params.adx_threshold * 0.85):
                return "SELL", shares_owned
        else:
            buy_signal = current_price <= lower_band and adx_value >= self.params.adx_threshold
            trend_confirmation = adx_slope >= 0 or current_price <= middle_band
            if buy_signal and trend_confirmation:
                strength = min(1.5, max(0.25, adx_value / max(self.params.adx_threshold, 1e-6)))
                max_trade_value = cash * self.params.max_cash_fraction
                qty = math.floor((max_trade_value * strength) / ask)
                if qty > 0:
                    return "BUY", qty

        return "HOLD", 0


class TrainablePenguin2_Manual(TrainablePenguin2):
    def __init__(self, name: str = "TrainablePenguin2_Manual", bb_period: int = 22, bb_stddev: float = 2.0, adx_period: int = 14, adx_threshold: float = 25.0, max_cash_fraction_per_trade: float = 0.05, stop_loss_pct: float = 0.04, take_profit_pct: float = 0.08, cooldown_bars: int = 10):
        super().__init__(name=name, bb_period=bb_period, bb_stddev=bb_stddev, adx_period=adx_period, adx_threshold=adx_threshold, max_cash_fraction_per_trade=max_cash_fraction_per_trade, stop_loss_pct=stop_loss_pct, take_profit_pct=take_profit_pct, cooldown_bars=cooldown_bars)