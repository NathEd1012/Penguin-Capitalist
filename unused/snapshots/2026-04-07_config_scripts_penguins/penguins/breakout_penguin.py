# penguins/breakout_penguin.py
from penguins.base_penguin import BasePenguin


class BreakoutPenguin(BasePenguin):
    def __init__(self, lookback=20):
        super().__init__("BreakoutPenguin")
        self.lookback = lookback

    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        if bid <= 0 or ask <= 0:
            return "HOLD", 0

        if len(mid_prices) < self.lookback:
            return "HOLD", 0

        high = max(mid_prices[-self.lookback : -1])
        low = min(mid_prices[-self.lookback : -1])

        if ask > high and portfolio.cash >= ask:
            return "BUY", 1
        if bid < low and portfolio.get_position(symbol) > 0:
            return "SELL", 1
        return "HOLD", 0
