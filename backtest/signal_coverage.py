"""Causal indicator-window coverage on a US-equity trading-session clock."""
from bisect import bisect_left, bisect_right
from collections import defaultdict
from datetime import datetime, time, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

import exchange_calendars as xcals

from backtest.history import binning_to_minutes, penguin_history_requirements


NY = ZoneInfo('America/New_York')
MINIMUM_COVERAGE = 0.5


def indicator_windows(penguin):
    """Use actual indicator periods; a storage/warmup buffer is only a fallback.

    Strategies without indicators declare COVERAGE_WINDOWS = (). A strategy can
    also declare explicit windows, or add fixed periods to parameterized ones.
    """
    explicit = getattr(penguin, 'COVERAGE_WINDOWS', None)
    if explicit is not None:
        return tuple(sorted({int(n) for n in explicit if n > 0}))
    params = getattr(penguin, 'params', None)
    parameters = params if isinstance(params, dict) else vars(params) if params is not None else {}
    windows = {int(value) for name, value in parameters.items()
               if name.endswith('_period') and isinstance(value, (int, float)) and value > 0}
    windows.update(getattr(penguin, 'COVERAGE_FIXED_WINDOWS', ()))
    return tuple(sorted(windows or {penguin_history_requirements(penguin)[0]}))


class MarketBarClock:
    """Map real bar timestamps to consecutive expected trading-bar slots.

    Missing observations consume slots; scheduled closures do not. Intraday
    timestamps are bar starts, aligned to the provider's UTC bin boundaries.
    Daily bar timestamps are UTC session-date labels, not intraday instants.
    """
    def __init__(self, start, end, binning, session):
        if session not in {'regular', 'extended'}:
            raise ValueError('DATA_TRADING_SESSION must be regular or extended')
        self.minutes = binning_to_minutes(binning)
        calendar = xcals.get_calendar('XNYS', start=start, end=end)
        self.dates, self.opens, self.closes, self.offsets = [], [], [], []
        offset = 0
        interval = timedelta(minutes=self.minutes)
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        for label, row in calendar.schedule.iterrows():
            opened = row['open'].to_pydatetime()
            closed = row['close'].to_pydatetime()
            day = label.date()
            if self.minutes < 1440 and session == 'extended':
                # The cached equities include 04:00-20:00 ET observations.
                # On scheduled half-days the late session ends at 17:00 ET.
                early_close = closed.astimezone(NY).time() < time(16)
                opened = datetime.combine(day, time(4), NY).astimezone(timezone.utc)
                closed = datetime.combine(day, time(17 if early_close else 20), NY).astimezone(timezone.utc)
            # Hourly provider bars can overlap the 09:30 regular-session open.
            opened = epoch + ((opened - epoch) // interval) * interval
            self.dates.append(day)
            self.opens.append(opened)
            self.closes.append(closed)
            self.offsets.append(offset)
            offset += 1 if self.minutes >= 1440 else int(-(-(closed-opened) // interval))

    def position(self, timestamp):
        if self.minutes >= 1440:
            day = timestamp.astimezone(timezone.utc).date()
            i = bisect_left(self.dates, day)
            return i if i < len(self.dates) and self.dates[i] == day else None
        i = bisect_right(self.opens, timestamp) - 1
        if i < 0 or timestamp >= self.closes[i]:
            return None
        return self.offsets[i] + int((timestamp-self.opens[i]).total_seconds() // (self.minutes*60))


@lru_cache(maxsize=16)
def market_bar_clock(start, end, binning, session='extended'):
    """Reuse the small session schedule across optimization trials."""
    return MarketBarClock(start, end, binning, session)


class SignalCoverage:
    """Bounded per-symbol observations shared by all strategies in a worker."""
    def __init__(self, maximum_window):
        self.maximum_window = max(1, maximum_window)
        self.observations = defaultdict(list)

    def observe(self, symbol, slot):
        if slot is None:
            return
        observations = self.observations[symbol]
        if observations and observations[-1] == slot:
            return  # Multiple observations in one expected bar count only once.
        observations.append(slot)
        if len(observations) > self.maximum_window*2:
            del observations[:bisect_left(observations, slot-self.maximum_window+1)]

    def sufficient(self, symbol, windows, slot):
        if not windows:
            return True
        if slot is None:
            return False
        observations = self.observations.get(symbol, ())
        return all(
            len(observations)-bisect_left(observations, slot-window+1) >= window*MINIMUM_COVERAGE
            for window in windows
        )
