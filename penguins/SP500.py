# penguins/msci_world_penguin.py
from penguins.base_penguin import BasePenguin


class SP500(BasePenguin):
    """Buy and hold SPY - invest all capital once and hold."""
    TRADED_SYMBOLS = {"SPY"}
    COVERAGE_WINDOWS = ()  # No indicator signals; execution still needs a fresh quote.
    LOOKBACK_BARS = 10  # Doesn't need history
    
    def __init__(self):
        super().__init__("SP500Penguin")
    
    def decide(self, symbol, mid_prices, low_price, high_price, portfolio):
        # Only trade SPY (S&P 500 benchmark)
        if symbol != "SPY":
            return "HOLD", 0

        # Invalid prices
        if high_price <= 0:
            return "HOLD", 0

        # If we don't hold SPY yet, invest all available capital
        if portfolio.get_position("SPY") == 0:
            max_shares = int(max(portfolio.cash - portfolio.transaction_cost, 0) / high_price)
            if max_shares > 0:
                return "BUY", max_shares

        # Already invested - hold forever
        return "HOLD", 0
