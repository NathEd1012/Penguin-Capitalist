# penguins/momentum_penguin.py
from penguins.base_penguin import BasePenguin
from indicators.momentum import roc


class MomentumPenguin(BasePenguin):
    def __init__(self):
        super().__init__("MomentumPenguin")

    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        r = roc(mid_prices, 5)
        if r > 0.01:
            return "BUY", 1
        if r < -0.01:
            return "SELL", 1
        return "HOLD", 0
