# penguins/random_penguin.py
import random
from penguins.base_penguin import BasePenguin


class RandomPenguin(BasePenguin):
    def __init__(self):
        super().__init__("RandomPenguin")

    def decide(self, symbol, prices, portfolio):
        """Make a random decision: BUY, SELL, or HOLD."""
        choice = random.choice(["BUY", "SELL", "HOLD"])
        qty = 1 if choice in ["BUY", "SELL"] else 0
        return choice, qty
