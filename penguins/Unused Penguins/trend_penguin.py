# penguins/trend_penguin.py
from penguins.base_penguin import BasePenguin


class TrendPenguin(BasePenguin):
    LOOKBACK_BARS = 10  # Needs only 2 bars for comparison
    
    def __init__(self, lookback=3):
        super().__init__("TrendPenguin")
        self.lookback = lookback

    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        """
        Buy when stock rises from previous minute, sell when it falls, else hold.
        """
        if bid <= 0 or ask <= 0:
            return "HOLD", 0

        if len(mid_prices) < 2:
            return "HOLD", 0

        if mid_prices[-1] > mid_prices[-2]:
            if portfolio.cash >= ask:
                return "BUY", 1
            return "HOLD", 0
        elif mid_prices[-1] < mid_prices[-2]:
            if portfolio.get_position(symbol) > 0 and bid > 0:
                return "SELL", 1
            return "HOLD", 0
        else:
            return "HOLD", 0
