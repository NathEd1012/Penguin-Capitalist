from dataclasses import asdict

from config.parameter_search_con import strategy_parameter_space
from penguins import Emperor_Penguin
from scripts.parameter_search import _optuna_suggest


def test_emperor_optuna_search_accepts_baseline_parameters() -> None:
    parameter_space = strategy_parameter_space(Emperor_Penguin)
    baseline_params = asdict(Emperor_Penguin().params)
    completed_trials = [{
        "status": "completed",
        "params": baseline_params,
        "objective_value": 0.0,
    }]

    suggested_params = _optuna_suggest(parameter_space, completed_trials, seed=42)

    assert set(suggested_params) == set(baseline_params)