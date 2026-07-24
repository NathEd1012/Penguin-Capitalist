from backtest.portfolio import Portfolio
from penguins.base_penguin import BasePenguin
from penguins.decision_utils import call_penguin_decide


class LegacyPenguin(BasePenguin):
    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        return "BUY", 1


class ContextAwarePenguin(BasePenguin):
    def decide(self, symbol, mid_prices, bid, ask, portfolio, spy_prices=None, volumes=None):
        return "SELL", 2


def test_call_penguin_decide_keeps_legacy_penguins_compatible():
    portfolio = Portfolio(initial_capital=1000.0)
    legacy_penguin = LegacyPenguin(name="legacy")

    action, quantity = call_penguin_decide(
        legacy_penguin,
        "AAPL",
        [100.0, 101.0],
        100.0,
        101.0,
        portfolio,
        spy_prices=[100.0, 101.0],
        volumes=[10.0, 11.0],
    )

    assert action == "BUY"
    assert quantity == 1


def test_call_penguin_decide_passes_context_to_supported_penguins():
    portfolio = Portfolio(initial_capital=1000.0)
    context_penguin = ContextAwarePenguin(name="context")

    action, quantity = call_penguin_decide(
        context_penguin,
        "AAPL",
        [100.0, 101.0],
        100.0,
        101.0,
        portfolio,
        spy_prices=[100.0, 101.0],
        volumes=[10.0, 11.0],
    )

    assert action == "SELL"
    assert quantity == 2
