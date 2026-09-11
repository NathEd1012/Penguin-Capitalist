"""Candidate generation for trainable-strategy parameter searches."""
import math
import random
from typing import Dict, List

import numpy as np

from config.parameter_search import (
    PARAMETER_SEARCH_BAYESIAN_CANDIDATE_POOL_SIZE,
    PARAMETER_SEARCH_BAYESIAN_LENGTH_SCALE,
    PARAMETER_SEARCH_BAYESIAN_LOCAL_CANDIDATE_COUNT,
    PARAMETER_SEARCH_BAYESIAN_LOCAL_JITTER,
    PARAMETER_SEARCH_BAYESIAN_MIN_WARMUP_TRIALS,
    PARAMETER_SEARCH_BAYESIAN_OBSERVATION_NOISE,
    PARAMETER_SEARCH_GRID_POINTS,
    PARAMETER_SEARCH_METHOD,
    strategy_parameter_space,
)

ParameterSpace = List[tuple[str, str, float, float]]
ParameterValues = Dict[str, int | float]


def _sample_parameters_from_space(parameter_space: ParameterSpace, rng: random.Random) -> ParameterValues:
    sampled: ParameterValues = {}
    for name, kind, low, high in parameter_space:
        sampled[name] = rng.randint(int(low), int(high)) if kind == "int" else round(rng.uniform(float(low), float(high)), 4)
    return sampled


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


def _trainable_params_to_vector(params: ParameterValues, parameter_space: ParameterSpace) -> np.ndarray:
    values = []
    for name, _kind, low, high in parameter_space:
        span = float(high) - float(low)
        values.append(0.0 if span <= 0 else float(np.clip((float(params[name]) - float(low)) / span, 0.0, 1.0)))
    return np.asarray(values, dtype=float)


def _vector_to_trainable_params(vector: np.ndarray, parameter_space: ParameterSpace) -> ParameterValues:
    params: ParameterValues = {}
    bounded_vector = np.clip(np.asarray(vector, dtype=float), 0.0, 1.0)
    for index, (name, kind, low, high) in enumerate(parameter_space):
        value = float(low) + bounded_vector[index] * (float(high) - float(low))
        params[name] = int(round(value)) if kind == "int" else round(value, 4)
    return params


def _rbf_kernel(left: np.ndarray, right: np.ndarray, length_scale: float) -> np.ndarray:
    diff = np.atleast_2d(left)[:, None, :] - np.atleast_2d(right)[None, :, :]
    squared_distance = np.sum(diff * diff, axis=2)
    scaled_length = max(float(length_scale), 1e-6)
    return np.exp(-0.5 * squared_distance / (scaled_length * scaled_length))


def _predict_gaussian_process(train_x, train_y, candidate_x):
    y_mean = float(train_y.mean())
    y_std = max(float(train_y.std()), 1e-9)
    normalized_y = (train_y - y_mean) / y_std
    kernel = _rbf_kernel(train_x, train_x, PARAMETER_SEARCH_BAYESIAN_LENGTH_SCALE)
    kernel += (PARAMETER_SEARCH_BAYESIAN_OBSERVATION_NOISE ** 2 + 1e-8) * np.eye(len(train_x))
    try:
        factor = np.linalg.cholesky(kernel)
        alpha = np.linalg.solve(factor.T, np.linalg.solve(factor, normalized_y))
        cross_kernel = _rbf_kernel(candidate_x, train_x, PARAMETER_SEARCH_BAYESIAN_LENGTH_SCALE)
        mean = cross_kernel @ alpha
        projection = np.linalg.solve(factor, cross_kernel.T)
        variance = np.maximum(0.0, 1.0 - np.sum(projection * projection, axis=0))
    except np.linalg.LinAlgError:
        mean = np.full(len(candidate_x), normalized_y.mean())
        variance = np.full(len(candidate_x), normalized_y.var() if len(normalized_y) > 1 else 1.0)
    return mean * y_std + y_mean, np.sqrt(variance) * y_std


def _expected_improvement(mu, sigma, best_y, xi=0.01):
    improvement = mu - best_y - xi
    safe_sigma = np.maximum(sigma, 1e-12)
    z = improvement / safe_sigma
    normal_pdf = np.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)
    normal_cdf = np.vectorize(lambda value: 0.5 * (1.0 + math.erf(value / math.sqrt(2.0))))(z)
    return improvement * normal_cdf + safe_sigma * normal_pdf


def _bayesian_parameters(parameter_space, completed_trials, rng, np_rng):
    warmup_trials = min(PARAMETER_SEARCH_BAYESIAN_MIN_WARMUP_TRIALS, max(2, len(parameter_space)))
    completed = [trial for trial in completed_trials if trial.get("status") == "completed"]
    if len(completed) < warmup_trials:
        return _sample_parameters_from_space(parameter_space, rng), "random_warmup"

    train_x = np.asarray([_trainable_params_to_vector(dict(trial["params"]), parameter_space) for trial in completed])
    train_y = np.asarray([float(trial["objective_value"]) for trial in completed])
    candidates = []
    sources = []
    for _ in range(max(PARAMETER_SEARCH_BAYESIAN_CANDIDATE_POOL_SIZE, len(parameter_space) * 8)):
        candidates.append(_sample_parameters_from_space(parameter_space, rng))
        sources.append("random")
    best_vector = train_x[int(np.argmax(train_y))]
    for _ in range(max(PARAMETER_SEARCH_BAYESIAN_LOCAL_CANDIDATE_COUNT, len(parameter_space) * 2)):
        vector = np.clip(best_vector + np_rng.normal(0.0, PARAMETER_SEARCH_BAYESIAN_LOCAL_JITTER, len(parameter_space)), 0.0, 1.0)
        candidates.append(_vector_to_trainable_params(vector, parameter_space))
        sources.append("local")

    candidate_x = np.asarray([_trainable_params_to_vector(candidate, parameter_space) for candidate in candidates])
    mean, sigma = _predict_gaussian_process(train_x, train_y, candidate_x)
    acquisition = _expected_improvement(mean, sigma, float(np.max(train_y)))
    if not np.isfinite(acquisition).any():
        return _sample_parameters_from_space(parameter_space, rng), "random_fallback"
    index = int(np.nanargmax(acquisition))
    return candidates[index], f"bayesian_ei/{sources[index]}"


def suggest_parameters(strategy_class, completed_trials, rng, np_rng):
    """Suggest the next parameters according to the configured search method."""
    parameter_space = strategy_parameter_space(strategy_class)
    method = PARAMETER_SEARCH_METHOD
    completed_count = len([trial for trial in completed_trials if trial.get("status") == "completed"])
    if method == "random":
        return _sample_parameters_from_space(parameter_space, rng), "random"
    if method == "grid":
        return _grid_parameters_from_space(parameter_space, completed_count, max(1, PARAMETER_SEARCH_GRID_POINTS)), "grid"
    if method == "bayesian_grid" and completed_count < PARAMETER_SEARCH_GRID_POINTS:
        return _grid_parameters_from_space(parameter_space, completed_count, PARAMETER_SEARCH_GRID_POINTS), "grid"
    if method not in {"bayesian", "bayesian_grid"}:
        raise ValueError(f"Unsupported PARAMETER_SEARCH_METHOD: {method}")
    return _bayesian_parameters(parameter_space, completed_trials, rng, np_rng)


# Compatibility for callers that used the old private helper.
_strategy_parameter_space = strategy_parameter_space
_suggest_bayesian_trainable_params = lambda strategy_class, completed_trials, rng, np_rng: _bayesian_parameters(
    strategy_parameter_space(strategy_class), completed_trials, rng, np_rng
)