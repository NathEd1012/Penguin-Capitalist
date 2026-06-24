from dataclasses import dataclass
import math
from typing import List

from backtest.portfolio import Portfolio

from .common import TrainablePenguinCommon


TRAINABLE_PENGUIN3_RSI_PERIOD = 14
TRAINABLE_PENGUIN3_BUY_RSI = 30.0
TRAINABLE_PENGUIN3_SELL_RSI = 70.0
TRAINABLE_PENGUIN3_MAX_CASH_FRACTION = 0.05
TRAINABLE_PENGUIN3_STOP_LOSS_PCT = 0.04
TRAINABLE_PENGUIN3_TAKE_PROFIT_PCT = 0.08
TRAINABLE_PENGUIN3_BB_PERIOD = 20
TRAINABLE_PENGUIN3_BB_STDDEV = 2.0
TRAINABLE_PENGUIN3_ADX_PERIOD = 14
TRAINABLE_PENGUIN3_ADX_THRESHOLD = 25.0
TRAINABLE_PENGUIN3_COOLDOWN_BARS = 10


@dataclass
class TrainablePenguin3Params:
    rsi_period: int = TRAINABLE_PENGUIN3_RSI_PERIOD
    buy_rsi: float = TRAINABLE_PENGUIN3_BUY_RSI
    sell_rsi: float = TRAINABLE_PENGUIN3_SELL_RSI
    max_cash_fraction: float = TRAINABLE_PENGUIN3_MAX_CASH_FRACTION
    stop_loss_pct: float = TRAINABLE_PENGUIN3_STOP_LOSS_PCT
    take_profit_pct: float = TRAINABLE_PENGUIN3_TAKE_PROFIT_PCT
    cooldown_bars: int = TRAINABLE_PENGUIN3_COOLDOWN_BARS
    bb_period: int = TRAINABLE_PENGUIN3_BB_PERIOD
    bb_stddev: float = TRAINABLE_PENGUIN3_BB_STDDEV
    adx_period: int = TRAINABLE_PENGUIN3_ADX_PERIOD
    adx_threshold: float = TRAINABLE_PENGUIN3_ADX_THRESHOLD


class TrainablePenguin3(TrainablePenguinCommon):
    LOOKBACK_BARS = 120

    def __init__(self, name: str = "TrainablePenguin3", rsi_period: int = TRAINABLE_PENGUIN3_RSI_PERIOD, buy_rsi: float = TRAINABLE_PENGUIN3_BUY_RSI, sell_rsi: float = TRAINABLE_PENGUIN3_SELL_RSI, max_cash_fraction_per_trade: float = TRAINABLE_PENGUIN3_MAX_CASH_FRACTION, stop_loss_pct: float = TRAINABLE_PENGUIN3_STOP_LOSS_PCT, take_profit_pct: float = TRAINABLE_PENGUIN3_TAKE_PROFIT_PCT, cooldown_bars: int = TRAINABLE_PENGUIN3_COOLDOWN_BARS, bb_period: int = TRAINABLE_PENGUIN3_BB_PERIOD, bb_stddev: float = TRAINABLE_PENGUIN3_BB_STDDEV, adx_period: int = TRAINABLE_PENGUIN3_ADX_PERIOD, adx_threshold: float = TRAINABLE_PENGUIN3_ADX_THRESHOLD):
        super().__init__(name)
        self.params = TrainablePenguin3Params(
            rsi_period=rsi_period,
            buy_rsi=buy_rsi,
            sell_rsi=sell_rsi,
            max_cash_fraction=max_cash_fraction_per_trade,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            cooldown_bars=cooldown_bars,
            bb_period=bb_period,
            bb_stddev=bb_stddev,
            adx_period=adx_period,
            adx_threshold=adx_threshold,
        )

    def decide(self, symbol: str, mid_prices: List[float], bid: float, ask: float, portfolio: Portfolio) -> tuple[str, int]:
        min_required = max(60, self.params.rsi_period + 2, self.params.bb_period, self.params.adx_period) + 2
        if bid <= 0 or ask <= 0 or len(mid_prices) < min_required:
            return "HOLD", 0

        rsi = self._rsi(mid_prices, self.params.rsi_period)
        trend_score = self._trend_quality(mid_prices)
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
            if rsi <= self.params.buy_rsi and trend_score > 0.5:
                max_shares_to_buy = math.floor((cash * self.params.max_cash_fraction) / current_price)
                return "BUY", max_shares_to_buy

        return "HOLD", 0


class TrainablePenguin3_Manual(TrainablePenguin3):
    def __init__(self, name: str = "TrainablePenguin3_Manual", rsi_period: int = 13, buy_rsi: float = 30.0, sell_rsi: float = 70.0, max_cash_fraction_per_trade: float = 0.05, stop_loss_pct: float = 0.04, take_profit_pct: float = 0.08, cooldown_bars: int = 10, bb_period: int = 22, bb_stddev: float = 2.0, adx_period: int = 14, adx_threshold: float = 25.0):
        super().__init__(name=name, rsi_period=rsi_period, buy_rsi=buy_rsi, sell_rsi=sell_rsi, max_cash_fraction_per_trade=max_cash_fraction_per_trade, stop_loss_pct=stop_loss_pct, take_profit_pct=take_profit_pct, cooldown_bars=cooldown_bars, bb_period=bb_period, bb_stddev=bb_stddev, adx_period=adx_period, adx_threshold=adx_threshold)