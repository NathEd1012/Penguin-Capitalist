from datetime import datetime, timezone
import importlib
import random

import pytest

from backtest.portfolio import Portfolio
from config.parameter_search_con import strategy_parameter_space
from scripts.parameter_search import _sample_parameters_from_space


@pytest.fixture(params=["GentooPenguin", "RockhopperPenguin"])
def strategy_factory(request, monkeypatch):
    module = importlib.import_module(f"penguins.{request.param}")
    strategy_class = getattr(module, request.param)
    monkeypatch.setattr(module, "relative_performance", lambda *args: 0.0)
    monkeypatch.setattr(module, "relative_volume", lambda *args: 1.0)
    parameters = dict(
        max_cash_fraction=0.1, stop_loss_pct=0.05, take_profit_pct=0.1,
        relative_performance_period=10, relative_performance_threshold=-1.0,
        rvol_period=10, rvol_threshold=2.0,
    )
    if request.param == "GentooPenguin":
        monkeypatch.setattr(module, "rsi", lambda *args: 10.0)
        monkeypatch.setattr(module, "ker", lambda *args: 60.0)
        parameters.update(
            rsi_period=10, buy_rsi=30, sell_rsi=70,
            ker_period=10, ker_reversal_threshold=20,
            ker_entry_threshold=20,
        )
    else:
        monkeypatch.setattr(module, "bollinger_bands", lambda *args: (105.0, 103.0, 101.0))
        monkeypatch.setattr(module, "trend_quality", lambda *args: 0.8)
        parameters.update(
            bb_period=10, bb_stddev=2.0, upper_band_buffer=0.1,
            trend_reversal_threshold=0.3,
            trend_entry_threshold=0.5,
        )

    def create(cooldown=None):
        params = dict(parameters)
        if cooldown is not None:
            params["cooldown_bars"] = cooldown
        return strategy_class(**params)

    return create


def decide(strategy, portfolio, symbol="AAPL", price=100.0):
    # Keep history length fixed, as in the rolling history buffer used by backtests.
    return strategy.decide(symbol, [100.0] * 61 + [price], price, price, portfolio)


def test_cooldown_expires_at_configured_bar_with_fixed_history_length(strategy_factory):
    strategy = strategy_factory(cooldown=3)
    portfolio = Portfolio(10_000)
    assert [decide(strategy, portfolio)[0] for _ in range(4)] == ["BUY", "HOLD", "HOLD", "BUY"]


def test_cooldown_is_independent_for_each_symbol(strategy_factory):
    strategy = strategy_factory(cooldown=3)
    portfolio = Portfolio(10_000)
    assert decide(strategy, portfolio, "AAPL")[0] == "BUY"
    assert decide(strategy, portfolio, "MSFT")[0] == "BUY"
    assert decide(strategy, portfolio, "AAPL")[0] == "HOLD"


@pytest.mark.parametrize("cooldown", [None, 0])
def test_zero_or_omitted_cooldown_preserves_legacy_entry_behavior(strategy_factory, cooldown):
    strategy = strategy_factory(cooldown=cooldown)
    portfolio = Portfolio(10_000)
    assert strategy.params.cooldown_bars == 0
    assert [decide(strategy, portfolio)[0] for _ in range(2)] == ["BUY", "BUY"]


def test_stop_loss_bypasses_cooldown_and_sale_restarts_it(strategy_factory):
    strategy = strategy_factory(cooldown=3)
    portfolio = Portfolio(10_000)
    timestamp = datetime(2026, 1, 5, tzinfo=timezone.utc)
    action, quantity = decide(strategy, portfolio)
    assert action == "BUY"
    assert portfolio.buy("AAPL", quantity, 100.0, timestamp)
    assert decide(strategy, portfolio, price=90.0) == ("SELL", quantity)
    assert portfolio.sell("AAPL", quantity, 90.0, timestamp)
    assert [decide(strategy, portfolio)[0] for _ in range(3)] == ["HOLD", "HOLD", "BUY"]


def test_zero_quantity_does_not_start_cooldown(strategy_factory):
    strategy = strategy_factory(cooldown=3)
    portfolio = Portfolio(50)
    assert decide(strategy, portfolio) == ("HOLD", 0)
    portfolio.cash = 10_000
    assert decide(strategy, portfolio)[0] == "BUY"


def test_parameter_search_includes_and_instantiates_cooldown(strategy_factory):
    strategy_class = type(strategy_factory())
    space = strategy_parameter_space(strategy_class)
    assert next(parameter for parameter in space if parameter[0] == "cooldown_bars") == (
        "cooldown_bars", "int", 0, 100,
    )
    sampled = _sample_parameters_from_space(space, random.Random(42))
    assert strategy_class(**sampled).params.cooldown_bars == sampled["cooldown_bars"]
