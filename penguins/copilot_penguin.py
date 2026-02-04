# penguins/copilot_penguin.py
from penguins.base_penguin import BasePenguin
from indicators.momentum import rsi


class CopilotPenguin(BasePenguin):
    def __init__(self):
        super().__init__("CopilotPenguin")

    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        """
        Mean reversion strategy using RSI.
        Buy when oversold (RSI < 30), sell when overbought (RSI > 70).
        """
        if len(mid_prices) < 14:
            return "HOLD", 0

        r = rsi(mid_prices)
        if r < 30:
            return "BUY", 1
        elif r > 70:
            # Sell all if we have position
            qty = (
                portfolio.positions[symbol].qty if symbol in portfolio.positions else 0
            )
            return "SELL", qty
        return "HOLD", 0
