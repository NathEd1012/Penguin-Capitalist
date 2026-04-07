# penguins/random_penguin.py
import random
from penguins.base_penguin import BasePenguin


class RandomPenguin(BasePenguin):
    LOOKBACK_BARS = 10  # Doesn't need history, but minimum allocated
    
    def __init__(self):
        super().__init__("RandomPenguin")

    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        """Make a random decision: BUY, SELL, or HOLD."""
        if bid <= 0 or ask <= 0:
            return "HOLD", 0

        choice = random.choice(["BUY", "SELL", "HOLD"])
        if choice == "BUY":
            if portfolio.cash >= ask:
                return "BUY", 1
            return "HOLD", 0
        if choice == "SELL":
            if portfolio.get_position(symbol) > 0 and bid > 0:
                return "SELL", 1
            return "HOLD", 0
        return "HOLD", 0
