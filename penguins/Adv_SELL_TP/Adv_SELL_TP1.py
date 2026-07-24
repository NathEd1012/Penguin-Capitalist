from dataclasses import dataclass
import math
from typing import List

from backtest.portfolio import Portfolio
from penguins.base_penguin import BasePenguin
from indicators.market_context import relative_strength, relative_volume


# Manual tuning block:
# Adjust these values here first so the strategy is easy to finetune by hand.
RSI_PERIOD = 13 #14
BUY_RSI = 30.0
SELL_RSI = 70.0
ADX_PERIOD = 14
ADX_THRESHOLD = 25.0
MAX_CASH_FRACTION = 0.05
STOP_LOSS_PCT = 0.04
TAKE_PROFIT_PCT = 0.08
COOLDOWN_BARS = 10
RELATIVE_STRENGTH_PERIOD = 20
RELATIVE_STRENGTH_THRESHOLD = 0.0
RVOL_PERIOD = 20
RVOL_THRESHOLD = 2.0


# Trainable Penguin, with Buy condition based on RSI and ADX strength,
# and Sell condition based on RSI breakdown, trend reversal, and profit taking.


@dataclass
class Adv_SELL_TP1Params:
    rsi_period: int = RSI_PERIOD
    buy_rsi: float = BUY_RSI
    sell_rsi: float = SELL_RSI
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


class Adv_SELL_TP1(BasePenguin):
    LOOKBACK_BARS = 120
    TRAINABLE = True

    def __init__(
        self,
        name: str = "TrainablePenguin1",
        rsi_period: int = RSI_PERIOD,
        buy_rsi: float = BUY_RSI,
        sell_rsi: float = SELL_RSI,
        adx_period: int = ADX_PERIOD,
        adx_threshold: float = ADX_THRESHOLD,
        max_cash_fraction_per_trade: float = MAX_CASH_FRACTION,
        stop_loss_pct: float = STOP_LOSS_PCT,
        take_profit_pct: float = TAKE_PROFIT_PCT,
        cooldown_bars: int = COOLDOWN_BARS,
        relative_strength_period: int = RELATIVE_STRENGTH_PERIOD,
        relative_strength_threshold: float = RELATIVE_STRENGTH_THRESHOLD,
        rvol_period: int = RVOL_PERIOD,
        rvol_threshold: float = RVOL_THRESHOLD,
    ):
        super().__init__(name)
        self.params = Adv_SELL_TP1Params(
            rsi_period=rsi_period,
            buy_rsi=buy_rsi,
            sell_rsi=sell_rsi,
            adx_period=adx_period,
            adx_threshold=adx_threshold,
            max_cash_fraction=max_cash_fraction_per_trade,
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
            self.params.adx_period,
            self.params.relative_strength_period,
            self.params.rvol_period,
        ) + 2
        if bid <= 0 or ask <= 0 or len(mid_prices) < min_required:
            return "HOLD", 0

        rsi = self._rsi(mid_prices, self.params.rsi_period)
        adx_value = self._adx_proxy(mid_prices, self.params.adx_period)
        trend_score = self._trend_quality(mid_prices)
        relative_strength_value = relative_strength(
            mid_prices,
            spy_prices,
            self.params.relative_strength_period,
        )
        rvol = relative_volume(volumes, self.params.rvol_period)

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

            profit_reversal_trigger = (
                avg_entry is not None
                and current_price >= avg_entry * (1 + self.params.take_profit_pct)
                and rsi > 60
                and trend_score < 0.3
            )
            is_profitable = avg_entry is not None and current_price > avg_entry
            relative_strength_exit_trigger = (
                is_profitable
                and relative_strength_value < self.params.relative_strength_threshold
            )
            rvol_exit_trigger = (
                is_profitable
                and rvol > self.params.rvol_threshold
            )

            overbought_breakdown_trigger = (
                rsi >= self.params.sell_rsi
                and trend_score < 0.15
            )

            if (
                loss_trigger
                or profit_reversal_trigger
                or overbought_breakdown_trigger
                or relative_strength_exit_trigger
                or rvol_exit_trigger
            ):
                return "SELL", shares_owned
        else:
            # BUY part
            buy_signal = (
                rsi <= self.params.buy_rsi
                and adx_value >= self.params.adx_threshold
            )
            if buy_signal:
                # AMOUNT part
                strength = min(
                    1.5,
                    max(
                        0.25,
                        adx_value / max(self.params.adx_threshold, 1e-6),
                    ),
                )
                max_trade_value = cash * self.params.max_cash_fraction
                qty = math.floor((max_trade_value * strength) / ask)
                if qty > 0:
                    return "BUY", qty

        return "HOLD", 0

    def _rsi(self, prices: List[float], period: int = 14) -> float:
        gain_sum = 0.0
        loss_sum = 0.0
        start = len(prices) - period

        for index in range(start, len(prices)):
            delta = prices[index] - prices[index - 1]
            if delta > 0:
                gain_sum += delta
            elif delta < 0:
                loss_sum -= delta

        avg_gain = gain_sum / period
        avg_loss = loss_sum / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _trend_quality(self, prices: List[float]) -> float:
        sma_10 = sum(prices[-10:]) / 10
        sma_30 = sum(prices[-30:]) / 30
        sma_60 = sum(prices[-60:]) / 60

        score = 0.0

        if sma_10 > sma_30:
            score += 0.35
        if sma_30 > sma_60:
            score += 0.35
        if prices[-1] > sma_30:
            score += 0.20
        if prices[-1] > prices[-5]:
            score += 0.10

        return min(score, 1.0)

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


class Adv_SELL_TP1_Manual(Adv_SELL_TP1):
    TRAINABLE = False

    def __init__(
        self,
        name: str = "TrainablePenguin1_Manual",
        rsi_period: int = RSI_PERIOD,
        buy_rsi: float = BUY_RSI,
        sell_rsi: float = SELL_RSI,
        adx_period: int = ADX_PERIOD,
        adx_threshold: float = ADX_THRESHOLD,
        max_cash_fraction_per_trade: float = MAX_CASH_FRACTION,
        stop_loss_pct: float = STOP_LOSS_PCT,
        take_profit_pct: float = TAKE_PROFIT_PCT,
        cooldown_bars: int = COOLDOWN_BARS,
        relative_strength_period: int = RELATIVE_STRENGTH_PERIOD,
        relative_strength_threshold: float = RELATIVE_STRENGTH_THRESHOLD,
        rvol_period: int = RVOL_PERIOD,
        rvol_threshold: float = RVOL_THRESHOLD,
    ):
        super().__init__(
            name=name,
            rsi_period=rsi_period,
            buy_rsi=buy_rsi,
            sell_rsi=sell_rsi,
            adx_period=adx_period,
            adx_threshold=adx_threshold,
            max_cash_fraction_per_trade=max_cash_fraction_per_trade,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            cooldown_bars=cooldown_bars,
            relative_strength_period=relative_strength_period,
            relative_strength_threshold=relative_strength_threshold,
            rvol_period=rvol_period,
            rvol_threshold=rvol_threshold,
        )
