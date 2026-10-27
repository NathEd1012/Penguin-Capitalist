from datetime import date, datetime
from types import SimpleNamespace

import pytest

from backtest.signal_coverage import SignalCoverage, indicator_windows, market_bar_clock


def at(value):
    return datetime.fromisoformat(value)


def test_exactly_half_passes_and_less_than_half_blocks():
    coverage = SignalCoverage(14)
    for slot in range(6):
        coverage.observe('SPY', slot)
    assert not coverage.sufficient('SPY', (14,), 13)
    coverage.observe('SPY', 13)
    assert coverage.sufficient('SPY', (14,), 13)
    assert not coverage.sufficient('SPY', (14,), 27)
    assert not coverage.sufficient('AAPL', (14,), 13)


def test_short_indicator_cannot_hide_behind_long_window():
    coverage = SignalCoverage(60)
    for slot in [*range(61, 91), 100]:
        coverage.observe('AAPL', slot)
    assert coverage.sufficient('AAPL', (60,), 100)
    assert not coverage.sufficient('AAPL', (14, 60), 100)


def test_duplicate_observations_cannot_fill_missing_bars():
    coverage = SignalCoverage(4)
    for _ in range(10):
        coverage.observe('AAPL', 3)
    coverage.observe('AAPL', None)
    assert not coverage.sufficient('AAPL', (4,), 3)


def test_tracking_is_bounded_and_recovers_after_a_gap():
    coverage = SignalCoverage(4)
    for slot in range(100):
        coverage.observe('AAPL', slot)
    assert len(coverage.observations['AAPL']) <= 8
    coverage.observe('AAPL', 200)
    assert not coverage.sufficient('AAPL', (4,), 200)
    coverage.observe('AAPL', 201)
    assert coverage.sufficient('AAPL', (4,), 201)


def test_actual_indicator_periods_override_storage_buffer():
    penguin = SimpleNamespace(LOOKBACK_BARS=1000, COVERAGE_FIXED_WINDOWS=(10, 30, 60),
                              params=SimpleNamespace(rsi_period=14, bb_period=20, cooldown_bars=500))
    assert indicator_windows(penguin) == (10, 14, 20, 30, 60)
    assert indicator_windows(SimpleNamespace(LOOKBACK_BARS=14)) == (14,)
    assert indicator_windows(SimpleNamespace(COVERAGE_WINDOWS=())) == ()


@pytest.mark.parametrize('session,last_bar,next_bar', [
    ('regular', '2026-01-16T20:59:00+00:00', '2026-01-20T14:30:00+00:00'),
    ('extended', '2026-01-17T00:59:00+00:00', '2026-01-20T09:00:00+00:00'),
])
def test_holiday_weekend_does_not_consume_expected_slots(session, last_bar, next_bar):
    clock = market_bar_clock(date(2026, 1, 1), date(2026, 1, 31), '1m', session)
    assert clock.position(at(next_bar)) == clock.position(at(last_bar))+1
    assert clock.position(at('2026-01-19T15:00:00+00:00')) is None


@pytest.mark.parametrize('session,last_bar,next_bar', [
    ('regular', '2025-07-03T16:59:00+00:00', '2025-07-07T13:30:00+00:00'),
    ('extended', '2025-07-03T20:59:00+00:00', '2025-07-07T08:00:00+00:00'),
])
def test_early_close_and_holiday_do_not_count_as_missing(session, last_bar, next_bar):
    clock = market_bar_clock(date(2025, 7, 1), date(2025, 7, 10), '1m', session)
    assert clock.position(at(next_bar)) == clock.position(at(last_bar))+1
    assert clock.position(at('2025-07-04T15:00:00+00:00')) is None


def test_clock_handles_daylight_saving_change_and_special_closure():
    clock = market_bar_clock(date(2026, 3, 1), date(2026, 3, 12), '1m', 'regular')
    assert clock.position(at('2026-03-09T13:30:00+00:00')) == clock.position(at('2026-03-06T20:59:00+00:00'))+1
    clock = market_bar_clock(date(2025, 1, 1), date(2025, 1, 15), '1m', 'regular')
    assert clock.position(at('2025-01-09T15:00:00+00:00')) is None


@pytest.mark.parametrize('binning,first,second', [
    ('5m', '2026-01-05T14:30:00+00:00', '2026-01-05T14:35:00+00:00'),
    ('15m', '2026-01-05T14:30:00+00:00', '2026-01-05T14:45:00+00:00'),
    ('1h', '2026-01-05T14:00:00+00:00', '2026-01-05T15:00:00+00:00'),
    ('1d', '2026-01-16T00:00:00+00:00', '2026-01-20T00:00:00+00:00'),
])
def test_clock_supports_all_coarser_binnings(binning, first, second):
    clock = market_bar_clock(date(2026, 1, 1), date(2026, 1, 31), binning, 'regular')
    assert clock.position(at(second)) == clock.position(at(first))+1


def test_bad_session_setting_fails_explicitly():
    with pytest.raises(ValueError, match='DATA_TRADING_SESSION'):
        market_bar_clock(date(2026, 1, 1), date(2026, 1, 31), '1m', 'invalid')
