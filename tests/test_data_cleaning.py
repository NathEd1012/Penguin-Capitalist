from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import io
import contextlib

import pytest

from backtest.data_cleaning import (
    CleaningPolicy, SymbolBars, annotate_quality, normalize_splits,
    prepare_market_data, slice_data,
)
from backtest.market_events import apply_events, event_schedule
from backtest.portfolio import Portfolio

UTC = timezone.utc
BASE = datetime(2026, 1, 5, 14, 30, tzinfo=UTC)
POLICY = CleaningPolicy()


def bar(price=100, volume=10000, **overrides):
    return dict(open=price, high=price, low=price, close=price, volume=volume, **overrides)


def prepared(symbol, points):
    return annotate_quality(symbol, normalize_splits(symbol, dict(points)), POLICY)


@pytest.mark.parametrize('changes', [
    {'close': float('nan')}, {'low': 110}, {'high': 90}, {'volume': -1},
    {'volume': float('inf')}, {'open': 0}, {'source_conflict': True},
])
def test_invalid_bars_cannot_reach_execution(changes):
    row = bar()
    row.update(changes)
    data = annotate_quality('AAPL', {BASE: row}, POLICY)
    assert data[BASE]['data_quality'] == 'INVALID'


def test_quality_is_causal_and_reentry_is_allowed():
    prefix = {BASE: bar(100, 100), BASE+timedelta(minutes=1): bar(107, 100)}
    extended = {**prefix, BASE+timedelta(minutes=2): bar(100, 100)}
    a = annotate_quality('AAPL', prefix, POLICY)
    b = annotate_quality('AAPL', extended, POLICY)
    assert all(a[t] == b[t] for t in prefix)
    assert b[BASE+timedelta(minutes=1)]['data_quality'] == 'OUTLIER'
    assert b[BASE+timedelta(minutes=2)]['data_quality'] == 'OK'


def test_mixed_split_adjustment_states_and_volume_units():
    dates = [datetime(2022, 1, 12, 20, tzinfo=UTC), datetime(2022, 1, 13, 14, tzinfo=UTC),
             datetime(2025, 11, 19, 20, tzinfo=UTC), datetime(2025, 11, 20, 14, tzinfo=UTC)]
    rows = {t: bar(p) for t, p in zip(dates, [72, 72, 112, 56])}
    result = normalize_splits('SSO', rows)
    assert [r['close'] for r in result.values()] == [36, 36, 56, 56]
    assert result[dates[0]]['volume'] == 20000
    assert rows[dates[0]]['close'] == 72  # raw input unchanged


def test_sparse_eligibility_uses_only_completed_sessions():
    spy, gree = {}, {}
    days = [BASE+timedelta(days=i) for i in range(30) if (BASE+timedelta(days=i)).weekday() < 5]
    for day in days:
        for minute in range(10):
            t = day+timedelta(minutes=minute)
            spy[t] = bar()
            if minute < 3:
                gree[t] = bar()
    data = {s: annotate_quality(s, rows, POLICY) for s, rows in [('SPY', spy), ('GREE', gree)]}
    prepare_market_data(data, days[-1]+timedelta(days=1), 1, POLICY)
    assert all(not r.get('trade_eligible', True) for r in data['GREE'].values())
    assert data['SPY'][days[6]].get('trade_eligible', True)
    assert not data['SPY'][days[0]].get('trade_eligible', True)
    prefix = {s: annotate_quality(s, {t: r for t, r in rows.items() if t < days[10]}, POLICY)
              for s, rows in [('SPY', spy), ('GREE', gree)]}
    prepare_market_data(prefix, days[10], 1, POLICY)
    for s in prefix:
        assert all(prefix[s][t].get('trade_eligible', True) == data[s][t].get('trade_eligible', True) for t in prefix[s])


def test_adjusted_distribution_entitlement_and_missing_price_protection():
    points = [(datetime.fromisoformat(t), bar(p)) for t, p in [
        ('2021-11-04T20:00:00+00:00', 25), ('2021-11-05T09:00:00+00:00', 17),
        ('2024-12-12T20:00:00+00:00', .37), ('2024-12-13T14:00:00+00:00', 7.4)]]
    at = points[1][0]
    for child_present in (True, False):
        data = {'BLUE': prepared('BLUE', points),
                'TSVT': prepared('TSVT', [(at, bar(24))]) if child_present else SymbolBars()}
        prepare_market_data(data, points[-1][0]+timedelta(minutes=1), 1, POLICY, coverage=False)
        events = [e for e in event_schedule(data)[at] if e[1] == 'distribution']
        p = Portfolio(1500)
        p.buy('BLUE', 3, 500, points[0][0])
        apply_events(events, {'p': p}, defaultdict(deque), defaultdict(deque), at)
        if child_present:
            assert p.positions['TSVT'] == 20
            assert p.get_total_value({'BLUE': 340, 'TSVT': 24}) == 1500
            assert p.cost_basis['BLUE'] == 340
            assert p.cost_basis['TSVT'] == pytest.approx(24)
            apply_events(events, {'p': p}, defaultdict(deque), defaultdict(deque), at)
            assert p.positions['TSVT'] == 20
        else:
            assert not p.positions
            assert p.cash == 1500
            assert p.trades[-1].reason == 'unpriced distribution protection'


def test_slice_and_pickle_preserve_metadata_without_mutating_source():
    import pickle
    rows = prepared('AAPL', [(BASE, bar()), (BASE+timedelta(days=4), bar(50))])
    data = {'AAPL': rows}
    prepare_market_data(data, BASE+timedelta(days=5), 1, POLICY, coverage=False)
    sliced = slice_data(data, BASE, BASE+timedelta(days=4, minutes=1))
    restored = pickle.loads(pickle.dumps(sliced))
    assert restored['AAPL'].events == rows.events
    assert len(restored['AAPL']) == 2
    assert sliced['AAPL'][BASE] is rows[BASE]


def test_cache_tracks_policy_registry_and_raw_files(tmp_path, monkeypatch):
    from backtest import finalized_data_cache as cache
    from scripts.data_fixes.list_of_corp_act import CORPORATE_ACTIONS
    monkeypatch.setenv('PENGUIN_DATA_CACHE_DIR', str(tmp_path))
    args = dict(symbols=['NOW'], start_date=BASE, end_date=BASE+timedelta(days=1), binning='1m',
                cache_start_date=None, training_start_date=None, training_end_date=None,
                validation_start_date=None, validation_end_date=None, warmup_bars=1000,
                prefilter_stale_symbols=True, enable_data_quality_checks=True, symbol_list_name='test')
    before = cache._configuration(**args)
    monkeypatch.setenv('DATA_CONSISTENCY_MAX_JUMP_PCT', '0.09')
    assert cache._configuration(**args) != before
    monkeypatch.delenv('DATA_CONSISTENCY_MAX_JUMP_PCT')
    (tmp_path/'NOW_1m.parquet').write_bytes(b'source revision')
    assert cache._configuration(**args) != before
    before = cache._configuration(**args)
    with patch.dict(CORPORATE_ACTIONS, NOW=[]):
        assert cache._configuration(**args) != before


def run_replay(points, *, symbols=('AAPL',), eligibility=None, delay=0, auxiliary=None, captures=None, lookback=1, timeline=None):
    import run_simulation as sim
    from penguins.base_penguin import BasePenguin
    class BuyOnce(BasePenguin):
        LOOKBACK_BARS = lookback
        def __init__(self):
            super().__init__('BuyOnce')
            self.bought = False
        def decide(self, symbol, mid_prices, bid, ask, portfolio, spy_prices=None, volumes=None):
            if captures is not None:
                captures.append((list(mid_prices), list(spy_prices)))
            if not self.bought:
                self.bought = True
                return 'BUY', 1
            return 'HOLD', 0
    class NoSpread:
        def get_bid_ask(self, mid_price, **kwargs):
            return mid_price, mid_price, 0
    data = {symbols[0]: prepared(symbols[0], points), **(auxiliary or {})}
    prepare_market_data(data, points[-1][0]+timedelta(minutes=1), 1, POLICY, coverage=False)
    if eligibility:
        for t, value in eligibility.items():
            data[symbols[0]][t]['trade_eligible'] = value
    snapshot = {t: dict(r) for t, r in data[symbols[0]].items()}
    with patch.object(sim, 'SyntheticSpreadModel', NoSpread), \
         patch.object(sim.DataLoader, 'load_bars', side_effect=AssertionError('unexpected reload')), \
         patch.dict('os.environ', {'PENGUIN_WORKERS': '1'}), \
         contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        results = sim.run_backtest(symbols=list(symbols), start_datetime=points[0][0],
                                  end_datetime=points[-1][0]+timedelta(minutes=1), binning='1m',
                                  initial_capital=100, transaction_cost=0, penguin_classes=[BuyOnce],
                                  training_step_allowed=False, loaded_data=data,
                                  loaded_valid_symbols=list(symbols), t_plus_x=delay)
    assert data[symbols[0]] == snapshot
    if timeline is not None:
        timeline.extend(results[2])
    return results[0]['BuyOnce'][0]


def test_real_loop_sells_before_returning_quote_after_72h():
    p = run_replay([(BASE, bar()), (BASE+timedelta(days=4), bar(50)),
                    (BASE+timedelta(days=4, minutes=1), bar(50))])
    assert p.cash == 100
    sell = next(t for t in p.trades if t.action == 'SELL')
    assert sell.price == 100
    assert sell.timestamp == BASE+timedelta(hours=72, microseconds=1)
    assert sell.reason == 'data gap >72h'


def test_real_loop_final_close_uses_latest_price():
    p = run_replay([(BASE, bar()), (BASE+timedelta(minutes=1), bar(102)), (BASE+timedelta(minutes=2), bar(104))])
    assert p.cash == 104
    assert p.trades[-1].price == 104


def test_deferred_order_cannot_buy_on_ineligible_bar():
    t = BASE+timedelta(minutes=1)
    p = run_replay([(BASE, bar()), (t, bar()), (BASE+timedelta(minutes=2), bar())],
                   eligibility={t: False}, delay=1)
    assert not p.trades


def test_exactly_72h_gap_does_not_force_sell():
    p = run_replay([(BASE, bar()), (BASE+timedelta(hours=72), bar(102)),
                    (BASE+timedelta(hours=72, minutes=1), bar(104))])
    assert not any(t.reason == 'data gap >72h' for t in p.trades)
    assert p.cash == 104


def test_invalid_quote_does_not_reset_gap_age():
    rows = prepared('AAPL', [(BASE, bar()), (BASE+timedelta(days=2), bar(float('nan'))),
                             (BASE+timedelta(days=4), bar())])
    prepare_market_data({'AAPL': rows}, BASE+timedelta(days=5), 1, POLICY, coverage=False)
    assert rows.events[0][:2] == (BASE+timedelta(hours=72, microseconds=1), 'stale')


def test_zero_volume_is_not_executable():
    rows = prepared('AAPL', [(BASE, bar(volume=0))])
    prepare_market_data({'AAPL': rows}, BASE+timedelta(minutes=1), 1, POLICY, coverage=False)
    assert rows[BASE]['data_quality'] == 'OK'  # usable mark, no trade print
    assert not rows[BASE]['trade_eligible']


def test_raw_merge_keeps_unresolved_duplicate_conflicts(tmp_path):
    import pandas as pd
    from market_data.cache import DataCache
    cache = DataCache(str(tmp_path))
    old = pd.DataFrame([{'timestamp': BASE, **bar(100)}, {'timestamp': BASE, **bar(120)}])
    new = pd.DataFrame([{'timestamp': BASE+timedelta(minutes=1), **bar(101)}])
    merged = cache.merge_cache_and_new_data('AAPL', '1m', old, new)
    assert len(merged) == 3
    revision = pd.DataFrame([{'timestamp': BASE, **bar(100)}])
    assert len(cache.merge_cache_and_new_data('AAPL', '1m', merged, revision)) == 2


def test_loader_quarantines_duplicate_source_rows_without_network(tmp_path):
    import pandas as pd
    from backtest.data_loader import DataLoader
    from market_data.cache import DataCache
    loader = DataLoader()
    loader.cache = DataCache(str(tmp_path))
    loader.cache.save_cache('AAPL', '1m', pd.DataFrame([
        {'timestamp': BASE, **bar(100)}, {'timestamp': BASE, **bar(120)},
        {'timestamp': BASE+timedelta(minutes=1), **bar(100)},
    ]))
    with patch.object(loader, 'client', None):
        data, _ = loader.load_bars(['AAPL'], BASE, BASE+timedelta(minutes=1),
                                  cache_only=True, include_dependencies=False,
                                  prefilter_stale_symbols=False)
    assert data['AAPL'][BASE]['data_quality'] == 'INVALID'
    assert data['AAPL'][BASE+timedelta(minutes=1)]['data_quality'] == 'OK'


def test_step1_roundtrip_preserves_prepared_events_and_refresh(tmp_path, monkeypatch):
    from backtest.finalized_data_cache import save, load
    monkeypatch.setenv('PENGUIN_DATA_CACHE_DIR', str(tmp_path/'raw'))
    bars = prepared('AAPL', [(BASE, bar()), (BASE+timedelta(days=4), bar(50))])
    data = {'AAPL': bars}
    prepare_market_data(data, BASE+timedelta(days=5), 1, POLICY, coverage=False)
    args = dict(cache_dir=tmp_path/'processed', symbols=['AAPL'], start_date=BASE,
                end_date=BASE+timedelta(days=5), binning='1m')
    save(**args, result={'data': data})
    result = load(**args)
    assert result['data']['AAPL'].events == bars.events
    assert load(**args, refresh_cache=True) is None


def test_training_context_reuses_prepared_slices():
    import scripts.train_trainable_penguins as training
    from penguins.base_penguin import BasePenguin
    class Tiny(BasePenguin):
        LOOKBACK_BARS = 1
    rows = prepared('AAPL', [(BASE-timedelta(days=1), bar()), (BASE, bar()),
                             (BASE+timedelta(minutes=1), bar())])
    data = {'AAPL': rows}
    prepare_market_data(data, BASE+timedelta(days=1), 1, POLICY, coverage=False)
    with patch.object(training.DataLoader, 'load_bars', side_effect=AssertionError('unexpected reload')):
        result = training.prepare_training_context(['AAPL'], BASE, BASE+timedelta(minutes=2),
                                                   '1m', [Tiny], loaded_data=data)
    assert result[0] == ['AAPL']
    assert isinstance(result[4]['AAPL'], SymbolBars)
    assert result[4]['AAPL'][BASE] is rows[BASE]


def test_benchmark_history_is_aligned_with_actual_stock_observations():
    captures = []
    spy = prepared('SPY', [(BASE+timedelta(minutes=i), bar(200+i)) for i in range(6)])
    p = run_replay([(BASE+timedelta(minutes=i), bar()) for i in (0, 2, 3, 4, 5)],
                   auxiliary={'SPY': spy}, captures=captures, lookback=3)
    assert captures[0][1] == [200, 202, 203]


def test_relative_strength_handles_missing_aligned_benchmark():
    from penguins.decision_utils import relative_strength
    assert relative_strength([100, 101, 102], [None, 200, 202], 2) == pytest.approx(.02)


def test_new_provider_requests_explicitly_use_raw_prices(tmp_path):
    import pandas as pd
    from types import SimpleNamespace
    from backtest.data_loader import DataLoader
    from market_data.cache import DataCache
    requests = []
    class Client:
        def get_stock_bars(self, request):
            requests.append(request)
            return SimpleNamespace(df=pd.DataFrame())
    loader = DataLoader()
    loader.cache = DataCache(str(tmp_path))
    loader.client = Client()
    loader.load_bars(['AAPL'], BASE, BASE+timedelta(minutes=1),
                     include_dependencies=False, prefilter_stale_symbols=False)
    assert requests
    assert requests[0].adjustment.value == 'raw'


def test_event_only_timestamps_have_matching_value_snapshots():
    timeline = []
    p = run_replay([(BASE, bar()), (BASE+timedelta(days=4), bar(50)),
                    (BASE+timedelta(days=4, minutes=1), bar(50))], timeline=timeline)
    assert BASE+timedelta(hours=72, microseconds=1) in timeline
    assert len(p.value_history) == len(timeline) + 1  # final liquidation snapshot
