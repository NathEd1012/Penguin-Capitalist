from datetime import datetime, timezone
import importlib
import random

import pytest

from backtest.portfolio import Portfolio
from config.parameter_search_con import strategy_parameter_space
from scripts.parameter_search import _sample_parameters_from_space


emperor_module = importlib.import_module("penguins.EmperorPenguin")


@pytest.fixture
def strategy(monkeypatch):
    # Isolate the RelVol exit from entries and the other sell conditions.
    monkeypatch.setattr(emperor_module, "rsi", lambda *args: 50.0)
    monkeypatch.setattr(emperor_module, "bollinger_bands", lambda *args: (110.0, 100.0, 90.0))
    monkeypatch.setattr(emperor_module, "relative_performance", lambda *args: 0.0)
    return emperor_module.EmperorPenguin(
        rsi_period=10, buy_rsi=30.0, sell_rsi=70.0,
        bb_period=10, bb_stddev=2.0, upper_band_buffer=0.1,
        ker_period=10, ker_reversal_threshold=30.0, ker_entry_threshold=50.0,
        trend_reversal_threshold=0.2,
        trend_entry_threshold=0.5,
        max_cash_fraction=0.1, stop_loss_pct=0.05, take_profit_pct=0.1,
        cooldown_bars=3,
        relative_performance_period=10, relative_performance_threshold=-1.0,
        rvol_period=10, rvol_threshold=2.0,
    )


@pytest.mark.parametrize("er_scores,trend_scores,rvol,action", [
    pytest.param((10.0, 20.0, 30.0), (0.8, 0.8, 0.8), 3.0, "SELL", id="er-only"),
    pytest.param((60.0, 60.0, 60.0), (0.1, 0.2, 0.3), 3.0, "SELL", id="trend-only"),
    pytest.param((10.0, 20.0, 30.0), (0.1, 0.2, 0.3), 3.0, "SELL", id="both"),
    pytest.param((60.0, 60.0, 60.0), (0.8, 0.8, 0.8), 3.0, "HOLD", id="neither"),
    pytest.param((10.0, 20.0, 30.0), (0.1, 0.2, 0.3), 1.0, "HOLD", id="low-volume"),
    pytest.param((10.0, 20.0, 30.0), (0.1, 0.2, 0.3), 2.0, "HOLD", id="volume-at-threshold"),
    pytest.param((30.0, 40.0, 50.0), (0.8, 0.8, 0.8), 3.0, "HOLD", id="er-at-threshold"),
    pytest.param((10.0, 10.0, 20.0), (0.8, 0.8, 0.8), 3.0, "HOLD", id="er-flat"),
    pytest.param((10.0, 20.0, 5.0), (0.8, 0.8, 0.8), 3.0, "HOLD", id="er-below-one-prior-bar"),
    pytest.param((60.0, 60.0, 60.0), (0.2, 0.3, 0.4), 3.0, "HOLD", id="trend-at-threshold"),
    pytest.param((60.0, 60.0, 60.0), (0.1, 0.1, 0.3), 3.0, "HOLD", id="trend-flat"),
    pytest.param((60.0, 60.0, 60.0), (0.1, 0.2, 0.05), 3.0, "HOLD", id="trend-below-one-prior-bar"),
    pytest.param((10.0, 5.0, 5.0), (0.5, 0.6, 0.7), 3.0, "HOLD", id="no-mixing-indicator-conditions"),
])
def test_rvol_exit_accepts_either_complete_indicator_signal(
    strategy, monkeypatch, er_scores, trend_scores, rvol, action,
):
    # Scores are current, one bar ago, and two bars ago.
    monkeypatch.setattr(
        emperor_module, "ker",
        lambda prices, period: er_scores[62 - len(prices)],
    )
    monkeypatch.setattr(
        emperor_module, "trend_quality", lambda prices: trend_scores[62 - len(prices)],
    )
    monkeypatch.setattr(emperor_module, "relative_volume", lambda *args: rvol)
    portfolio = Portfolio(10_000)
    assert portfolio.buy("AAPL", 10, 100.0, datetime(2026, 1, 5, tzinfo=timezone.utc))
    strategy._last_trade_bar["AAPL"] = 0  # RelVol exits must bypass entry cooldown.

    assert strategy.decide("AAPL", [100.0] * 62, 100.0, 100.0, portfolio) == (
        action, 10 if action == "SELL" else 0,
    )
    assert strategy._last_trade_bar["AAPL"] == (1 if action == "SELL" else 0)


@pytest.mark.parametrize("range_set,reversal_bounds,entry_bounds", [
    ("narrow", (20.0, 40.0), (20.0, 40.0)),
    ("broad", (0.01, 55.0), (0.01, 75.0)),
])
def test_parameter_search_samples_emperor_thresholds_independently(
    monkeypatch, range_set, reversal_bounds, entry_bounds,
):
    import config.parameter_search_con as config

    monkeypatch.setattr(config, "PARAMETER_SEARCH_RANGE_SET", range_set)
    monkeypatch.setattr(config, "_ACTIVE_RANGES", dict(
        (parameter[0], parameter) for parameter in config.PARAMETER_RANGE_OVERVIEW[range_set]
    ))
    space = strategy_parameter_space(emperor_module.EmperorPenguin)
    assert ("ker_reversal_threshold", "float", *reversal_bounds) in space
    assert ("ker_entry_threshold", "float", *entry_bounds) in space
    assert ("trend_reversal_threshold", "float", 0.0, 1.0) in space
    parameters = _sample_parameters_from_space(space, random.Random(42))
    strategy = emperor_module.EmperorPenguin(**parameters)
    assert strategy.params.ker_reversal_threshold == parameters["ker_reversal_threshold"]
    assert strategy.params.ker_entry_threshold == parameters["ker_entry_threshold"]
    assert strategy.params.trend_reversal_threshold == parameters["trend_reversal_threshold"]
