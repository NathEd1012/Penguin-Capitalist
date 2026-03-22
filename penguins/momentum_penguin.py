# penguins/momentum_penguin.py
from penguins.base_penguin import BasePenguin
from indicators.momentum import roc


class MomentumPenguin(BasePenguin):
    LOOKBACK_BARS = 30  # Needs ROC period 5 + margin
    
    def __init__(self):
        super().__init__("MomentumPenguin")

    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        if bid <= 0 or ask <= 0:
            return "HOLD", 0

        r = roc(mid_prices, 5)
        if r > 0.01 and portfolio.cash >= ask:
            return "BUY", 1
        if r < -0.01 and portfolio.get_position(symbol) > 0 and bid > 0:
            qty = portfolio.get_position(symbol)    
            return "SELL", 1
        return "HOLD", 0
