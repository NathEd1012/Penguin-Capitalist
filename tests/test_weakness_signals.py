from dataclasses import asdict, fields
from datetime import datetime, timezone
import importlib
import random

import pytest

from backtest.portfolio import Portfolio
from scripts.parameter_search import _sample_parameters_from_space


STRATEGIES = ("EmperorPenguin", "GentooPenguin", "RockhopperPenguin")


def _strategy_parameters(module, strategy_name):
    parameters = dict(
        rsi_period=10, buy_rsi=30.0, sell_rsi=70.0,
        bb_period=10, bb_stddev=2.0, upper_band_buffer=0.0,
        ker_period=10, ker_reversal_threshold=20.0, ker_entry_threshold=20.0,
        trend_reversal_threshold=0.3, trend_entry_threshold=0.5,
        max_cash_fraction=0.1, stop_loss_pct=0.05, take_profit_pct=0.1,
        cooldown_bars=0,
        relative_performance_period=10, relative_performance_threshold=-1.0,
        rvol_period=10, rvol_threshold=2.0,
    )
    parameter_names = {field.name for field in fields(getattr(module, f"{strategy_name}Params"))}
    return {name: value for name, value in parameters.items() if name in parameter_names}


@pytest.mark.parametrize("strategy_name,indicator,threshold_name,thresholds,scores", [
    ("GentooPenguin", "ker", "ker_reversal_threshold", (20.0, 30.0), (25.0, 35.0, 45.0)),
    ("EmperorPenguin", "ker", "ker_reversal_threshold", (20.0, 30.0), (25.0, 35.0, 45.0)),
    ("EmperorPenguin", "trend", "trend_reversal_threshold", (0.3, 0.45), (0.4, 0.5, 0.6)),
    ("RockhopperPenguin", "trend", "trend_reversal_threshold", (0.3, 0.45), (0.4, 0.5, 0.6)),
])
@pytest.mark.parametrize("exit_kind", ["profit", "volume"])
@pytest.mark.parametrize("ker_entry_threshold", [10.0, 60.0])
@pytest.mark.parametrize("threshold_index,expected_action", [(0, "HOLD"), (1, "SELL")])
def test_indicator_and_volume_exits_share_the_weakness_threshold(
    monkeypatch, strategy_name, indicator, threshold_name, thresholds, scores,
    exit_kind, ker_entry_threshold, threshold_index, expected_action,
):
    module = importlib.import_module(f"penguins.{strategy_name}")
    parameters = _strategy_parameters(module, strategy_name)
    if "ker_entry_threshold" in parameters:
        parameters["ker_entry_threshold"] = ker_entry_threshold
    parameters[threshold_name] = thresholds[threshold_index]
    strategy = getattr(module, strategy_name)(**parameters)

    ker_scores = scores if indicator == "ker" else (60.0, 60.0, 60.0)
    trend_scores = scores if indicator == "trend" else (0.8, 0.8, 0.8)
    if hasattr(module, "ker"):
        monkeypatch.setattr(module, "ker", lambda prices, period: ker_scores[62 - len(prices)])
    if hasattr(module, "trend_quality"):
        monkeypatch.setattr(module, "trend_quality", lambda prices: trend_scores[62 - len(prices)])
    if hasattr(module, "rsi"):
        monkeypatch.setattr(module, "rsi", lambda *args: 80.0 if exit_kind == "profit" else 50.0)
    if hasattr(module, "bollinger_bands"):
        upper_band = 95.0 if exit_kind == "profit" else 110.0
        monkeypatch.setattr(module, "bollinger_bands", lambda *args: (upper_band, 92.0, 90.0))
    monkeypatch.setattr(module, "relative_performance", lambda *args: 0.0)
    monkeypatch.setattr(module, "relative_volume", lambda *args: 3.0 if exit_kind == "volume" else 1.0)

    portfolio = Portfolio(10_000)
    assert portfolio.buy("AAPL", 10, 100.0, datetime(2026, 1, 5, tzinfo=timezone.utc))
    assert strategy.decide("AAPL", [100.0] * 62, 100.0, 100.0, portfolio) == (
        expected_action, 10 if expected_action == "SELL" else 0,
    )


@pytest.mark.parametrize("strategy_name", ["EmperorPenguin", "GentooPenguin"])
@pytest.mark.parametrize("ker_reversal_threshold", [10.0, 50.0])
@pytest.mark.parametrize("ker_entry_threshold,expected_decision", [
    (20.0, ("BUY", 15)),
    (30.0, ("BUY", 10)),
    (40.0, ("HOLD", 0)),
])
def test_ker_entry_signal_and_sizing_are_independent_of_reversal_threshold(
    monkeypatch, strategy_name, ker_reversal_threshold, ker_entry_threshold,
    expected_decision,
):
    module = importlib.import_module(f"penguins.{strategy_name}")
    parameters = _strategy_parameters(module, strategy_name)
    parameters.update(
        ker_reversal_threshold=ker_reversal_threshold,
        ker_entry_threshold=ker_entry_threshold,
    )
    strategy = getattr(module, strategy_name)(**parameters)
    monkeypatch.setattr(module, "ker", lambda *args: 30.0)
    monkeypatch.setattr(module, "rsi", lambda *args: 10.0)
    monkeypatch.setattr(module, "relative_performance", lambda *args: 0.0)
    monkeypatch.setattr(module, "relative_volume", lambda *args: 1.0)
    if hasattr(module, "bollinger_bands"):
        monkeypatch.setattr(module, "bollinger_bands", lambda *args: (110.0, 100.0, 90.0))
    if hasattr(module, "trend_quality"):
        monkeypatch.setattr(module, "trend_quality", lambda *args: 0.1)

    assert strategy.decide("AAPL", [100.0] * 62, 100.0, 100.0, Portfolio(10_000)) == expected_decision


@pytest.mark.parametrize('strategy_name,expected_quantity', [
    ('EmperorPenguin', 8), ('GentooPenguin', 7), ('RockhopperPenguin', 8),
])
def test_buy_sizing_uses_candle_high_instead_of_close(monkeypatch, strategy_name, expected_quantity):
    module = importlib.import_module(f'penguins.{strategy_name}')
    strategy = getattr(module, strategy_name)(**_strategy_parameters(module, strategy_name))
    if hasattr(module, 'ker'):
        monkeypatch.setattr(module, 'ker', lambda *args: 30.0)
    if hasattr(module, 'rsi'):
        monkeypatch.setattr(module, 'rsi', lambda *args: 10.0)
    if hasattr(module, 'bollinger_bands'):
        monkeypatch.setattr(module, 'bollinger_bands', lambda *args: (110.0, 105.0, 101.0))
    if hasattr(module, 'trend_quality'):
        monkeypatch.setattr(module, 'trend_quality', lambda *args: 0.8)
    monkeypatch.setattr(module, 'relative_performance', lambda *args: 0.0)
    monkeypatch.setattr(module, 'relative_volume', lambda *args: 1.0)

    assert strategy.decide('AAPL', [100.0] * 62, 90.0, 200.0, Portfolio(10_000)) == (
        'BUY', expected_quantity,
    )


@pytest.mark.parametrize('strategy_name', STRATEGIES)
@pytest.mark.parametrize('quantity', [0.5, 10.5])
@pytest.mark.parametrize('price', [90.0, 120.0], ids=['stop-loss', 'take-profit'])
def test_price_exits_close_fractional_positions_without_weakness_confirmation(
    monkeypatch, strategy_name, quantity, price,
):
    module = importlib.import_module(f'penguins.{strategy_name}')
    strategy = getattr(module, strategy_name)(**_strategy_parameters(module, strategy_name))
    if hasattr(module, 'ker'):
        monkeypatch.setattr(module, 'ker', lambda *args: 80.0)
    if hasattr(module, 'trend_quality'):
        monkeypatch.setattr(module, 'trend_quality', lambda *args: 0.8)
    if hasattr(module, 'rsi'):
        monkeypatch.setattr(module, 'rsi', lambda *args: 50.0)
    if hasattr(module, 'bollinger_bands'):
        monkeypatch.setattr(module, 'bollinger_bands', lambda *args: (110.0, 100.0, 90.0))
    monkeypatch.setattr(module, 'relative_performance', lambda *args: 0.0)
    monkeypatch.setattr(module, 'relative_volume', lambda *args: 1.0)

    portfolio = Portfolio(10_000)
    at = datetime(2026, 1, 5, tzinfo=timezone.utc)
    assert portfolio.buy('AAPL', 10, 100.0, at)
    portfolio.positions['AAPL'] = quantity  # A distribution can leave fractional shares.
    action, sold_quantity = strategy.decide(
        'AAPL', [price] * 62, price, price, portfolio,
    )
    assert (action, sold_quantity) == ('SELL', quantity)
    assert portfolio.sell('AAPL', sold_quantity, price, at)
    assert portfolio.get_position('AAPL') == 0


@pytest.mark.parametrize("strategy_name", STRATEGIES)
@pytest.mark.parametrize("range_set", ["narrow", "broad"])
def test_search_parameters_match_the_consolidated_strategy_fields(monkeypatch, strategy_name, range_set):
    import config.parameter_search_con as config

    module = importlib.import_module(f"penguins.{strategy_name}")
    strategy_class = getattr(module, strategy_name)
    parameter_fields = fields(getattr(module, f"{strategy_name}Params"))
    monkeypatch.setattr(config, "PARAMETER_SEARCH_RANGE_SET", range_set)
    monkeypatch.setattr(config, "_ACTIVE_RANGES", {
        parameter[0]: parameter for parameter in config.PARAMETER_RANGE_OVERVIEW[range_set]
    })

    space = config.strategy_parameter_space(strategy_class)
    names = [name for name, *_ in space]
    assert len(names) == len(set(names))
    assert set(names) == {field.name for field in parameter_fields}
    assert all("negative" not in name for name in names)
    parameters = _sample_parameters_from_space(space, random.Random(42))
    assert asdict(strategy_class(**parameters).params) == parameters
