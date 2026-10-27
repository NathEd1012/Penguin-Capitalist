from datetime import datetime, timedelta, timezone
import json
from unittest.mock import patch

import pytest

from backtest.evaluator import Evaluator
from backtest.portfolio import Portfolio
from scripts.plotting import _aligned_curve, plot_capital_curves


BASE = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)


def timestamped_portfolio():
    portfolio = Portfolio(10_000)
    portfolio.buy('AAPL', 50, 100, BASE)
    first = portfolio.get_total_value({'AAPL': 100}, timestamp=BASE)
    portfolio.add_value_snapshot(first, BASE)
    later = BASE + timedelta(minutes=1)
    second = portfolio.get_total_value(
        {'AAPL': 120},
        timestamp=later,
        price_metadata={'AAPL': {'quality_state': 'CONFIRMED_REGIME'}},
    )
    portfolio.add_value_snapshot(second, later)
    return portfolio


def test_plotting_rejects_curve_timestamp_mismatch():
    with pytest.raises(ValueError, match='2 curve values but 1 timestamps'):
        _aligned_curve({'Strategy': [BASE]}, [10_000, 10_100], 'Strategy')


def test_plotting_accepts_different_strategy_calendars(tmp_path):
    output = tmp_path / 'curves.png'
    plot_capital_curves(
        {'SP500': [10_000, 10_010], 'Strategy': [10_000, 10_020, 10_030]},
        output,
        bar_timestamps={
            'SP500': [BASE, BASE+timedelta(minutes=2)],
            'Strategy': [BASE, BASE+timedelta(minutes=1), BASE+timedelta(minutes=2)],
        },
    )
    assert output.exists()


def test_results_export_timestamps_trades_and_jump_attribution(tmp_path):
    portfolio = timestamped_portfolio()
    results = {'Strategy': (portfolio, Evaluator.calculate_metrics(portfolio, 10_000))}
    timestamps = {'Strategy': portfolio.value_timestamps}
    Evaluator.save_results(
        results,
        None,
        tmp_path,
        {BASE: ['  Strategy: BUY 50 AAPL @ $100.00']},
        timestamps,
        artifacts_dir=tmp_path,
    )

    json_dir = tmp_path / 'json'
    saved_timestamps = json.loads((json_dir / 'curve_timestamps.json').read_text())
    saved_attribution = json.loads((json_dir / 'equity_jump_attribution.json').read_text())
    assert saved_timestamps['Strategy'] == [timestamp.isoformat() for timestamp in timestamps['Strategy']]
    assert saved_attribution['Strategy'][0]['positions'][0]['symbol'] == 'AAPL'
    assert f'At {BASE.isoformat()}:' in (tmp_path / 'trades_log.txt').read_text()


def test_results_export_rejects_misaligned_timestamps(tmp_path):
    portfolio = timestamped_portfolio()
    results = {'Strategy': (portfolio, Evaluator.calculate_metrics(portfolio, 10_000))}
    with pytest.raises(ValueError, match='2 curve values but 1 timestamps'):
        Evaluator.save_results(
            results,
            None,
            tmp_path,
            {},
            {'Strategy': [BASE]},
            artifacts_dir=tmp_path,
        )


def test_results_export_stale_open_holdings_without_fabricating_sales(tmp_path):
    portfolio = timestamped_portfolio()
    at = BASE+timedelta(days=4)
    portfolio.add_value_snapshot(portfolio.get_total_value({}, timestamp=at), at)
    metrics = Evaluator.calculate_metrics(portfolio, 10_000)
    assert metrics['stale_position_count'] == 1
    results = {'Strategy': (portfolio, metrics)}
    Evaluator.save_results(results, None, tmp_path, {},
                           {'Strategy': portfolio.value_timestamps}, artifacts_dir=tmp_path)

    marks = json.loads((tmp_path/'json'/'valuation_marks.json').read_text())
    assert marks['Strategy']['timestamp'] == at.isoformat()
    mark = marks['Strategy']['positions']['AAPL']
    assert mark['mark_is_stale']
    assert mark['mark_timestamp'] == (BASE+timedelta(minutes=1)).isoformat()
    assert mark['mark_age_seconds'] == 4*24*60*60-60
    log = (tmp_path/'trades_log.txt').read_text()
    assert 'STALE; mark time' in log
    assert 'Open Positions (marked value included in Final Value)' in log
    assert 'SELL' not in log
    assert f'BUY 50 AAPL' in log  # Last-bar ordinary trades remain visible.


def test_open_position_summary_uses_carried_mark_without_double_counting_cost():
    portfolio = timestamped_portfolio()
    summary = portfolio.get_symbol_summary()['AAPL']
    assert summary['market_price'] == 120
    assert summary['market_value'] == 6000
    assert summary['realized_pnl'] == 0
    assert summary['unrealized_pnl'] == 1000
    assert summary['total_pnl'] == 1000

    portfolio.sell('AAPL', 10, 120, BASE+timedelta(minutes=2))
    summary = portfolio.get_symbol_summary()['AAPL']
    assert summary['realized_pnl'] == 200
    assert summary['unrealized_pnl'] == 800
    assert summary['total_pnl'] == 1000


def test_pdf_summary_uses_portfolios_own_marks_for_open_positions(tmp_path):
    import scripts.plotting as plotting
    portfolio = timestamped_portfolio()
    at = BASE+timedelta(days=4)
    portfolio.add_value_snapshot(portfolio.get_total_value({}, timestamp=at), at)
    with patch.object(plotting, '_save_strategy_summary_to_artifacts') as saved:
        plotting.create_final_report_pdf(
            {'Strategy': portfolio.value_history}, {'Strategy': portfolio},
            str(tmp_path/'report.pdf'), latest_prices={'AAPL': 999},
            bar_timestamps={'Strategy': portfolio.value_timestamps}, artifacts_dir=tmp_path,
        )
    assert saved.call_args.args[3:6] == (5000, 6000, 11000)
    assert saved.call_args.args[8] == 1000
    assert (tmp_path/'report.pdf').exists()
