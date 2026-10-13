from penguins.base_penguin import BasePenguin


class BuyEqualPriceEachPenguin(BasePenguin):
    """Buy an equal dollar amount of each symbol once, then hold."""

    LOOKBACK_BARS = 1

    def __init__(self):
        super().__init__("Buy Equal Price Each Penguin")

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

        transaction_cost = portfolio.transaction_cost * len(eligible_symbols)
        remaining_cash = portfolio.cash - transaction_cost
        if remaining_cash <= 0:
            return []

        equal_budget = remaining_cash / len(eligible_symbols)
        orders = []
        for symbol, ask in zip(eligible_symbols, ask_prices):
            quantity = int(equal_budget // ask)
            if quantity > 0:
                orders.append((symbol, "BUY", quantity))

        return orders