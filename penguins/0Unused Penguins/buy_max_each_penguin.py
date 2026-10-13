from penguins.base_penguin import BasePenguin


class BuyMaxEachPenguin(BasePenguin):
    """Buy the same maximum share count for every symbol once, then hold."""

    LOOKBACK_BARS = 1

    def __init__(self):
        super().__init__("Buy Max Each Penguin")

    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        return "HOLD", 0

    def decide_batch(self, symbols, quotes, portfolio):
        eligible_symbols = []
        ask_prices = []

        for symbol in symbols:
            if portfolio.get_position(symbol) > 0:
                continue

            quote = quotes.get(symbol)
            if not quote:
                continue

            _, ask = quote
            if ask > 0:
                eligible_symbols.append(symbol)
                ask_prices.append(ask)

        if not eligible_symbols:
            return []

        total_ask = sum(ask_prices)
        transaction_cost = portfolio.transaction_cost * len(eligible_symbols)
        if total_ask <= 0 or portfolio.cash <= transaction_cost:
            return []

        max_equal_qty = int((portfolio.cash - transaction_cost) // total_ask)
        if max_equal_qty <= 0:
            return []

        return [(symbol, "BUY", max_equal_qty) for symbol in eligible_symbols]
