# penguins/breakout_penguin.py
from penguins.base_penguin import BasePenguin


class BreakoutPenguin(BasePenguin):
    def __init__(self, lookback=20):
        super().__init__("BreakoutPenguin")
        self.lookback = lookback

    def decide(self, symbol, prices, portfolio):
        if len(prices) < self.lookback:
            return "HOLD"

        high = max(prices[-self.lookback : -1])
        low = min(prices[-self.lookback : -1])

        if prices[-1] > high:
            return "BUY"
        if prices[-1] < low:
            return "SELL"
        return "HOLD"
