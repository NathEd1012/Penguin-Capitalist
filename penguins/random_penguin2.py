# penguins/random_penguin2.py
import random
from penguins.base_penguin import BasePenguin


class RandomPenguin2(BasePenguin):
    def __init__(self):
        super().__init__("RandomPenguin2")

    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        """Make a random decision: BUY, SELL, or HOLD (same as RandomPenguin)."""
        choice = random.choice(["BUY", "SELL", "HOLD"])
        qty = 1 if choice in ["BUY", "SELL"] else 0
        return choice, qty
