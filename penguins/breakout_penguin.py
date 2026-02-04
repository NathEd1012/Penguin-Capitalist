# penguins/breakout_penguin.py
from penguins.base_penguin import BasePenguin


class BreakoutPenguin(BasePenguin):
    def __init__(self, lookback=20):
        super().__init__("BreakoutPenguin")
        self.lookback = lookback

    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        if len(mid_prices) < self.lookback:
            return "HOLD", 0

        high = max(mid_prices[-self.lookback : -1])
        low = min(mid_prices[-self.lookback : -1])

        if mid_prices[-1] > high:
            return "BUY", 1
        if mid_prices[-1] < low:
            return "SELL", 1
        return "HOLD", 0
