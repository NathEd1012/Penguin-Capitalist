from penguins.base_penguin import BasePenguin
from indicators.momentum import rsi


class RSIMeanReversionPenguin(BasePenguin):
    def __init__(self, rsi_period=14, oversold=30, overbought=70):
        super().__init__("RSI Mean Reversion")
        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought

    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        if len(mid_prices) < self.rsi_period + 1:
            return "HOLD", 0

        rsi_val = rsi(mid_prices, self.rsi_period)
        qty = portfolio.get_position(symbol)
        cash = portfolio.cash

        if rsi_val < self.oversold and qty <= 0 and cash >= mid_prices[-1]:
            return "BUY", 1
        elif rsi_val > self.overbought and qty > 0:
            return "SELL", qty

        return "HOLD", 0
