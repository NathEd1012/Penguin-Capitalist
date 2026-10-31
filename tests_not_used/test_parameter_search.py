from dataclasses import asdict

from config.parameter_search_con import strategy_parameter_space
from penguins import EmperorPenguin, GentooPenguin
from scripts.parameter_search import _optuna_suggest


def test_emperor_optuna_search_accepts_baseline_parameters() -> None:
    parameter_space = strategy_parameter_space(EmperorPenguin)
    baseline_params = asdict(EmperorPenguin().params)
    completed_trials = [{
        "status": "completed",
        "params": baseline_params,
        "objective_value": 0.0,
    }]

    suggested_params = _optuna_suggest(parameter_space, completed_trials, seed=42)

    assert set(suggested_params) == set(baseline_params)


def test_optuna_search_ignores_completed_trials_outside_active_range() -> None:
    parameter_space = [("relative_performance_period", "int", 60, 252)]
    completed_trials = [{
        "status": "completed",
        "params": {"relative_performance_period": 20},
        "objective_value": 1.0,
    }]

    suggested_params = _optuna_suggest(parameter_space, completed_trials, seed=42)

    assert 60 <= suggested_params["relative_performance_period"] <= 252


def test_gentoo_parameter_space_is_defined() -> None:
    parameter_space = strategy_parameter_space(GentooPenguin)

    assert {parameter[0] for parameter in parameter_space} == {
        "bb_period",
        "bb_stddev",
        "kaufman_efficiency_ratio_period",
        "kaufman_efficiency_ratio_threshold",
        "max_cash_fraction",
        "stop_loss_pct",
        "take_profit_pct",
        "relative_performance_period",
        "relative_performance_threshold",
        "rvol_period",
        "rvol_threshold",
        "trend_score_threshold",
    }