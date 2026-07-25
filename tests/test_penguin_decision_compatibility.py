from backtest.portfolio import Portfolio
from penguins.base_penguin import BasePenguin
from penguins.decision_utils import call_penguin_decide
from penguins.OG_TP.OG_TP4 import OG_TP4
from scripts.train_trainable_penguins import _strategy_parameter_space


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


def test_training_parameter_space_for_og_tp4_matches_constructor():
    parameter_space = _strategy_parameter_space(OG_TP4)
    parameter_names = {name for name, _, _, _ in parameter_space}

    assert parameter_names == {
        "rsi_period",
        "buy_rsi",
        "sell_rsi",
        "max_cash_fraction_per_trade",
        "stop_loss_pct",
        "take_profit_pct",
        "cooldown_bars",
        "strength_cap",
    }

    params = {
        name: (int(low) if kind == "int" else float(low))
        for name, kind, low, _ in parameter_space
    }
    strategy = OG_TP4(**params)

    assert strategy.name == "TrainablePenguin4"
