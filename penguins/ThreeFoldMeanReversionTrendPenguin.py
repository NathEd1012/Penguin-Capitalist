from typing import List
import math

from backtest.portfolio import Portfolio
from penguins.base_penguin import BasePenguin


class ThreeFoldMeanReversionTrendPenguin(BasePenguin):
    LOOKBACK_BARS = 120

    def __init__(
        self,
        name: str = "ThreeFold_MeanReversion_TrendPenguin",
        rsi_period: int = 14,
        buy_rsi: float = 30.0,
        sell_rsi: float = 70.0,
        max_cash_fraction_per_trade: float = 0.05,
        stop_loss_pct: float = 0.04,
        take_profit_pct: float = 0.08,
    ):
        super().__init__(name)
        self.rsi_period = rsi_period
        self.buy_rsi = buy_rsi
        self.sell_rsi = sell_rsi
        self.max_cash_fraction_per_trade = max_cash_fraction_per_trade
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct

    def decide(
        self,
        symbol: str,
        mid_prices: List[float],
        bid: float,
        ask: float,
        portfolio: Portfolio,
    ) -> tuple[str, int]:

        if len(mid_prices) < max(60, self.rsi_period + 2):
            return "HOLD", 0

        rsi = self._rsi(mid_prices, self.rsi_period)
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
                and current_price <= avg_entry * (1 - self.stop_loss_pct)
            )

            profit_reversal_trigger = (
                avg_entry is not None
                and current_price >= avg_entry * (1 + self.take_profit_pct)
                and rsi > 60
                and trend_score < 0.3
            )

            overbought_breakdown_trigger = (
                rsi >= self.sell_rsi
                and trend_score < 0.15
            )

            if loss_trigger or profit_reversal_trigger or overbought_breakdown_trigger:
                return "SELL", shares_owned

        # -----------------
        # BUY CONDITION
        # -----------------
        if shares_owned == 0 and rsi <= self.buy_rsi:
            quality = self._buy_quality(rsi, trend_score)

            if quality <= 0:
                return "HOLD", 0

            qty = self._position_size(
                cash=cash,
                ask=ask,
                quality=quality,
            )

            if qty > 0:
                return "BUY", qty

        return "HOLD", 0

    # --------------------------------------------------
    # Indicators
    # --------------------------------------------------

    def _rsi(self, prices: List[float], period: int = 14) -> float:
        gain_sum = 0.0
        loss_sum = 0.0
        start = len(prices) - period
        for i in range(start, len(prices)):
            delta = prices[i] - prices[i - 1]
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
        """
        Returns 0..1.
        Higher means: better medium-term trend, not a falling knife.
        """
        sma_10 = sum(prices[-10:]) / 10
        sma_30 = sum(prices[-30:]) / 30
        sma_60 = sum(prices[-60:]) / 60

        price = prices[-1]

        score = 0.0

        if sma_10 > sma_30:
            score += 0.35
        if sma_30 > sma_60:
            score += 0.35
        if price > sma_30:
            score += 0.20
        if prices[-1] > prices[-5]:
            score += 0.10

        return min(score, 1.0)

    def _buy_quality(self, rsi: float, trend_score: float) -> float:
        """
        RSI gives mean-reversion opportunity.
        Trend score avoids buying weak crashes.
        """
        rsi_discount = max(0.0, (self.buy_rsi - rsi) / self.buy_rsi)

        # Require at least some trend support.
        if trend_score < 0.25:
            return 0.0

        return min(1.0, 0.6 * rsi_discount + 0.4 * trend_score)

    # --------------------------------------------------
    # Position sizing
    # --------------------------------------------------

    def _position_size(self, cash: float, ask: float, quality: float) -> int:
        if cash <= 0 or ask <= 0:
            return 0

        max_trade_value = cash * self.max_cash_fraction_per_trade
        adjusted_trade_value = max_trade_value * quality

        return max(0, math.floor(adjusted_trade_value / ask))

    # --------------------------------------------------
    # Portfolio compatibility helpers
    # --------------------------------------------------

    def _get_cash(self, portfolio: Portfolio) -> float:
        return float(portfolio.cash)

    def _get_position(self, portfolio: Portfolio, symbol: str) -> int:
        positions = portfolio.positions
        pos = positions.get(symbol, 0)
        if type(pos) is int:
            return pos

        if isinstance(pos, dict):
            return int(pos.get("quantity", 0))

        if hasattr(pos, "quantity"):
            return int(pos.quantity)

        return int(pos)

    def _get_avg_entry(self, portfolio: Portfolio, symbol: str) -> float | None:
        positions = portfolio.positions
        pos = positions.get(symbol)

        if pos is None or type(pos) is int:
            return None

        if isinstance(pos, dict):
            return pos.get("avg_entry_price") or pos.get("avg_price")

        return getattr(pos, "avg_entry_price", None) or getattr(pos, "avg_price", None)