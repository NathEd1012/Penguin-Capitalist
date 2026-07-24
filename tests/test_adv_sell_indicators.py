from datetime import datetime

from backtest.portfolio import Portfolio
from penguins.Adv_SELL_TP.Adv_SELL_TP1 import Adv_SELL_TP1


def test_adv_sell_tp1_uses_relative_strength_and_rvol_exit_signals():
    penguin = Adv_SELL_TP1(
        name="test",
        relative_strength_period=2,
        relative_strength_threshold=0.0,
        rvol_period=2,
        rvol_threshold=1.5,
    )
    portfolio = Portfolio(initial_capital=1000.0)
    portfolio.buy("AAPL", 1, 100.0, datetime.now())

    mid_prices = [100.0 + i * 0.5 for i in range(70)]
    mid_prices[-1] = 115.0
    spy_prices = [100.0 + i * 0.8 for i in range(70)]
    spy_prices[-1] = 120.0
    volumes = [100.0] * 69 + [1000.0]

    action, quantity = penguin.decide(
        "AAPL",
        mid_prices,
        115.0,
        115.0,
        portfolio,
        spy_prices,
        volumes,
    )

    assert action == "SELL"
    assert quantity == 1
