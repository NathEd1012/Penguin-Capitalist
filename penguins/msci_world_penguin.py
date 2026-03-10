# penguins/msci_world_penguin.py
from penguins.base_penguin import BasePenguin


class SP500Penguin(BasePenguin):
    """Buy and hold SPY - invest all capital once and hold."""
    TRADED_SYMBOLS = {"SPY"}
    
    def __init__(self):
        super().__init__("SP500Penguin")
    
    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        # Only trade SPY (S&P 500 benchmark)
        if symbol != "SPY":
            return "HOLD", 0

        # Invalid prices
        if ask <= 0:
            return "HOLD", 0

        # If we don't hold SPY yet, invest all available capital
        if portfolio.get_position("SPY") == 0:
            max_shares = int(portfolio.cash / ask)
            if max_shares > 0:
                return "BUY", max_shares

        # Already invested - hold forever
        return "HOLD", 0



# Backwards compatibility alias
MSCIWorldPenguin = SP500Penguin
