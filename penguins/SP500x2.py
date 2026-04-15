from penguins.base_penguin import BasePenguin


class SP500x2(BasePenguin):
    """Buy and hold SSO (2x leveraged S&P 500 ETF)."""

    TRADED_SYMBOLS = {"SSO"}
    LOOKBACK_BARS = 10  # Doesn't need history

    def __init__(self):
        super().__init__("SP500x2Penguin")

    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        # Only trade SSO (2x leveraged S&P 500 ETF)
        if symbol != "SSO":
            return "HOLD", 0

        # Invalid prices
        if ask <= 0:
            return "HOLD", 0

        # If we don't hold SSO yet, invest all available capital
        if portfolio.get_position("SSO") == 0:
            max_shares = int(portfolio.cash / ask)
            if max_shares > 0:
                return "BUY", max_shares

        # Already invested - hold forever
        return "HOLD", 0
