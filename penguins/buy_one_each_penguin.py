from penguins.base_penguin import BasePenguin


class BuyOneEachPenguin(BasePenguin):
    """Buy exactly one share of each available symbol, then hold."""

    LOOKBACK_BARS = 1

    def __init__(self):
        super().__init__("Buy One Each Penguin")
        self._filled_symbols = set()

    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        if ask <= 0:
            return "HOLD", 0

        # Never buy the same symbol twice.
        if symbol in self._filled_symbols or portfolio.get_position(symbol) > 0:
            return "HOLD", 0

        if portfolio.cash >= ask:
            self._filled_symbols.add(symbol)
            return "BUY", 1

        return "HOLD", 0
