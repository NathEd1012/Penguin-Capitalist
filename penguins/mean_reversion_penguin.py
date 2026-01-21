# penguins/mean_reversion_penguin.py
from penguins.base_penguin import BasePenguin
from indicators.momentum import rsi


class MeanReversionPenguin(BasePenguin):
    def __init__(self):
        super().__init__("MeanReversionPenguin")

    def decide(self, symbol, prices, portfolio):
        r = rsi(prices)
        if r < 30:
            return "BUY", 1
        if r > 70:
            return "SELL", 1
        return "HOLD", 0
