from datetime import datetime

from backtest.portfolio import Portfolio
from penguins.Adv_SELL_TP.Adv_SELL_TP1 import Adv_SELL_TP1
from scripts.data_fixes.corporate_actions import (
    get_price_adjustment_events,
    has_corporate_action_near,
)


def test_portfolio_preserves_value_through_forward_split():
    portfolio = Portfolio(initial_capital=1000.0)
    event_time = datetime(2024, 10, 3)
    portfolio.buy("LRCX", 4, 80.0, datetime(2024, 10, 2))

    before_value = portfolio.get_total_value({"LRCX": 80.0})
    portfolio.apply_price_adjustments(
        event_time,
        {"LRCX": [(event_time, 0.1, {"type": "split", "ratio": "10:1"})]},
    )
    after_value = portfolio.get_total_value({"LRCX": 8.0})

    assert portfolio.get_position("LRCX") == 40
    assert after_value == before_value


def test_corporate_action_registry_preserves_overlapping_symbol_events():
    ge_events = get_price_adjustment_events("GE")
    assert len(ge_events) == 1
    assert ge_events[0][2]["ratio"] == "1:8"


def test_missing_split_events_are_returned_with_correct_factors():
    nvda_events = get_price_adjustment_events("NVDA")
    fcel_events = get_price_adjustment_events("FCEL")

    assert [(event[0].date().isoformat(), event[1]) for event in nvda_events] == [
        ("2021-07-20", 0.25),
        ("2024-06-10", 0.1),
    ]
    assert [(event[0].date().isoformat(), event[1]) for event in fcel_events] == [
        ("2024-11-11", 30.0),
    ]


def test_mtch_reorganization_is_detected_without_price_multiplier():
    event_time = datetime(2020, 7, 1)

    assert has_corporate_action_near("MTCH", event_time)
    assert get_price_adjustment_events("MTCH") == []


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
