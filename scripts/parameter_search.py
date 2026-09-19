"""Candidate generation for trainable-strategy parameter searches."""
import math
import random
from typing import Dict, List

from config.parameter_search_con import (
    PARAMETER_SEARCH_BAYESIAN_ACQUISITION,
    PARAMETER_SEARCH_BAYESIAN_SAMPLER,
    PARAMETER_SEARCH_BAYESIAN_UCB_KAPPA,
    PARAMETER_SEARCH_METHOD,
    PARAMETER_SEARCH_WARMUP_TRIALS,
    strategy_parameter_space,
)

ParameterSpace = List[tuple[str, str, float, float]]
ParameterValues = Dict[str, int | float]


class _UCBGPSampler:
    """Optuna GPSampler with an upper-confidence-bound acquisition function."""

    def __new__(cls, seed: int):
        try:
            import numpy as np
            import torch
            from optuna._gp import optim_mixed
            from optuna.samplers import GPSampler
        except ImportError as exc:
            raise RuntimeError(
                "UCB acquisition requires Optuna, NumPy, and PyTorch. Install requirements.txt."
            ) from exc

        class UCBGPSampler(GPSampler):
            def _optimize_acqf(self, acqf, best_params):
                gpr = acqf._gpr
                kappa = PARAMETER_SEARCH_BAYESIAN_UCB_KAPPA

                class UCB:
                    length_scales = acqf.length_scales
                    search_space = acqf.search_space

                    def eval_acqf(self, x):
                        mean, variance = gpr.posterior(x)
                        return mean + kappa * torch.sqrt(torch.clamp(variance, min=0.0))

                    def eval_acqf_no_grad(self, x):
                        with torch.no_grad():
                            return self.eval_acqf(torch.from_numpy(x)).detach().numpy()

                    def eval_acqf_with_grad(self, x):
                        x_tensor = torch.from_numpy(x).requires_grad_(True)
                        value = self.eval_acqf(x_tensor)
                        value.backward()
                        return value.item(), x_tensor.grad.detach().numpy()

                return optim_mixed.optimize_acqf_mixed(
                    UCB(),
                    warmstart_normalized_params_array=best_params,
                    n_preliminary_samples=self._n_preliminary_samples,
                    n_local_search=self._n_local_search,
                    tol=self._tol,
                    rng=self._rng.rng,
                )[0]

        return UCBGPSampler(seed=seed, n_startup_trials=0)


def _sample_parameters_from_space(parameter_space: ParameterSpace, rng: random.Random) -> ParameterValues:
    return {
        name: rng.randint(int(low), int(high)) if kind == "int" else round(rng.uniform(float(low), float(high)), 4)
        for name, kind, low, high in parameter_space
    }


def _grid_parameters_from_space(parameter_space: ParameterSpace, point_index: int, point_count: int) -> ParameterValues:
    """Select a deterministic point from a compact Cartesian grid."""
    levels = max(2, math.ceil(point_count ** (1.0 / max(1, len(parameter_space)))))
    point = point_index % max(1, levels ** len(parameter_space))
    params: ParameterValues = {}
    for name, kind, low, high in parameter_space:
        level = point % levels
        point //= levels
        fraction = level / (levels - 1)
        value = float(low) + fraction * (float(high) - float(low))
        params[name] = int(round(value)) if kind == "int" else round(value, 4)
    return params


def _optuna_sampler(seed: int):
    try:
        import optuna
    except ImportError as exc:
        raise RuntimeError("Optuna is required for Bayesian parameter search. Install requirements.txt.") from exc

    if PARAMETER_SEARCH_BAYESIAN_SAMPLER == "tpe":
        return optuna.samplers.TPESampler(seed=seed, n_startup_trials=0)
    if PARAMETER_SEARCH_BAYESIAN_ACQUISITION == "ucb":
        return _UCBGPSampler(seed)
    if not hasattr(optuna.samplers, "GPSampler"):
        raise RuntimeError("The installed Optuna version does not provide GPSampler; install optuna>=4.0.0.")
    return optuna.samplers.GPSampler(seed=seed, n_startup_trials=0)


def _optuna_suggest(
    parameter_space: ParameterSpace,
    completed_trials: list[dict[str, object]],
    seed: int,
) -> ParameterValues:
    import optuna

    study = optuna.create_study(direction="maximize", sampler=_optuna_sampler(seed))
    distributions = {}
    for name, kind, low, high in parameter_space:
        if kind == "int":
            distributions[name] = optuna.distributions.IntDistribution(int(low), int(high))
        else:
            distributions[name] = optuna.distributions.FloatDistribution(float(low), float(high))

    for trial in completed_trials:
        if trial.get("status") != "completed":
            continue
        study.add_trial(optuna.trial.create_trial(
            params=dict(trial["params"]),
            distributions=distributions,
            value=float(trial["objective_value"]),
        ))

    trial = study.ask()
    params: ParameterValues = {}
    for name, kind, low, high in parameter_space:
        if kind == "int":
            params[name] = trial.suggest_int(name, int(low), int(high))
        else:
            params[name] = round(trial.suggest_float(name, float(low), float(high)), 4)
    return params


def suggest_parameters(strategy_class, completed_trials, rng, np_rng=None):
    """Suggest the next parameters using random/grid or an Optuna sampler."""
    del np_rng
    parameter_space = strategy_parameter_space(strategy_class)
    method = PARAMETER_SEARCH_METHOD
    completed_count = len([trial for trial in completed_trials if trial.get("status") == "completed"])

    if method == "random":
        return _sample_parameters_from_space(parameter_space, rng), "random"
    if method == "grid":
        return _grid_parameters_from_space(parameter_space, completed_count, max(1, PARAMETER_SEARCH_WARMUP_TRIALS)), "grid"
    if method == "bayesian_grid" and completed_count < PARAMETER_SEARCH_WARMUP_TRIALS:
        return _grid_parameters_from_space(parameter_space, completed_count, PARAMETER_SEARCH_WARMUP_TRIALS), "grid"
    if method == "rand_baysian" and completed_count < PARAMETER_SEARCH_WARMUP_TRIALS:
        return _sample_parameters_from_space(parameter_space, rng), "random_warmup"
    if method not in {"bayesian", "bayesian_grid", "rand_baysian"}:
        raise ValueError(f"Unsupported PARAMETER_SEARCH_METHOD: {method}")

    params = _optuna_suggest(parameter_space, completed_trials, rng.randrange(0, 2**32))
    return params, f"optuna_{PARAMETER_SEARCH_BAYESIAN_SAMPLER}"


_strategy_parameter_space = strategy_parameter_space
