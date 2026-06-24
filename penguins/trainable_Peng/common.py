from typing import List

from backtest.portfolio import Portfolio
from penguins.base_penguin import BasePenguin


class TrainablePenguinCommon(BasePenguin):
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