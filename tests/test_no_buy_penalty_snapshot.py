"""Regression checks for the isolated no-buy-penalty experiment (unittest)."""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from partial_scripts.prepare_no_buy_penalty_snapshot import create_snapshot, digest

PROJECT = Path(__file__).resolve().parents[1]
LONG_SCRIPT = PROJECT.parent / "slurm_scripts/full_runs/run_long.sh"


def objective_at(path):
    spec = importlib.util.spec_from_file_location("isolated_training_objective", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NoBuyPenaltySnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="penguin_no_buy_test_")
        cls.snapshot = Path(cls.temporary.name) / "source"
        cls.manifest = create_snapshot(PROJECT, cls.snapshot, LONG_SCRIPT)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_live_source_and_default_penalty_are_unchanged(self):
        for relative, original_hash in self.manifest["source_sha256"].items():
            self.assertEqual(digest(PROJECT / relative), original_hash, relative)
        self.assertEqual(digest(LONG_SCRIPT), self.manifest["runner_source_sha256"])
        self.assertEqual(
            set(self.manifest["modified_files"]),
            {"config/training_step.py", "scripts/training_objective.py",
             "scripts/train_trainable_penguins.py", "run_simulation.py"},
        )
        live = objective_at(PROJECT / "scripts/training_objective.py")
        self.assertEqual(live.activity_penalty(0, 100_000, 20), 150_000)
        with self.assertRaises(ValueError):
            live.activity_penalty(0, 100_000, 0)

    def test_zero_minimum_removes_only_the_activity_penalty(self):
        objective = objective_at(self.snapshot / "scripts/training_objective.py")
        for buys in (0, 1, 5, 19, 20, 100):
            candidate = {"total_return": 1234, "buy_trades": buys, "total_trades": buys * 2}
            self.assertEqual(objective.activity_penalty(buys, 100_000, 0), 0)
            self.assertEqual(objective.score_training_candidate(
                candidate, {"total_return": 500}, "SPY", 100_000, minimum_buys=0,
            ), (734, -buys, -2 * buys))
        # Existing positive-minimum scoring and net execution fees remain intact.
        self.assertEqual(objective.activity_penalty(1, 100_000, 20), 142_500)
        self.assertEqual(objective.score_training_candidate(
            {"total_return": -2, "buy_trades": 1, "total_trades": 2},
            {}, 0, 100_000, minimum_buys=0,
        ), (-2, -1, -2))
        with self.assertRaises(ValueError):
            objective.activity_penalty(0, 100_000, -1)

    def test_training_sampler_and_selection_use_unpenalized_objective(self):
        code = r'''
import contextlib
import io
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from scripts import train_trainable_penguins as training
from scripts import plotting
from config.backtest import get_run_output_dir
from pathlib import Path
assert training.TRAINING_MIN_BUY_TRADES == 0
assert plotting.create_training_pareto_pdf.__kwdefaults__ is None
assert plotting.create_training_pareto_pdf.__defaults__[3] == 0
class ActivityStrategy:
    def __init__(self, buys):
        self.name = "ActivityStrategy"
        self.params = SimpleNamespace(buys=buys)
trial_buys = [0, 1, 20]
sampler_history = []
def suggest(strategy_class, completed_trials, rng, np_rng, optuna_search=None):
    sampler_history.append(list(completed_trials))
    return {"buys": trial_buys[len(completed_trials)]}, "test"
def backtest(**kwargs):
    candidate = kwargs["penguin_classes"][0]
    buys = candidate.params.buys
    profit = 10_000 if buys == 1 else 0
    metrics = {"buy_trades": buys, "total_trades": buys * 2,
               "total_return": profit, "final_value": 100_000 + profit}
    return {candidate.name: (None, metrics),
            training.SP500().name: (None, {"total_return": 500})}, {}, [], {}, {}, ""
with patch.multiple(training, TRAINING_ITERATIONS=3, TRAINING_RELATIVE_TO="SPY",
                    suggest_parameters=suggest, run_backtest=backtest,
                    _release_training_trial_memory=lambda: None):
    with contextlib.redirect_stdout(io.StringIO()):
        trained, logs, history, pareto = training._train_trainable_penguins(
            [ActivityStrategy], ["SPY"], [datetime(2024, 1, 2, tzinfo=timezone.utc)],
            "1m", 100_000, 1.0, 1)
assert trained["ActivityStrategy"]["best_params"] == {"buys": 1}
assert trained["ActivityStrategy"]["validation_params"][0]["params"] == {"buys": 1}
assert [item["objective_value"] for item in history] == [-500, 9500, -500]
assert [item["activity_penalty"] for item in history] == [0, 0, 0]
assert sampler_history[-1][-1]["objective_value"] == 9500
assert all(item["activity_penalty"] == 0 for item in pareto["ActivityStrategy"])
print(json.dumps({"best_buys": 1, "objective_values": [-500, 9500, -500]}))
'''
        environment = {**os.environ, "PYTHONPATH": str(self.snapshot),
                       "TRAINING_MIN_BUY_TRADES": "0", "PYTHONDONTWRITEBYTECODE": "1",
                       "ACTIVE_PENGUINS": "EmperorPenguin,GentooPenguin,RockhopperPenguin,SP500"}
        result = subprocess.run([sys.executable, "-c", code], cwd=self.snapshot,
                                env=environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["best_buys"], 1)

    def test_frozen_runner_uses_snapshot_and_does_not_install_packages(self):
        runner = self.snapshot / "run_long_no_buy_penalty.sh"
        result = subprocess.run(["bash", "-n", str(runner)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        text = runner.read_text()
        self.assertIn('cd "$BASE_DIR"', text)
        self.assertIn('export TRAINING_MIN_BUY_TRADES=0', text)
        self.assertNotIn("pip install", text)
        self.assertNotIn("venvPeng/bin/activate", text)
        self.assertEqual((self.snapshot / "run_log").resolve(), PROJECT / "run_log")
        for relative in self.manifest["modified_files"]:
            self.assertNotEqual((self.snapshot / relative).stat().st_ino,
                                (PROJECT / relative).stat().st_ino)


if __name__ == "__main__":
    unittest.main()
