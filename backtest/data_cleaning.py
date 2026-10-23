"""One-time, causal bar validation and eligibility preparation.

Raw Parquet files remain unchanged. SymbolBars carries small, immutable event
lists through slices; strategies only read accepted observations and eligibility.
"""
from bisect import bisect_left, bisect_right
from collections import Counter, deque
from dataclasses import asdict, dataclass
from datetime import timedelta
import math
import os
import pytz

from scripts.data_fixes.corporate_actions import get_price_adjustment_events, get_distribution_events

CLEANING_VERSION = 'prepared-bars-v1'
NY = pytz.timezone('America/New_York')
STALE_AFTER = timedelta(hours=72, microseconds=1)


@dataclass(frozen=True)
class CleaningPolicy:
    max_jump: float = 0.08
    thin_jump: float = 0.03
    thin_dollar_volume: float = 100_000
    coverage: float = 0.80
    coverage_sessions: int = 20
    minimum_sessions: int = 5
    quarantine: bool = False

    @classmethod
    def from_environment(cls):
        policy = cls(
            max_jump=float(os.getenv('DATA_CONSISTENCY_MAX_JUMP_PCT', '0.08')),
            thin_jump=float(os.getenv('DATA_THIN_MAX_JUMP_PCT', '0.03')),
            thin_dollar_volume=float(os.getenv('DATA_THIN_DOLLAR_VOLUME', '100000')),
            coverage=float(os.getenv('DATA_MIN_SESSION_COVERAGE', '0.80')),
            coverage_sessions=int(os.getenv('DATA_COVERAGE_SESSIONS', '20')),
            minimum_sessions=int(os.getenv('DATA_MIN_SESSIONS', '5')),
            quarantine=os.getenv('DATA_CONSISTENCY_QUARANTINE_AFTER_JUMP', '0').lower() in ('1', 'true', 'yes'),
        )
        if not (0 < policy.thin_jump <= policy.max_jump < 1 and 0 < policy.coverage <= 1
                and 1 <= policy.minimum_sessions <= policy.coverage_sessions
                and policy.thin_dollar_volume >= 0):
            raise ValueError('Invalid data-cleaning policy settings')
        return policy

    def configuration(self):
        return {'version': CLEANING_VERSION, **asdict(self)}


class SymbolBars(dict):
    """Read-only by convention after preparation; rows are shared across trials."""
    def __init__(self, rows=(), *, events=(), basis_events=(), summary=None):
        super().__init__(rows)
        self.timestamps = tuple(sorted(self))
        self.events = tuple(events)
        self.basis_events = tuple(basis_events)
        self.summary = summary or {}


def slice_data(data, start, end, symbols=None):
    """Slice prepared data without losing events or copying individual bar dicts."""
    result = {}
    for symbol in data if symbols is None else symbols:
        if symbol not in data:
            continue
        source = data[symbol]
        if isinstance(source, SymbolBars):
            lo = bisect_left(source.timestamps, start)
            hi = bisect_left(source.timestamps, end)
            rows = {t: source[t] for t in source.timestamps[lo:hi]}
        else:
            rows = {t: row for t, row in source.items() if start <= t < end}
        if isinstance(source, SymbolBars):
            rows = SymbolBars(rows, events=(e for e in source.events if start <= e[0] < end),
                              basis_events=source.basis_events, summary=source.summary)
        result[symbol] = rows
    return result


def invalid_reason(row):
    if row.get("source_conflict"):
        return "conflicting duplicate timestamp"
    try:
        o, h, l, c, v = (float(row[k]) for k in ('open', 'high', 'low', 'close', 'volume'))
        if not all(math.isfinite(x) and x > 0 for x in (o, h, l, c)):
            return 'nonfinite or nonpositive price'
        if not math.isfinite(v) or v < 0:
            return 'nonfinite or negative volume'
        if l > min(o, c) or h < max(o, c) or l > h:
            return 'inconsistent OHLC bounds'
    except (KeyError, TypeError, ValueError, OverflowError):
        return 'missing or nonnumeric OHLCV'
    return None


def normalize_splits(symbol, rows):
    """Detect adjustment state per boundary, then normalize each segment once.

    An already adjusted boundary is left alone. Prices and volumes are converted
    together. Unbracketed events are not guessed from a distant price level.
    """
    if not rows or os.getenv('IGNORE_CORPORATE_ACTIONS', '').lower() in ('1', 'true', 'yes'):
        return SymbolBars(rows)
    timestamps = sorted(rows)
    if any(t.tzinfo is None or t.utcoffset() is None for t in timestamps):
        raise ValueError(f'{symbol}: bar timestamps must be timezone aware')
    adjustments = get_price_adjustment_events(symbol)
    if not adjustments:
        return SymbolBars(rows)
    usable = [t for t in timestamps if not invalid_reason(rows[t])]
    changes, basis = [], []
    for boundary, factor, event in adjustments:
        i = bisect_left(usable, boundary)
        if not (0 < i < len(usable)):
            continue
        ratio = rows[usable[i]]['close'] / rows[usable[i-1]]['close']
        raw_distance = abs(math.log(ratio / factor))
        adjusted_distance = abs(math.log(ratio))
        # Both segments share final share units, regardless of which segment
        # required a correction in the raw source.
        basis.append((boundary, factor, event))
        if raw_distance < adjusted_distance:
            changes.append((boundary, factor))
    if not changes:
        return SymbolBars(rows, basis_events=basis)
    output = {}
    changes.sort()
    index = 0
    cumulative = math.prod(f for _, f in changes)
    for t in timestamps:
        while index < len(changes) and t >= changes[index][0]:
            cumulative /= changes[index][1]
            index += 1
        row = dict(rows[t])
        if not math.isclose(cumulative, 1.0):
            for key in ('open', 'high', 'low', 'close'):
                row[key] *= cumulative
            if 'volume' in row:
                row['volume'] /= cumulative
        output[t] = row
    return SymbolBars(output, basis_events=basis)


def annotate_quality(symbol, rows, policy):
    """Causal outlier checks: no next-bar lookup and no invented prices."""
    output, counts = {}, Counter()
    last = candidate = previous_time = None
    permanent_quarantine = False
    distribution_times = sorted({t for t, *_ in get_distribution_events(symbol)})
    for t in sorted(rows):
        original = rows[t]
        row = dict(original)
        reason = invalid_reason(row)
        quality = 'INVALID' if reason else 'OK'
        if not reason:
            close = row['close']
            threshold = policy.max_jump
            if close * row['volume'] < policy.thin_dollar_volume:
                threshold = min(threshold, policy.thin_jump)
            event_crossing = (previous_time is not None and
                              bisect_right(distribution_times, previous_time) < bisect_right(distribution_times, t))
            gap_reset = previous_time is not None and t - previous_time >= STALE_AFTER
            if permanent_quarantine:
                quality, reason = 'OUTLIER', 'quarantined after unexplained jump'
            elif last is not None and not gap_reset and not event_crossing and abs(close / last - 1) > threshold:
                # A stable new level can reenter after one rejected observation;
                # a return to the last accepted level can reenter immediately.
                confirmed = candidate is not None and abs(close / candidate - 1) <= threshold / 4
                if not confirmed:
                    quality, reason = 'OUTLIER', f'unconfirmed price jump above {threshold:.1%}'
                    permanent_quarantine = policy.quarantine
            candidate = close if quality == 'OUTLIER' else None
            if quality == 'OK':
                last = close
                previous_time = t
        row['data_quality'] = quality
        if reason:
            row['quality_reason'] = reason
        counts[quality] += 1
        output[t] = row
    return SymbolBars(output, basis_events=getattr(rows, 'basis_events', ()), summary=dict(counts))


def pricing_symbols(symbols):
    """Expand to the closure of distribution children and the coverage reference."""
    result = list(dict.fromkeys([*symbols, 'SPY']))
    for symbol in result:
        for _, event, _, child, _ in get_distribution_events(symbol):
            for dependency in (child, event.get('target_symbol')):
                if dependency and dependency not in result:
                    result.append(dependency)
    return result


def _session_counts(rows, minutes):
    counts = Counter()
    for t, row in rows.items():
        if row.get('data_quality', 'OK') != 'OK' or row.get('volume', 0) <= 0:
            continue
        local = t.astimezone(NY)
        if minutes >= 1440 or (local.weekday() < 5 and 570 <= local.hour * 60 + local.minute < 960):
            counts[local.date()] += 1
    return counts


def prepare_market_data(data, end, minutes, policy, coverage=True, reference=None):
    """Prepare session eligibility and sparse portfolio events exactly once."""
    if reference is None:
        reference = _session_counts(data.get('SPY', {}), minutes)
    if coverage and not reference:
        raise ValueError('SPY reference bars are required for session-coverage checks')
    sessions = sorted(reference)
    for symbol, rows in data.items():
        own = _session_counts(rows, minutes) if coverage else {}
        eligible = {}
        window = deque(maxlen=policy.coverage_sessions)
        # Begin at listing/first observation, never at the end of the run.
        first_date = min(rows).astimezone(NY).date() if rows else end.date()
        for day in sessions:
            if day < first_date:
                continue
            expected = sum(x[1] for x in window)
            eligible[day] = (len(window) >= policy.minimum_sessions and expected > 0 and
                             sum(x[0] for x in window) / expected >= policy.coverage)
            window.append((min(own.get(day, 0), reference[day]), reference[day]))
        blocked = 0
        accepted = []
        for t, row in rows.items():
            if row.get('volume', 0) <= 0 or (coverage and not eligible.get(t.astimezone(NY).date(), False)):
                row['trade_eligible'] = False
                blocked += 1
            if row.get('data_quality', 'OK') == 'OK' and row.get('volume', 0) > 0:
                accepted.append(t)
        accepted.sort()
        events = []
        for i, t in enumerate(accepted):
            deadline = t + STALE_AFTER
            next_t = accepted[i+1] if i+1 < len(accepted) else end
            if deadline < next_t and deadline < end:
                events.append((deadline, 'stale', symbol, rows[t]['close']))
        rows.events = tuple(events)
        rows.summary['ineligible_bars'] = blocked
        rows.summary['regular_bars'] = sum(own.values())
        rows.summary['reference_sessions'] = len(eligible)
        rows.summary['eligible_sessions'] = sum(eligible.values())

    def factor(symbol, at):
        return math.prod(f for t, f, _ in getattr(data.get(symbol), 'basis_events', ()) if at < t)

    # Group multi-child events once; ratios convert canonical parent units to
    # canonical child units, rather than mixing split-adjusted and legal units.
    for symbol, rows in data.items():
        grouped = {}
        for at, event, source, child, ratio in get_distribution_events(symbol):
            if symbol not in (source, event.get('target_symbol')):
                continue
            grouped.setdefault(at, []).append((child, ratio, event))
        if not grouped:
            continue
        valid = [t for t, r in rows.items() if r.get('data_quality', 'OK') == 'OK' and r.get('volume', 0) > 0]
        valid.sort()
        events = list(rows.events)
        for at, children in grouped.items():
            i = bisect_left(valid, at)
            if i == 0 or i == len(valid):
                continue
            execution_time = valid[i]
            child_info = []
            for child, ratio, event in children:
                child_rows = data.get(child, {})
                # This lookup runs only at corporate actions, not at each bar.
                child_times = getattr(child_rows, 'timestamps', ())
                j = bisect_right(child_times, execution_time) - 1
                while j >= 0 and child_rows[child_times[j]].get('data_quality', 'OK') != 'OK':
                    j -= 1
                mark_at = child_times[j] if j >= 0 else None
                mark = child_rows[mark_at]['close'] if mark_at is not None and execution_time-mark_at < STALE_AFTER else None
                adjusted_ratio = ratio * factor(symbol, at) / factor(child, at)
                child_info.append((child, adjusted_ratio, mark, event))
            if any(mark is None for _, _, mark, _ in child_info):
                rows.summary['unpriced_distributions'] = rows.summary.get('unpriced_distributions', 0) + 1
            events.append((execution_time, 'distribution', symbol, (at, tuple(child_info), rows[execution_time]['close'])))
        rows.events = tuple(sorted(events, key=lambda e: e[0]))
    return data
