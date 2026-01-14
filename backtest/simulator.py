from collections import defaultdict
from backtest.portfolio import Portfolio


class Simulator:
    def __init__(self, agent, symbols):
        self.agent = agent
        self.symbols = symbols
        self.portfolio = Portfolio()
        self.price_history = defaultdict(list)

    def step(self, prices):
        for symbol, price in prices.items():
            self.price_history[symbol].append(price)
            decision = self.agent.decide(
                symbol,
                self.price_history[symbol],
                self.portfolio,
            )

            if decision == "BUY":
                self.portfolio.buy(symbol, price, qty=1)

            elif decision == "SELL":
                self.portfolio.sell(symbol, price, qty=1)
