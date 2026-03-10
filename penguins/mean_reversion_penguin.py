# penguins/mean_reversion_penguin.py
from penguins.base_penguin import BasePenguin
from indicators.momentum import rsi


class MeanReversionPenguin(BasePenguin):
    LOOKBACK_BARS = 30  # Needs RSI period 14 + margin
    
    def __init__(self):
        super().__init__("MeanReversionPenguin")

    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        if bid <= 0 or ask <= 0:
            return "HOLD", 0

        r = rsi(mid_prices)
        if r < 30 and portfolio.cash >= ask:
            return "BUY", 1
        if r > 70 and portfolio.get_position(symbol) > 0 and bid > 0:
            return "SELL", 1
        return "HOLD", 0
