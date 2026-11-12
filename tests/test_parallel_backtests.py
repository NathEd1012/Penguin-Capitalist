import contextlib
import io
import json
import os
import signal
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

import run_simulation as simulation
from backtest.data_cleaning import CleaningPolicy, annotate_quality, normalize_splits, prepare_market_data


class HoldStrategy:
    LOOKBACK_BARS = 1

    def __init__(self, name):
        self.name = name

    def decide(self, *args, **kwargs):
        return "HOLD", 0


def test_validation_reuses_workers_for_more_candidates_than_slots(monkeypatch):
    start = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
    end = start + timedelta(minutes=3)
    rows = {
        start + timedelta(minutes=i): dict(open=100, high=100, low=100, close=100, volume=1000)
        for i in range(3)
    }
    data = {"SPY": annotate_quality("SPY", normalize_splits("SPY", rows), CleaningPolicy())}
    prepare_market_data(data, end, 1, CleaningPolicy(), coverage=False)
    original_metrics = simulation.Evaluator.calculate_metrics

    def metrics_with_pid(portfolio, initial_capital):
        metrics = original_metrics(portfolio, initial_capital)
        metrics["worker_pid"] = os.getpid()
        return metrics

    monkeypatch.setattr(simulation.Evaluator, "calculate_metrics", metrics_with_pid)
    monkeypatch.setenv("PENGUIN_PARALLEL", "1")
    monkeypatch.setenv("PENGUIN_WORKERS", "2")
    monkeypatch.setenv("PENGUIN_MEMORY_PER_WORKER_GB", "0.01")
    monkeypatch.setenv("PENGUIN_WORKER_TIMEOUT", "10")
    strategies = [HoldStrategy(f"Candidate_{i:03d}") for i in range(31)]
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        results, trades, timestamps, _, _, _ = simulation.run_backtest(
            symbols=["SPY"], start_datetime=start, end_datetime=end, binning="1m",
            initial_capital=100, transaction_cost=0, penguin_classes=strategies,
            training_step_allowed=False, backtest_label="Validation",
            loaded_data=data, loaded_valid_symbols=["SPY"],
        )

    assert len(results) == 31
    assert len({metrics["worker_pid"] for _, metrics in results.values()}) <= 2
    assert all(metrics["final_value"] == 100 for _, metrics in results.values())
    assert all(len(portfolio.value_history) == len(timestamps[name]) for name, (portfolio, _) in results.items())
    assert trades == {}
    assert simulation._PARALLEL_BACKTEST_CONTEXT is None


@pytest.mark.parametrize("exit_code", [0, 7])
def test_worker_exit_reports_failure_and_cleans_up_without_waiting_for_stall(exit_code):
    # A separate process bounds the regression even if shutdown itself hangs.
    code = r'''
import contextlib, io, json, multiprocessing, os, sys
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import run_simulation as simulation

class Hold:
    LOOKBACK_BARS = 1
    def __init__(self, name): self.name = name
    def decide(self, *args, **kwargs): return "HOLD", 0

original = simulation.run_backtest
def crash(**kwargs): os._exit(int(sys.argv[1]))
simulation.run_backtest = crash
start = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
data = {"SPY": {start + timedelta(minutes=i):
    dict(open=100, high=100, low=100, close=100, volume=1000) for i in range(3)}}
settings = {"PENGUIN_PARALLEL": "1", "PENGUIN_WORKERS": "2",
            "PENGUIN_MEMORY_PER_WORKER_GB": "0.01", "PENGUIN_WORKER_TIMEOUT": "10",
            "PENGUIN_POOL_SHUTDOWN_TIMEOUT": "1"}
try:
    with patch.dict(os.environ, settings), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        original(symbols=["SPY"], start_datetime=start, end_datetime=start+timedelta(minutes=3),
                 binning="1m", initial_capital=100, transaction_cost=0,
                 penguin_classes=[Hold("One"), Hold("Two")], training_step_allowed=False,
                 loaded_data=data, loaded_valid_symbols=["SPY"])
except RuntimeError as error:
    print(json.dumps({"error": str(error), "children": len(multiprocessing.active_children()),
                      "context_cleared": simulation._PARALLEL_BACKTEST_CONTEXT is None}))
else:
    raise AssertionError("A worker exit must not return a successful backtest")
'''
    process = subprocess.Popen(
        [sys.executable, "-c", code, str(exit_code)], cwd=Path(__file__).resolve().parents[1],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=30)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        pytest.fail("Worker failure or pool cleanup hung")
    assert process.returncode == 0, stderr
    result = json.loads(stdout)
    assert "exited unexpectedly" in result["error"]
    assert f"exitcode={exit_code}" in result["error"]
    assert result["children"] == 0
    assert result["context_cleared"]
