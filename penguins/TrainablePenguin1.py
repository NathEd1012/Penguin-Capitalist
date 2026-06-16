from typing import List
import math

from backtest.portfolio import Portfolio
from penguins.base_penguin import BasePenguin


class TrainablePenguin1(BasePenguin):
    LOOKBACK_BARS = 120

@dataclass
class TrainablePenguin1Params:
    rsi_period: int
    buy_rsi: float
    sell_rsi: float
    max_cash_fraction: float
    stop_loss_pct: float
    take_profit_pct: float
    cooldown_bars: int

    # Trainable Penguin, with Buy condition based on RSI and the Amount by Trend compared between different Stocks, and Sell condition based on RS=Stock/SPY ratio and Trend Reversal

    def __init__(
        self,
        name: str = "TrainablePenguin1",
        rsi_period: int = 14,
        buy_rsi: float = 30.0,
        sell_rsi: float = 70.0,
        max_cash_fraction_per_trade: float = 0.05,
        stop_loss_pct: float = 0.04,
        take_profit_pct: float = 0.08,
        cooldown_bars: int = 10,
    ):
        super().__init__(name)
        self.params = TrainablePenguin1Params(
            rsi_period=rsi_period,
            buy_rsi=buy_rsi,
            sell_rsi=sell_rsi,
            max_cash_fraction=max_cash_fraction_per_trade,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            cooldown_bars=cooldown_bars,
        )   

    def decide(
        self,
        symbol: str,
        mid_prices: List[float],
        bid: float,
        ask: float,
        portfolio: Portfolio,
    ) -> tuple[str, int]:

        if len(mid_prices) < max(60, self.params.rsi_period + 2):
            return "HOLD", 0

        rsi = self._rsi(mid_prices, self.params.rsi_period)
        trend_score = self._trend_quality(mid_prices)

        cash = self._get_cash(portfolio)
        shares_owned = self._get_position(portfolio, symbol)
        avg_entry = self._get_avg_entry(portfolio, symbol)

        current_price = mid_prices[-1]
        # -----------------
        # SELL CONDITION
        # -----------------
        if shares_owned > 0:
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
            overbought_breakdown_trigger = (
                rsi >= self.params.sell_rsi
                and trend_score < 0.15
            )
            if loss_trigger or profit_reversal_trigger or overbought_breakdown_trigger:
                return "SELL", shares_owned
        # -----------------
        # BUY CONDITION
        else:
            if rsi <= self.params.buy_rsi and trend_score > 0.5:
                max_shares_to_buy = math.floor(
                    (cash * self.params.max_cash_fraction) / current_price
                )
                return "BUY", max_shares_to_buy
        return "HOLD", 0
    