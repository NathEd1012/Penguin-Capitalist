from penguins.base_penguin import BasePenguin


class SP500x2(BasePenguin):
    """Buy and hold SPY at 2x portfolio leverage."""

    TRADED_SYMBOLS = {"SPY"}
    LOOKBACK_BARS = 10  # Doesn't need history
    MAX_LEVERAGE = 2.0

    def __init__(self):
        super().__init__("SP500x2Penguin")

    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        # Only trade SPY and express leverage via portfolio margin.
        if symbol != "SPY":
            return "HOLD", 0

        # Invalid prices
        if ask <= 0:
            return "HOLD", 0

        # If we don't hold SPY yet, invest up to 2x notional.
        if portfolio.get_position("SPY") == 0:
            target_notional = portfolio.initial_capital * self.MAX_LEVERAGE
            max_shares = int(max(target_notional - portfolio.transaction_cost, 0) / ask)
            if max_shares > 0:
                return "BUY", max_shares

        # Already invested - hold forever
        return "HOLD", 0
