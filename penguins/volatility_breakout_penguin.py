from penguins.base_penguin import BasePenguin
import numpy as np


class VolatilityBreakoutPenguin(BasePenguin):
    def __init__(self, period=20, std_mult=2):
        super().__init__("Volatility Breakout")
        self.period = period
        self.std_mult = std_mult

    def decide(self, symbol, prices, portfolio):
        if len(prices) < self.period:
            return "HOLD", 0

        recent_prices = prices[-self.period :]
        mean = np.mean(recent_prices)
        std = np.std(recent_prices)
        upper = mean + self.std_mult * std
        lower = mean - self.std_mult * std

        current_price = prices[-1]
        qty = portfolio.get_position(symbol)
        cash = portfolio.cash

        if current_price > upper and qty <= 0 and cash >= current_price:
            return "BUY", 1
        elif current_price < lower and qty > 0:
            return "SELL", qty

        return "HOLD", 0
