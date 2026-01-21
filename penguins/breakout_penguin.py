# penguins/breakout_penguin.py
from penguins.base_penguin import BasePenguin


class BreakoutPenguin(BasePenguin):
    def __init__(self, lookback=20):
        super().__init__("BreakoutPenguin")
        self.lookback = lookback

    def decide(self, symbol, prices, portfolio):
        if len(prices) < self.lookback:
            return "HOLD", 0

        high = max(prices[-self.lookback : -1])
        low = min(prices[-self.lookback : -1])

        if prices[-1] > high:
            return "BUY", 1
        if prices[-1] < low:
            return "SELL", 1
        return "HOLD", 0
