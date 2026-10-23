from datetime import datetime, timezone

import pytest

from backtest.portfolio import Portfolio
from scripts.data_fixes.corporate_actions import (
    get_price_adjustment_events,
    price_effective_at,
)
from scripts.data_fixes.list_of_corp_act import CORPORATE_ACTIONS


def test_split_only_holding_value_is_preserved_and_adjustment_is_idempotent():
    portfolio = Portfolio(initial_capital=1000.0)
    opened_at = datetime(2025, 12, 17, tzinfo=timezone.utc)
    boundary = datetime(2025, 12, 18, 9, tzinfo=timezone.utc)
    portfolio.buy("NOW", 1, 100.0, opened_at)
    events = {"NOW": [(boundary, 0.2, CORPORATE_ACTIONS["NOW"][0])]}
    prices = {"NOW": [100.0, 105.0]}
    volumes = {"NOW": [1000.0, 900.0]}

    before = portfolio.get_total_value({"NOW": 100.0})
    portfolio.apply_price_adjustments(boundary, events, prices, volumes)
    portfolio.apply_price_adjustments(boundary, events, prices, volumes)

    assert portfolio.get_total_value({}) == before
    assert portfolio.get_position("NOW") == 5
    assert prices["NOW"] == [20.0, 21.0]
    assert volumes["NOW"] == [5000.0, 4500.0]


def test_verified_boundaries_are_timezone_aware_and_use_dst():
    expected = {
        "SSO": "2022-01-13T09:00:00+00:00",
        "BLUE": "2024-12-13T09:00:00+00:00",
        "LCID": "2025-09-02T08:00:00+00:00",
        "NOW": "2025-12-18T09:00:00+00:00",
    }
    for symbol, expected_timestamp in expected.items():
        event = next(
            event
            for event in CORPORATE_ACTIONS[symbol]
            if event.get("type") in {"split", "reverse_split"}
            and event["date"] == expected_timestamp[:10]
        )
        timestamp = price_effective_at(event)
        assert timestamp.isoformat() == expected_timestamp
        assert timestamp.tzinfo is not None


def test_all_registered_price_adjustments_have_aware_boundaries():
    for symbol in CORPORATE_ACTIONS:
        for timestamp, _factor, event in get_price_adjustment_events(symbol):
            assert timestamp.tzinfo is not None
            assert event["price_effective_at"]


def test_loader_classifies_old_scale_after_hours_before_boundary():
    pytest.importorskip("alpaca")
    from backtest.data_loader import DataLoader

    loader = object.__new__(DataLoader)
    before_boundary = datetime(2025, 12, 18, 8, 59, tzinfo=timezone.utc)
    at_boundary = datetime(2025, 12, 18, 9, tzinfo=timezone.utc)
    rows = {
        before_boundary: {"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0},
        at_boundary: {"open": 20.0, "high": 20.0, "low": 20.0, "close": 20.0},
    }

    adjusted = loader._apply_price_adjustments("NOW", rows)

    assert adjusted[before_boundary]["close"] == 20.0
    assert adjusted[at_boundary]["close"] == 20.0
