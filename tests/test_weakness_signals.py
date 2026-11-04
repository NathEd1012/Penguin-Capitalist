from dataclasses import asdict, fields
from datetime import datetime, timezone
import importlib
import random

import pytest

from backtest.portfolio import Portfolio
from scripts.parameter_search import _sample_parameters_from_space


STRATEGIES = ("EmperorPenguin", "GentooPenguin", "KingPenguin", "RockhopperPenguin")


@pytest.mark.parametrize("strategy_name,indicator,threshold_name,thresholds,scores", [
    ("GentooPenguin", "ker", "ker_threshold", (20.0, 30.0), (25.0, 35.0, 45.0)),
    ("EmperorPenguin", "ker", "ker_threshold", (20.0, 30.0), (25.0, 35.0, 45.0)),
    ("EmperorPenguin", "trend", "trend_reversal_threshold", (0.3, 0.45), (0.4, 0.5, 0.6)),
    ("KingPenguin", "trend", "trend_reversal_threshold", (0.3, 0.45), (0.4, 0.5, 0.6)),
    ("RockhopperPenguin", "trend", "trend_reversal_threshold", (0.3, 0.45), (0.4, 0.5, 0.6)),
])
@pytest.mark.parametrize("exit_kind", ["profit", "volume"])
@pytest.mark.parametrize("threshold_index,expected_action", [(0, "HOLD"), (1, "SELL")])
def test_profit_and_volume_exits_share_the_weakness_threshold(
    monkeypatch, strategy_name, indicator, threshold_name, thresholds, scores,
    exit_kind, threshold_index, expected_action,
):
    module = importlib.import_module(f"penguins.{strategy_name}")
    parameters = dict(
        rsi_period=10, buy_rsi=30.0, sell_rsi=70.0,
        bb_period=10, bb_stddev=2.0, upper_band_buffer=0.0,
        ker_period=10, ker_threshold=20.0, ker_entry_threshold=20.0,
        trend_reversal_threshold=0.3, trend_entry_threshold=0.5,
        max_cash_fraction=0.1, stop_loss_pct=0.05, take_profit_pct=0.1,
        cooldown_bars=0,
        relative_performance_period=10, relative_performance_threshold=-1.0,
        rvol_period=10, rvol_threshold=2.0,
        sr_period=10, sr_low_threshhold=0.01, sr_high_threshhold=0.01,
    )
    parameter_names = {field.name for field in fields(getattr(module, f"{strategy_name}Params"))}
    parameters = {name: value for name, value in parameters.items() if name in parameter_names}
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
