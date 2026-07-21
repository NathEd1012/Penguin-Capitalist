from dataclasses import dataclass
import math
from typing import List

from backtest.portfolio import Portfolio
from penguins.base_penguin import BasePenguin
from penguins.trainable_signals import average_relative_strength_return


# Manual tuning block:
TRAINABLE_PENGUIN4_RSI_PERIOD = 13
TRAINABLE_PENGUIN4_BUY_RSI = 30.0
TRAINABLE_PENGUIN4_MAX_CASH_FRACTION = 0.05
TRAINABLE_PENGUIN4_RS_LOOKBACK = 5
TRAINABLE_PENGUIN4_RS_SELL_THRESHOLD = 0.0
TRAINABLE_PENGUIN4_MIN_HOLD_BARS = 3
TRAINABLE_PENGUIN4_STOP_LOSS_PCT = 0.04
TRAINABLE_PENGUIN4_TAKE_PROFIT_PCT = 0.08
TRAINABLE_PENGUIN4_COOLDOWN_BARS = 10


@dataclass
class TrainablePenguin4Params:
    rsi_period: int = TRAINABLE_PENGUIN4_RSI_PERIOD
    buy_rsi: float = TRAINABLE_PENGUIN4_BUY_RSI
    max_cash_fraction: float = TRAINABLE_PENGUIN4_MAX_CASH_FRACTION
    rs_lookback: int = TRAINABLE_PENGUIN4_RS_LOOKBACK
    rs_sell_threshold: float = TRAINABLE_PENGUIN4_RS_SELL_THRESHOLD
    min_hold_bars: int = TRAINABLE_PENGUIN4_MIN_HOLD_BARS
    stop_loss_pct: float = TRAINABLE_PENGUIN4_STOP_LOSS_PCT
    take_profit_pct: float = TRAINABLE_PENGUIN4_TAKE_PROFIT_PCT
    cooldown_bars: int = TRAINABLE_PENGUIN4_COOLDOWN_BARS


class TrainablePenguin4(BasePenguin):
    """RSI/trend entry and sizing with a Stock/SPY relative-strength exit."""

    LOOKBACK_BARS = 120
    BENCHMARK_SYMBOL = "SPY"
    REQUIRED_CONTEXT_SYMBOLS = {BENCHMARK_SYMBOL}

    def __init__(
        self,
        name: str = "TrainablePenguin4",
        rsi_period: int = TRAINABLE_PENGUIN4_RSI_PERIOD,
        buy_rsi: float = TRAINABLE_PENGUIN4_BUY_RSI,
        max_cash_fraction_per_trade: float = TRAINABLE_PENGUIN4_MAX_CASH_FRACTION,
        rs_lookback: int = TRAINABLE_PENGUIN4_RS_LOOKBACK,
        rs_sell_threshold: float = TRAINABLE_PENGUIN4_RS_SELL_THRESHOLD,
        min_hold_bars: int = TRAINABLE_PENGUIN4_MIN_HOLD_BARS,
        stop_loss_pct: float = TRAINABLE_PENGUIN4_STOP_LOSS_PCT,
        take_profit_pct: float = TRAINABLE_PENGUIN4_TAKE_PROFIT_PCT,
        cooldown_bars: int = TRAINABLE_PENGUIN4_COOLDOWN_BARS,
    ):
        super().__init__(name)
        self.params = TrainablePenguin4Params(
            rsi_period=rsi_period,
            buy_rsi=buy_rsi,
            max_cash_fraction=max_cash_fraction_per_trade,
            rs_lookback=rs_lookback,
            rs_sell_threshold=rs_sell_threshold,
            min_hold_bars=min_hold_bars,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            cooldown_bars=cooldown_bars,
        )
        self._entry_bar_index: dict[str, int] = {}

    def decide(
        self,
        symbol: str,
        mid_prices: List[float],
        bid: float,
        ask: float,
        portfolio: Portfolio,
    ) -> tuple[str, int]:
        if symbol == self.BENCHMARK_SYMBOL:
            return "HOLD", 0

        benchmark_prices = self._market_price_history.get(self.BENCHMARK_SYMBOL, ())
        relative_strength = average_relative_strength_return(
            mid_prices,
            benchmark_prices,
            self.params.rs_lookback,
        )
        shares_owned = int(portfolio.get_position(symbol))
        if shares_owned > 0:
            current_bar = len(mid_prices)
            entry_bar = self._entry_bar_index.get(symbol)
            if entry_bar is None:
                self._entry_bar_index[symbol] = current_bar
                entry_bar = current_bar

            bars_held = max(0, current_bar - entry_bar)
            if bars_held < self.params.min_hold_bars:
                return "HOLD", 0

            avg_entry = self._get_avg_entry(portfolio, symbol)
            current_price = bid if bid > 0 else mid_prices[-1]

            stop_loss_trigger = (
                avg_entry is not None
                and current_price <= avg_entry * (1.0 - self.params.stop_loss_pct)
            )
            take_profit_trigger = (
                avg_entry is not None
                and current_price >= avg_entry * (1.0 + self.params.take_profit_pct)
            )
            relative_strength_trigger = (
                relative_strength is not None
                and relative_strength <= self.params.rs_sell_threshold
            )

            if stop_loss_trigger or take_profit_trigger or relative_strength_trigger:
                self._entry_bar_index.pop(symbol, None)
                return "SELL", shares_owned
            return "HOLD", 0

        min_required = max(60, self.params.rsi_period + 2) + 2
        if (
            bid <= 0
            or ask <= 0
            or len(mid_prices) < min_required
            or relative_strength is None
        ):
            return "HOLD", 0

        rsi = self._rsi(mid_prices, self.params.rsi_period)
        trend_score = self._trend_quality(mid_prices)
        cash = float(portfolio.cash)

        buy_signal = rsi <= self.params.buy_rsi and trend_score > 0.5
        if buy_signal:
            strength = min(1.5, max(0.25, trend_score / 0.5))
            max_trade_value = cash * self.params.max_cash_fraction
            quantity = math.floor((max_trade_value * strength) / ask)
            if quantity > 0:
                self._entry_bar_index[symbol] = len(mid_prices)
                return "BUY", quantity

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
        relative_strength = avg_gain / avg_loss
        return 100 - (100 / (1 + relative_strength))

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

    def _get_avg_entry(self, portfolio: Portfolio, symbol: str) -> float | None:
        avg_entry = portfolio.cost_basis.get(symbol)
        if avg_entry is None or avg_entry <= 0:
            return None
        return float(avg_entry)


class TrainablePenguin4_Manual(TrainablePenguin4):
    def __init__(
        self,
        name: str = "TrainablePenguin4_Manual",
        rsi_period: int = TRAINABLE_PENGUIN4_RSI_PERIOD,
        buy_rsi: float = TRAINABLE_PENGUIN4_BUY_RSI,
        max_cash_fraction_per_trade: float = TRAINABLE_PENGUIN4_MAX_CASH_FRACTION,
        rs_lookback: int = TRAINABLE_PENGUIN4_RS_LOOKBACK,
        rs_sell_threshold: float = TRAINABLE_PENGUIN4_RS_SELL_THRESHOLD,
        min_hold_bars: int = TRAINABLE_PENGUIN4_MIN_HOLD_BARS,
        stop_loss_pct: float = TRAINABLE_PENGUIN4_STOP_LOSS_PCT,
        take_profit_pct: float = TRAINABLE_PENGUIN4_TAKE_PROFIT_PCT,
        cooldown_bars: int = TRAINABLE_PENGUIN4_COOLDOWN_BARS,
    ):
        super().__init__(
            name=name,
            rsi_period=rsi_period,
            buy_rsi=buy_rsi,
            max_cash_fraction_per_trade=max_cash_fraction_per_trade,
            rs_lookback=rs_lookback,
            rs_sell_threshold=rs_sell_threshold,
            min_hold_bars=min_hold_bars,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            cooldown_bars=cooldown_bars,
        )
