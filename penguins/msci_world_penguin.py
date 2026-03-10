# penguins/msci_world_penguin.py
from penguins.base_penguin import BasePenguin


class SP500Penguin(BasePenguin):
    """Buy and hold SPY - invest all capital once and hold."""
    
    def __init__(self):
        super().__init__("SP500Penguin")
        self.invested = False  # Track if we've already invested
    
    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        """
        Invest all capital into SPY on first opportunity, then hold.
        
        Args:
            symbol: Stock symbol
            mid_prices: Historical mid-prices for analysis
            bid: Current bid price
            ask: Current ask price
            portfolio: Current portfolio
        
        Returns:
            (BUY | HOLD, quantity)
        """
        # Only trade SPY (S&P 500 benchmark)
        if symbol != "SPY":
            return "HOLD", 0
        
        # Invalid prices
        if ask <= 0:
            return "HOLD", 0
        
        # If we haven't invested yet, buy as many shares as possible
        if not self.invested:
            max_shares = int(portfolio.cash / ask)
            if max_shares > 0:
                self.invested = True
                return "BUY", max_shares
        
        # Otherwise, hold forever
        return "HOLD", 0



# Backwards compatibility alias
MSCIWorldPenguin = SP500Penguin
