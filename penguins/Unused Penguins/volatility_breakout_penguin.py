from penguins.base_penguin import BasePenguin
import numpy as np


class VolatilityBreakoutPenguin(BasePenguin):
    def __init__(self, period=20, std_mult=2):
        super().__init__("Volatility Breakout")
        self.period = period
        self.std_mult = std_mult

    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        if bid <= 0 or ask <= 0:
            return "HOLD", 0

        if len(mid_prices) < self.period:
            return "HOLD", 0

        recent_prices = mid_prices[-self.period :]
        mean = np.mean(recent_prices)
        std = np.std(recent_prices)
        upper = mean + self.std_mult * std
        lower = mean - self.std_mult * std

        qty = portfolio.get_position(symbol)
        cash = portfolio.cash

        if ask > upper and qty <= 0 and cash >= ask:
            return "BUY", 1
        elif bid < lower and qty > 0:
            return "SELL", qty

        return "HOLD", 0
