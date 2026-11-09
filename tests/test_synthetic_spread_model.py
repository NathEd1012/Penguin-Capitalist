from datetime import datetime, timedelta, timezone
from math import isfinite

from bidask import edge
import pytest

from scripts.data_fixes.synthetic_spread_model import SyntheticSpreadModel


BASE = datetime(2026, 1, 5, 17, tzinfo=timezone.utc)
CANDLES = [
    (100.0, 100.5, 99.5, 100.2),
    (100.4, 100.9, 99.9, 100.1),
    (100.3, 100.8, 99.8, 100.5),
    (100.7, 101.2, 100.2, 100.4),
    (100.2, 100.9, 99.7, 100.6),
    (100.8, 101.3, 100.3, 100.5),
]


def quote(model, index, candle=None, symbol='AAPL', volume=None):
    opening, high, low, close = candle or CANDLES[index]
    return model.get_bid_ask(
        mid_price=close, high=high, low=low,
        timestamp=BASE + timedelta(minutes=index),
        volume=volume, symbol=symbol, open_price=opening,
    )


def test_quotes_match_edge_on_trailing_ohlc_and_convert_to_price_units():
    model = SyntheticSpreadModel(spread_window=3)
    for i, candle in enumerate(CANDLES):
        bid, ask, spread = quote(model, i)
        if i < 2:
            expected = max(candle[3] * 0.0002, (candle[1] - candle[2]) * 0.05)
        else:
            expected = candle[3] * edge(*zip(*CANDLES[i-2:i+1]), sign=False)
            assert isfinite(expected)
        assert spread == pytest.approx(expected)
        assert ask - bid == pytest.approx(spread)
        assert (ask + bid) / 2 == pytest.approx(candle[3])


def test_interleaved_symbols_have_independent_windows():
    interleaved = SyntheticSpreadModel(spread_window=3)
    isolated = SyntheticSpreadModel(spread_window=3)
    for i, candle in enumerate(CANDLES):
        assert quote(interleaved, i) == pytest.approx(quote(isolated, i))
        quote(interleaved, i, tuple(price * 4 for price in candle), symbol='MSFT')


def test_unavailable_edge_and_missing_open_use_legacy_fallback():
    model = SyntheticSpreadModel()
    for i in range(4):
        assert quote(model, i, (100, 100, 100, 100))[2] == pytest.approx(0.02)
    assert model.get_spread_only(100, 101, 99, BASE) == pytest.approx(0.1)


def test_zero_edge_is_valid_and_is_not_replaced_by_fallback(monkeypatch):
    monkeypatch.setattr('scripts.data_fixes.synthetic_spread_model.edge', lambda *a, **kw: 0.0)
    model = SyntheticSpreadModel()
    for i in range(3):
        result = quote(model, i)
    assert result == (CANDLES[2][3], CANDLES[2][3], 0.0)


def test_repeated_quote_and_spread_only_do_not_append_duplicate_observations():
    model = SyntheticSpreadModel()
    for i in range(3):
        result = quote(model, i, volume=1000)
    assert quote(model, 2, volume=1000) == pytest.approx(result)
    opening, high, low, close = CANDLES[2]
    assert model.get_spread_only(
        close, high, low, BASE + timedelta(minutes=2),
        volume=1000, symbol='AAPL', open_price=opening,
    ) == pytest.approx(result[2])
    assert len(model._ohlc_history['AAPL']) == 3
    assert len(model.volume_history['AAPL']) == 3


def test_time_and_volume_adjustments_apply_to_edge(monkeypatch):
    monkeypatch.setattr('scripts.data_fixes.synthetic_spread_model.edge', lambda *a, **kw: 0.001)
    model = SyntheticSpreadModel(market_open_time='17:00')
    quote(model, 0, volume=1000)
    quote(model, 1, volume=1000)
    # Average volume includes this candle, as in the existing model.
    spread = quote(model, 2, volume=500)[2]
    assert spread == pytest.approx(CANDLES[2][3] * 0.001 * 1.5 * (2500 / 3 / 500))


def test_reset_at_price_basis_change_discards_only_affected_history():
    model = SyntheticSpreadModel()
    for i in range(3):
        quote(model, i, volume=1000)
        quote(model, i, symbol='MSFT', volume=1000)
    model.reset_symbol('AAPL')
    assert 'AAPL' not in model.volume_history
    assert len(model._ohlc_history['MSFT']) == 3
    candle = tuple(price / 2 for price in CANDLES[3])
    spread = quote(model, 3, candle, volume=2000)[2]
    assert spread == pytest.approx(max(candle[3] * 0.0002, (candle[1] - candle[2]) * 0.05))


@pytest.mark.parametrize('window', [0, 2, 3.5, True])
def test_rejects_invalid_spread_window(window):
    with pytest.raises(ValueError, match='spread_window'):
        SyntheticSpreadModel(spread_window=window)


@pytest.mark.parametrize('candle', [
    (0, 101, 99, 100),
    (100, float('inf'), 99, 100),
    (100, 101, 99, float('nan')),
    (102, 101, 99, 100),
])
def test_rejects_invalid_prices_without_contaminating_history(candle):
    model = SyntheticSpreadModel()
    with pytest.raises(ValueError, match='OHLC|range'):
        quote(model, 0, candle)
    assert model._ohlc_history == {}


def test_rejects_out_of_order_or_changed_completed_candles():
    model = SyntheticSpreadModel()
    quote(model, 1)
    with pytest.raises(ValueError, match='timestamp order'):
        quote(model, 0)
    with pytest.raises(ValueError, match='cannot change'):
        quote(model, 1, CANDLES[2])


@pytest.mark.parametrize('spread_window', [3, 50])
def test_sparse_quotes_match_eager_quotes_with_all_intervening_ohlcv(monkeypatch, spread_window):
    calls = []

    def recording_edge(*args, **kwargs):
        calls.append(args)
        return edge(*args, **kwargs)

    monkeypatch.setattr('scripts.data_fixes.synthetic_spread_model.edge', recording_edge)
    eager = SyntheticSpreadModel(spread_window=spread_window, volume_window=3, market_open_time='17:00')
    sparse = SyntheticSpreadModel(spread_window=spread_window, volume_window=3, market_open_time='17:00')
    for i in range(62):
        opening, high, low, close = candle = CANDLES[i % len(CANDLES)]
        volume = 500 + 100 * (i % 7)
        expected = quote(eager, i, candle, volume=volume)
        calls.clear()
        sparse.observe_candle(
            mid_price=close, high=high, low=low,
            timestamp=BASE + timedelta(minutes=i),
            volume=volume, symbol='AAPL', open_price=opening,
        )
        assert calls == []
        if i in (2, 5, 52, 61):
            assert quote(sparse, i, candle, volume=volume) == pytest.approx(expected)
            assert len(calls) == 1
    assert sparse._ohlc_history == eager._ohlc_history
    assert sparse.volume_history == eager.volume_history
    assert sparse.volume_window_sums == eager.volume_window_sums


def test_simulation_observes_warmup_and_hold_candles_without_quotes(monkeypatch):
    import run_simulation as sim
    from penguins.base_penguin import BasePenguin

    observations = []

    class RecordingSpreadModel(SyntheticSpreadModel):
        def observe_candle(self, **kwargs):
            super().observe_candle(**kwargs)
            observations.append(kwargs)

        def get_bid_ask(self, **kwargs):
            pytest.fail('HOLD and warmup candles must not request execution quotes')

    class Hold(BasePenguin):
        LOOKBACK_BARS = 1

        def __init__(self):
            super().__init__('Hold')

        def decide(self, symbol, mid_prices, bid, ask, portfolio, **kwargs):
            return 'HOLD', 0

    data = {'AAPL': {
        BASE + timedelta(minutes=i): dict(zip(
            ('open', 'high', 'low', 'close', 'volume'), (*candle, 1000)
        ))
        for i, candle in enumerate(CANDLES)
    }}
    monkeypatch.setattr(sim, 'SyntheticSpreadModel', RecordingSpreadModel)
    monkeypatch.setenv('PENGUIN_WORKERS', '1')
    monkeypatch.setenv('DATA_TRADING_SESSION', 'regular')
    sim.run_backtest(
        symbols=['AAPL'], start_datetime=BASE + timedelta(minutes=3),
        end_datetime=BASE + timedelta(minutes=len(CANDLES)), binning='1m',
        initial_capital=100, transaction_cost=0, penguin_classes=[Hold],
        training_step_allowed=False, loaded_data=data,
        loaded_valid_symbols=['AAPL'], t_plus_x=0,
    )
    assert len(observations) == len(CANDLES)
    for i, kwargs in enumerate(observations):
        assert kwargs['open_price'] == CANDLES[i][0]


@pytest.mark.parametrize('delay', [0, 1, 2])
@pytest.mark.parametrize('strategy_count', [1, 2])
def test_high_sizing_and_cached_quotes_use_execution_bar_history(monkeypatch, delay, strategy_count):
    import run_simulation as sim
    from penguins.base_penguin import BasePenguin

    edge_calls = []
    decisions = []

    def recording_edge(*args, **kwargs):
        edge_calls.append(args)
        return 0.02

    class BuyOnce(BasePenguin):
        LOOKBACK_BARS = 1
        COVERAGE_WINDOWS = ()

        def __init__(self):
            super().__init__('BuyOnce')
            self.decided = False

        def decide(self, symbol, mid_prices, low_price, high_price, portfolio):
            if self.decided:
                return 'HOLD', 0
            self.decided = True
            decisions.append((low_price, high_price, len(edge_calls)))
            return 'BUY', int(portfolio.cash / high_price)

    class SecondBuyOnce(BuyOnce):
        pass

    candles = [(100+i, 200+i, 90+i, 100.2+i) for i in range(8)]
    data = {'AAPL': {
        BASE + timedelta(minutes=i): dict(zip(
            ('open', 'high', 'low', 'close', 'volume'), (*candle, 1000)
        ))
        for i, candle in enumerate(candles)
    }}
    monkeypatch.setattr('scripts.data_fixes.synthetic_spread_model.edge', recording_edge)
    monkeypatch.setenv('PENGUIN_WORKERS', '1')
    monkeypatch.setenv('DATA_TRADING_SESSION', 'regular')
    strategies = [BuyOnce, SecondBuyOnce][:strategy_count]
    results, *_ = sim.run_backtest(
        symbols=['AAPL'], start_datetime=BASE + timedelta(minutes=3),
        end_datetime=BASE + timedelta(minutes=len(candles)), binning='1m',
        initial_capital=1000, transaction_cost=0, penguin_classes=strategies,
        training_step_allowed=False, loaded_data=data,
        loaded_valid_symbols=['AAPL'], t_plus_x=delay,
    )
    assert decisions[0] == (candles[3][2], candles[3][1], 0)
    assert len(decisions) == strategy_count
    assert len(edge_calls) == 2  # One buy quote and one liquidation quote, shared by strategies.
    execution_index = 3 + delay
    assert edge_calls[0] == tuple(zip(*candles[:execution_index+1]))
    assert edge_calls[1] == tuple(zip(*candles))
    for strategy in strategies:
        portfolio = results[strategy.__name__][0]
        buy, sale = portfolio.trades
        assert buy.quantity == 4  # floor(1000 / decision candle high of 203)
        assert buy.timestamp == BASE + timedelta(minutes=execution_index)
        assert buy.price == pytest.approx(candles[execution_index][3] * 1.01)
        assert sale.timestamp == BASE + timedelta(minutes=7)
        assert sale.price == pytest.approx(candles[-1][3] * 0.99)


def test_sp500_preserves_high_sized_quantity_at_delayed_execution(monkeypatch):
    import run_simulation as sim
    from penguins import SP500

    class Benchmark(SP500):
        LOOKBACK_BARS = 1

    data = {'SPY': {
        BASE + timedelta(minutes=i): {
            'open': 100, 'high': 200, 'low': 90, 'close': 100, 'volume': 1000,
        }
        for i in range(3)
    }}
    monkeypatch.setattr('scripts.data_fixes.synthetic_spread_model.edge', lambda *args, **kwargs: 0.02)
    monkeypatch.setenv('PENGUIN_WORKERS', '1')
    monkeypatch.setenv('DATA_TRADING_SESSION', 'regular')
    results, *_ = sim.run_backtest(
        symbols=['SPY'], start_datetime=BASE,
        end_datetime=BASE + timedelta(minutes=3), binning='1m',
        initial_capital=1000, transaction_cost=0, penguin_classes=[Benchmark],
        training_step_allowed=False, loaded_data=data,
        loaded_valid_symbols=['SPY'], t_plus_x=1,
    )
    buy, sale = results['Benchmark'][0].trades
    assert buy.quantity == sale.quantity == 5
    assert buy.timestamp == BASE + timedelta(minutes=1)
    # With only two observations the execution quote uses the range fallback.
    assert buy.price == pytest.approx(102.75)
