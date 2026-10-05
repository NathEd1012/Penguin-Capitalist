from dataclasses import asdict

from config.parameter_search_con import strategy_parameter_space
from penguins import Emperor_Penguin, Simpler_Penguin
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


def test_simpler_parameter_space_is_defined() -> None:
    parameter_space = strategy_parameter_space(Simpler_Penguin)

    assert {parameter[0] for parameter in parameter_space} == {
        "bb_period",
        "bb_stddev",
        "adx_period",
        "adx_threshold",
        "max_cash_fraction",
        "stop_loss_pct",
        "take_profit_pct",
        "relative_strength_period",
        "relative_strength_threshold",
        "rvol_period",
        "rvol_threshold",
        "trend_score_threshold",
    }