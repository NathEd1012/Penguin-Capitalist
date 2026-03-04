# penguins/msci_world_penguin.py
from penguins.base_penguin import BasePenguin


class MSCIWorldPenguin(BasePenguin):
    """Buy and hold AAPL - invest all capital once and hold."""
    
    def __init__(self):
        super().__init__("MSCIWorldPenguin")
        self.invested = False  # Track if we've already invested
    
    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        """
        Invest all capital into AAPL on first opportunity, then hold.
        
        Args:
            symbol: Stock symbol
            mid_prices: Historical mid-prices for analysis
            bid: Current bid price
            ask: Current ask price
            portfolio: Current portfolio
        
        Returns:
            (BUY | HOLD, quantity)
        """
        # Only trade AAPL (market benchmark)
        if symbol != "AAPL":
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
