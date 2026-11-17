from pathlib import Path
import random
import runpy
from datetime import datetime, timezone
from types import SimpleNamespace

import numpy as np
import optuna
from optuna._gp import optim_mixed
import pytest

from scripts import parameter_search as search


@pytest.fixture
def cmaes(monkeypatch):
    space = [("x", "float", -10.0, 10.0), ("y", "float", -10.0, 10.0)]
    monkeypatch.setattr(search, "strategy_parameter_space", lambda strategy: space)
    monkeypatch.setattr(search, "PARAMETER_SEARCH_METHOD", "bayesian_rand")
    monkeypatch.setattr(search, "PARAMETER_SEARCH_BAYESIAN_SAMPLER", "cmaes")
    monkeypatch.setattr(search, "PARAMETER_SEARCH_WARMUP_TRIALS", 10)
    return space


def run_search(count, target=3.0):
    session = search.OptunaSearch()
    rng = random.Random(42)
    history = []
    proposals = []
    sources = []
    for _ in range(count):
        params, source = search.suggest_parameters(object, history, rng, optuna_search=session)
        value = -sum((value - target) ** 2 for value in params.values())
        session.tell(value)
        history.append({"status": "completed", "params": params, "objective_value": value})
        proposals.append(params)
        sources.append(source)
    return session, proposals, sources, history


def test_cmaes_retains_generations_and_includes_warmup_in_500_trials(cmaes):
    session, proposals, sources, history = run_search(500)
    trials = session.study.trials

    assert sources == ["random_warmup"] * 10 + ["optuna_cmaes"] * 490
    assert len(trials) == 500
    assert all(trial.state == optuna.trial.TrialState.COMPLETE for trial in trials)
    assert [trial.params for trial in trials] == proposals
    assert [trial.value for trial in trials] == [item["objective_value"] for item in history]
    assert max(trial.system_attrs.get("cma:generation", -1) for trial in trials) > 2
    assert any(key.startswith("cma:optimizer") for trial in trials for key in trial.system_attrs)
    # The objective must guide proposals toward the optimum, beyond the initial distribution.
    assert max(trial.value for trial in trials[-20:]) > -0.01


def test_cmaes_is_reproducible_and_responds_to_objective_values(cmaes):
    _, positive, _, _ = run_search(40, target=3.0)
    _, repeated, _, _ = run_search(40, target=3.0)
    _, negative, _, _ = run_search(40, target=-3.0)

    assert positive == repeated
    assert positive[:10] == negative[:10]
    assert positive[20:] != negative[20:]


def test_cmaes_rejects_stateless_history_reconstruction(cmaes):
    history = [{"status": "completed", "params": {"x": 0.0, "y": 0.0}, "objective_value": 0.0}]
    with pytest.raises(RuntimeError, match="persistent OptunaSearch"):
        search._optuna_suggest(cmaes, history, seed=42)


def test_cmaes_can_continue_after_failed_trial(cmaes, monkeypatch):
    monkeypatch.setattr(search, "PARAMETER_SEARCH_WARMUP_TRIALS", 0)
    session = search.OptunaSearch()
    rng = random.Random(42)
    search.suggest_parameters(object, [], rng, optuna_search=session)
    with pytest.raises(RuntimeError, match="previous Optuna trial"):
        search.suggest_parameters(object, [], rng, optuna_search=session)
    session.fail()
    search.suggest_parameters(object, [], rng, optuna_search=session)
    session.tell(1.0)

    assert [trial.state for trial in session.study.trials] == [
        optuna.trial.TrialState.FAIL, optuna.trial.TrialState.COMPLETE,
    ]


@pytest.mark.parametrize("warmup", [0, 10])
@pytest.mark.parametrize("skip_first", [False, True])
def test_training_keeps_cmaes_study_per_strategy(cmaes, monkeypatch, warmup, skip_first):
    from scripts import train_trainable_penguins as training

    class ToyStrategy:
        def __init__(self, x, y):
            self.name = type(self).__name__
            self.params = SimpleNamespace(x=x, y=y)

    class OtherStrategy(ToyStrategy):
        pass

    sessions = []

    def create_session():
        session = search.OptunaSearch()
        sessions.append(session)
        return session

    def backtest(**kwargs):
        candidate = kwargs["penguin_classes"][0]
        profit = -(candidate.params.x - 3.0) ** 2 - (candidate.params.y - 3.0) ** 2
        metrics = {
            "buy_trades": 20, "total_trades": 40,
            "total_return": profit, "final_value": 100_000 + profit,
        }
        results = {
            candidate.name: (None, metrics),
            training.SP500().name: (None, {"total_return": 0}),
        }
        return results, {}, [], {}, {}, ""

    timestamp = datetime(2024, 1, 2, tzinfo=timezone.utc)
    windows = iter([[] if skip_first and i % 40 == 0 else [timestamp] for i in range(80)])
    monkeypatch.setattr(search, "PARAMETER_SEARCH_WARMUP_TRIALS", warmup)
    monkeypatch.setattr(training, "PARAMETER_SEARCH_BAYESIAN_SAMPLER", "cmaes")
    monkeypatch.setattr(training, "TRAINING_ITERATIONS", 40)
    monkeypatch.setattr(training, "TRAINING_RELATIVE_TO", 0)
    monkeypatch.setattr(training, "OptunaSearch", create_session)
    monkeypatch.setattr(training, "run_backtest", backtest)
    monkeypatch.setattr(training, "max_period_for_strategies", lambda strategies: 1)
    monkeypatch.setattr(training, "_release_training_trial_memory", lambda: None)
    monkeypatch.setattr(training, "_training_window_subset", lambda *args: next(windows))

    _, _, history, _ = training._train_trainable_penguins(
        [ToyStrategy, OtherStrategy], ["SPY"], [timestamp], "1m", 100_000, 2.0, 1,
    )

    assert len(history) == 80
    assert len(sessions) == 2
    assert sessions[0].study is not sessions[1].study
    for name, session in zip(("ToyStrategy", "OtherStrategy"), sessions):
        completed = [trial for trial in history if trial["strategy"] == name and trial["status"] == "completed"]
        study_completed = session.study.get_trials(states=(optuna.trial.TrialState.COMPLETE,))
        assert len(completed) == 40 - int(skip_first)
        assert [trial.params for trial in study_completed] == [trial["params"] for trial in completed]
        assert [trial.value for trial in study_completed] == [trial["objective_value"] for trial in completed]
        assert sum(trial["proposal_source"] == "random_warmup" for trial in completed) == warmup
        assert max(trial.system_attrs.get("cma:generation", -1) for trial in study_completed) > 1
        assert all(trial.state != optuna.trial.TrialState.RUNNING for trial in session.study.trials)


@pytest.fixture
def acquisition(monkeypatch):
    captured = {}

    def capture(acqf, **kwargs):
        captured["acqf"] = acqf
        return np.array([0.5, 0.5]), 0.0

    class Posterior:
        def posterior(self, x):
            return 1.5 + x.sum(dim=-1), 0.25 + 0.0 * x[..., 0]

    monkeypatch.setattr(optim_mixed, "optimize_acqf_mixed", capture)
    monkeypatch.setattr(search, "PARAMETER_SEARCH_BAYESIAN_SAMPLER", "gp")
    monkeypatch.setattr(search, "PARAMETER_SEARCH_BAYESIAN_UCB_KAPPA", 2.0)
    monkeypatch.setattr(search, "PARAMETER_SEARCH_BAYESIAN_BP_UCB_DELTA", 0.1)

    def build(mode="bp_ucb", weight=1.0):
        monkeypatch.setattr(search, "PARAMETER_SEARCH_BAYESIAN_ACQUISITION", mode)
        monkeypatch.setattr(search, "PARAMETER_SEARCH_BAYESIAN_BP_UCB_LAMBDA", weight)
        sampler = search._optuna_sampler(seed=42)
        sampler._optimize_acqf(
            SimpleNamespace(_gpr=Posterior(), length_scales=np.ones(2), search_space=object()),
            best_params=None,
        )
        return captured["acqf"]

    return build


@pytest.mark.parametrize("mode,weight", [("bp_ucb", 1.0), ("bp_ucb", 2.5), ("bp_ucb", 0.0), ("ucb", 1.0)])
def test_boundary_penalty_values(acquisition, mode, weight):
    acqf = acquisition(mode, weight)
    points = np.array([
        [0.5, 0.5], [0.0, 0.5], [1.0, 0.5], [0.05, 0.5],
        [0.5, 0.95], [0.0, 1.0], [0.1, 0.9], [0.02, 0.04],
    ])
    # Multiple boundary coordinates contribute their maximum, rather than their sum.
    penalties = np.array([0.0, 1.0, 1.0, 0.25, 0.25, 1.0, 0.0, 0.64])
    expected = 2.5 + points.sum(axis=-1)
    if mode == "bp_ucb":
        expected -= weight * penalties

    np.testing.assert_allclose(acqf.eval_acqf_no_grad(points), expected)
    for point, value in zip(points, expected):
        assert acqf.eval_acqf_no_grad(point) == pytest.approx(value)


@pytest.mark.parametrize("point", [[0.02, 0.5], [0.98, 0.5], [0.5, 0.5], [0.1, 0.5]])
def test_boundary_penalty_gradient_matches_finite_differences(acquisition, point):
    acqf = acquisition(weight=1.5)
    point = np.array(point)
    value, gradient = acqf.eval_acqf_with_grad(point)
    offsets = np.eye(2) * 1e-7
    expected = np.array([
        (acqf.eval_acqf_no_grad(point + offset) - acqf.eval_acqf_no_grad(point - offset)) / 2e-7
        for offset in offsets
    ])
    assert value == pytest.approx(acqf.eval_acqf_no_grad(point))
    np.testing.assert_allclose(gradient, expected, atol=1e-5)


def load_config(monkeypatch, mode="bp_ucb", sampler="gp"):
    monkeypatch.setenv("PARAMETER_SEARCH_BAYESIAN_SAMPLER", sampler)
    monkeypatch.setenv("PARAMETER_SEARCH_BAYESIAN_ACQUISITION", mode)
    return runpy.run_path(str(Path(search.__file__).parents[1] / "config" / "parameter_search_con.py"))


@pytest.mark.parametrize("mode", ["ei", "ucb", "bp_ucb"])
def test_gp_acquisition_configuration(monkeypatch, mode):
    monkeypatch.delenv("PARAMETER_SEARCH_BAYESIAN_BP_UCB_LAMBDA", raising=False)
    monkeypatch.delenv("PARAMETER_SEARCH_BAYESIAN_BP_UCB_DELTA", raising=False)
    config = load_config(monkeypatch, mode)
    assert config["PARAMETER_SEARCH_STRATEGY"] == f"gp_{mode}"
    assert config["SEARCH_STRATEGIES"][f"gp_{mode}"] == {"sampler": "gp", "acquisition": mode}
    assert config["PARAMETER_SEARCH_BAYESIAN_BP_UCB_LAMBDA"] == 1.0
    assert config["PARAMETER_SEARCH_BAYESIAN_BP_UCB_DELTA"] == 0.1


def test_boundary_penalty_configuration_overrides(monkeypatch):
    monkeypatch.setenv("PARAMETER_SEARCH_BAYESIAN_BP_UCB_LAMBDA", "0")
    monkeypatch.setenv("PARAMETER_SEARCH_BAYESIAN_BP_UCB_DELTA", "0.2")
    config = load_config(monkeypatch)
    assert config["PARAMETER_SEARCH_BAYESIAN_BP_UCB_LAMBDA"] == 0.0
    assert config["PARAMETER_SEARCH_BAYESIAN_BP_UCB_DELTA"] == 0.2


@pytest.mark.parametrize("sampler", ["tpe", "cmaes"])
def test_boundary_penalty_requires_gp(monkeypatch, sampler):
    with pytest.raises(ValueError, match="requires the gp sampler"):
        load_config(monkeypatch, sampler=sampler)


@pytest.mark.parametrize("setting,value", [
    ("LAMBDA", "-1"), ("LAMBDA", "nan"), ("LAMBDA", "inf"),
    ("DELTA", "0"), ("DELTA", "-0.1"), ("DELTA", "nan"), ("DELTA", "inf"),
])
def test_invalid_boundary_penalty_settings(monkeypatch, setting, value):
    variable = f"PARAMETER_SEARCH_BAYESIAN_BP_UCB_{setting}"
    monkeypatch.setenv(variable, value)
    with pytest.raises(ValueError, match=variable):
        load_config(monkeypatch)
