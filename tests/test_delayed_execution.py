from datetime import datetime, timezone

import run_simulation
import pytest
from penguins.base_penguin import BasePenguin


class BuyOnFirstBarPenguin(BasePenguin):
    LOOKBACK_BARS = 1

    def __init__(self):
        super().__init__(name="BuyOnFirstBarPenguin")

    def decide(self, symbol, mid_prices, bid, ask, portfolio, spy_prices=None, volumes=None):
        return "BUY", 1


class FakeSpreadModel:
    def get_bid_ask(self, mid_price, high, low, timestamp, volume, symbol):
        return mid_price - 1.0, mid_price + 1.0, 0.0


@pytest.mark.parametrize(
    ("t_plus_x", "expected_price", "expected_timestamp"),
    [
        (0, 101.0, datetime(2025, 1, 1, tzinfo=timezone.utc)),
        (1, 201.0, datetime(2025, 1, 1, 0, 1, tzinfo=timezone.utc)),
    ],
)
def test_decision_bar_and_execution_bar_are_configurable(
    monkeypatch, t_plus_x, expected_price, expected_timestamp
):
    first_timestamp = datetime(2025, 1, 1, tzinfo=timezone.utc)
    second_timestamp = datetime(2025, 1, 1, 0, 1, tzinfo=timezone.utc)
    bars = {
        "AAPL": {
            first_timestamp: {"close": 100.0, "high": 101.0, "low": 99.0, "volume": 10, "data_quality": "OK"},
            second_timestamp: {"close": 200.0, "high": 201.0, "low": 199.0, "volume": 10, "data_quality": "OK"},
        }
    }

    monkeypatch.setattr(run_simulation.DataLoader, "load_bars", lambda self, *args, **kwargs: (bars, None))
    monkeypatch.setattr(run_simulation.DataLoader, "detect_stale_data", lambda self, data: (["AAPL"], []))
    monkeypatch.setattr(run_simulation, "SyntheticSpreadModel", FakeSpreadModel)
    monkeypatch.setattr(run_simulation, "get_price_adjustment_events", lambda symbol: [])

    results, _, _, _, _, _ = run_simulation.run_backtest(
        symbols=["AAPL"],
        start_datetime=first_timestamp,
        end_datetime=second_timestamp,
        binning="1m",
        initial_capital=1000.0,
        transaction_cost=0.0,
        penguin_classes=[BuyOnFirstBarPenguin],
        training_step_allowed=False,
        t_plus_x=t_plus_x,
    )

    portfolio = results["BuyOnFirstBarPenguin"][0]
    first_trade = portfolio.trades[0]
    assert first_trade.action == "BUY"
    assert first_trade.price == expected_price
    assert first_trade.timestamp == expected_timestamp