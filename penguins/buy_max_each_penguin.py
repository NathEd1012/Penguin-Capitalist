from penguins.base_penguin import BasePenguin


class BuyMaxEachPenguin(BasePenguin):
    """Buy as many shares as possible for each symbol once, then hold."""

    LOOKBACK_BARS = 1

    def __init__(self):
        super().__init__("Buy Max Each Penguin")
        self._filled_symbols = set()

    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        if ask <= 0:
            return "HOLD", 0

        # After we fill a symbol once, stop trading it.
        if symbol in self._filled_symbols or portfolio.get_position(symbol) > 0:
            return "HOLD", 0

        max_qty = int(portfolio.cash / ask)
        if max_qty > 0:
            self._filled_symbols.add(symbol)
            return "BUY", max_qty

        return "HOLD", 0
