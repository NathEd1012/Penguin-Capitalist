# penguins/trend_penguin.py
from penguins.base_penguin import BasePenguin


class TrendPenguin(BasePenguin):
    def __init__(self, lookback=3):
        super().__init__("TrendPenguin")
        self.lookback = lookback

    def decide(self, symbol, prices, portfolio):
        """
        Buy when stock rises from previous minute, sell when it falls, else hold.
        """
        if len(prices) < 2:
            return "HOLD", 0

        if prices[-1] > prices[-2]:
            return "BUY", 1
        elif prices[-1] < prices[-2]:
            return "SELL", 1
        else:
            return "HOLD", 0
