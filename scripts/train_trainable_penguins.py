"""Standalone training entry point for the trainable penguin strategies."""
from contextlib import redirect_stderr, redirect_stdout
import json
import math
import os
import random
import sys
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List

import numpy as np
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtest.data_loader import DataLoader
from config import (
    INITIAL_CAPITAL,
    BINNING,
    TRAINING_START_DATE,
    TRAINING_STOP_DATE,
    SYMBOLS,
    TRAINABLE_PENGUINS,
    TRAINING_ITERATIONS,
    TRAINING_RELATIVE_TO,
    TRAINING_SUBSET_MONTHS,
    TRAINING_SUBSET_STOCKS,
    TRAINING_TRANSACTION_COST,
    TRAINING_RANDOM_SEED,
    TRAINING_RESULTS_FILENAME,
    TRAINING_LOG_FILENAME,
    TRAINING_PARAMETER_LOG_FILENAME,
    TRAINING_PARAMETER_DELTA_FILENAME,
    TRAINING_PARETO_FILENAME,
    PLOT_PARETO,
)
from run_simulation import parse_datetime_string, run_backtest
from penguins import SP500
from scripts.plotting import create_training_pareto_pdf


def _print_training_configuration() -> None:
    print("\nTRAINING CONFIGURATION")
    print(f"Relative To:       {TRAINING_RELATIVE_TO}")
    print(f"Training Steps:    {TRAINING_ITERATIONS}")
    print(f"Training Sample:   {TRAINING_SUBSET_STOCKS} stocks x {TRAINING_SUBSET_MONTHS} month(s)")
    print(f"Training Cost:     ${TRAINING_TRANSACTION_COST:.2f}")
    print(f"Training Seed:     {TRAINING_RANDOM_SEED}")
    print("=" * 80)


TRAINING_BAYESIAN_MIN_WARMUP_TRIALS = 4
TRAINING_BAYESIAN_CANDIDATE_POOL_SIZE = 64
TRAINING_BAYESIAN_LOCAL_CANDIDATE_COUNT = 32
TRAINING_BAYESIAN_LOCAL_JITTER = 0.08
TRAINING_BAYESIAN_LENGTH_SCALE = 0.35
TRAINING_BAYESIAN_OBSERVATION_NOISE = 0.15


def _strategy_parameter_space(strategy_class) -> List[tuple[str, str, float, float]]:
    strategy_name = strategy_class.__name__
    if strategy_name.endswith(("Adv_SELL_TP1", "Adv_SELL_TP1_Manual")):
        return [
            ("rsi_period", "int", 7, 28),
            ("buy_rsi", "float", 18.0, 42.0),
            ("sell_rsi", "float", 55.0, 88.0),
            ("adx_period", "int", 7, 28),
            ("adx_threshold", "float", 10.0, 40.0),
            ("max_cash_fraction", "float", 0.02, 0.20),
            ("stop_loss_pct", "float", 0.01, 0.10),
            ("take_profit_pct", "float", 0.02, 0.20),
            ("cooldown_bars", "int", 0, 30),
            ("relative_strength_period", "int", 7, 40),
            ("relative_strength_threshold", "float", -1.0, 1.0),
            ("rvol_period", "int", 7, 40),
            ("rvol_threshold", "float", 0.5, 4.0),
        ]
    if strategy_name.endswith(("Adv_SELL_TP2", "Adv_SELL_TP2_Manual", "Adv_SELL_TP3", "Adv_SELL_TP3_Manual")):
        return [
            ("bb_period", "int", 10, 40),
            ("bb_stddev", "float", 1.0, 3.5),
            ("adx_period", "int", 7, 28),
            ("adx_threshold", "float", 10.0, 40.0),
            ("max_cash_fraction", "float", 0.02, 0.20),
            ("stop_loss_pct", "float", 0.01, 0.10),
            ("take_profit_pct", "float", 0.02, 0.20),
            ("cooldown_bars", "int", 0, 30),
            ("relative_strength_period", "int", 7, 40),
            ("relative_strength_threshold", "float", -1.0, 1.0),
            ("rvol_period", "int", 7, 40),
            ("rvol_threshold", "float", 0.5, 4.0),
        ]
    if strategy_name.endswith(("OG_TP4", "OG_TP4_Manual")):
        return [
            ("rsi_period", "int", 7, 28),
            ("buy_rsi", "float", 18.0, 42.0),
            ("sell_rsi", "float", 55.0, 88.0),
            ("max_cash_fraction", "float", 0.02, 0.20),
            ("stop_loss_pct", "float", 0.01, 0.10),
            ("take_profit_pct", "float", 0.02, 0.20),
            ("cooldown_bars", "int", 0, 30),
            ("strength_cap", "float", 1.0, 2.0),
        ]
    if strategy_name.endswith(("Adv_SELL_TP4", "Adv_SELL_TP4_Manual")):
        return [
            ("rsi_period", "int", 7, 28),
            ("buy_rsi", "float", 18.0, 42.0),
            ("sell_rsi", "float", 55.0, 88.0),
            ("max_cash_fraction", "float", 0.02, 0.20),
            ("stop_loss_pct", "float", 0.01, 0.10),
            ("take_profit_pct", "float", 0.02, 0.20),
            ("cooldown_bars", "int", 0, 30),
            ("relative_strength_period", "int", 7, 40),
            ("relative_strength_threshold", "float", -1.0, 1.0),
            ("rvol_period", "int", 7, 40),
            ("rvol_threshold", "float", 0.5, 4.0),
        ]
    if strategy_name.endswith(("OG_TP1", "OG_TP1_Manual", "TrainablePenguin1", "TrainablePenguin1_Manual")):
        return [
            ("rsi_period", "int", 7, 28),
            ("buy_rsi", "float", 18.0, 42.0),
            ("sell_rsi", "float", 55.0, 88.0),
            ("adx_period", "int", 7, 28),
            ("adx_threshold", "float", 10.0, 40.0),
            ("max_cash_fraction", "float", 0.02, 0.20),
            ("stop_loss_pct", "float", 0.01, 0.10),
            ("take_profit_pct", "float", 0.02, 0.20),
            ("cooldown_bars", "int", 0, 30),
            ("strength_cap", "float", 1.0, 2.0),
        ]
    if strategy_name.endswith(("OG_TP2", "OG_TP2_Manual", "TrainablePenguin2", "TrainablePenguin2_Manual", "OG_TP3", "OG_TP3_Manual", "TrainablePenguin3", "TrainablePenguin3_Manual")):
        return [
            ("bb_period", "int", 10, 40),
            ("bb_stddev", "float", 1.0, 3.5),
            ("adx_period", "int", 7, 28),
            ("adx_threshold", "float", 10.0, 40.0),
            ("max_cash_fraction", "float", 0.02, 0.20),
            ("stop_loss_pct", "float", 0.01, 0.10),
            ("take_profit_pct", "float", 0.02, 0.20),
            ("cooldown_bars", "int", 0, 30),
            ("strength_cap", "float", 1.0, 2.0),
        ]
    raise ValueError(f"No parameter space is defined for {strategy_name}")


def _sample_parameters_from_space(
    parameter_space: List[tuple[str, str, float, float]],
    rng: random.Random,
) -> Dict[str, int | float]:
    sampled: Dict[str, int | float] = {}
    for name, kind, low, high in parameter_space:
        if kind == "int":
            sampled[name] = rng.randint(int(low), int(high))
        else:
            sampled[name] = round(rng.uniform(float(low), float(high)), 4)
    return sampled


def _trainable_params_to_vector(
    params: Dict[str, int | float],
    parameter_space: List[tuple[str, str, float, float]],
) -> np.ndarray:
    values = []
    for name, kind, low, high in parameter_space:
        span = float(high) - float(low)
        if span <= 0:
            values.append(0.0)
            continue

        raw_value = params[name]
        normalized_value = (float(raw_value) - float(low)) / span
        values.append(float(np.clip(normalized_value, 0.0, 1.0)))
    return np.asarray(values, dtype=float)


def _vector_to_trainable_params(
    vector: np.ndarray,
    parameter_space: List[tuple[str, str, float, float]],
) -> Dict[str, int | float]:
    params: Dict[str, int | float] = {}
    bounded_vector = np.clip(np.asarray(vector, dtype=float), 0.0, 1.0)
    for index, (name, kind, low, high) in enumerate(parameter_space):
        value = float(low) + bounded_vector[index] * (float(high) - float(low))
        if kind == "int":
            params[name] = int(round(value))
        else:
            params[name] = float(round(value, 4))
    return params


def _rbf_kernel(left: np.ndarray, right: np.ndarray, length_scale: float) -> np.ndarray:
    left = np.atleast_2d(np.asarray(left, dtype=float))
    right = np.atleast_2d(np.asarray(right, dtype=float))
    diff = left[:, None, :] - right[None, :, :]
    squared_distance = np.sum(diff * diff, axis=2)
    scaled_length = max(float(length_scale), 1e-6)
    return np.exp(-0.5 * squared_distance / (scaled_length * scaled_length))


def _predict_gaussian_process(
    train_x: np.ndarray,
    train_y: np.ndarray,
    candidate_x: np.ndarray,
    length_scale: float,
    observation_noise: float,
) -> tuple[np.ndarray, np.ndarray]:
    if len(train_x) == 0:
        candidate_count = len(candidate_x)
        return np.zeros(candidate_count, dtype=float), np.ones(candidate_count, dtype=float)

    train_x = np.asarray(train_x, dtype=float)
    train_y = np.asarray(train_y, dtype=float)
    candidate_x = np.asarray(candidate_x, dtype=float)

    y_mean = float(train_y.mean())
    y_std = float(train_y.std())
    if y_std < 1e-9:
        y_std = 1.0

    y_normalized = (train_y - y_mean) / y_std
    kernel = _rbf_kernel(train_x, train_x, length_scale)
    kernel += (observation_noise * observation_noise + 1e-8) * np.eye(len(train_x), dtype=float)

    try:
        cholesky_factor = np.linalg.cholesky(kernel)
        alpha = np.linalg.solve(cholesky_factor.T, np.linalg.solve(cholesky_factor, y_normalized))
        cross_kernel = _rbf_kernel(candidate_x, train_x, length_scale)
        normalized_mean = cross_kernel @ alpha
        projection = np.linalg.solve(cholesky_factor, cross_kernel.T)
        normalized_variance = np.maximum(0.0, 1.0 - np.sum(projection * projection, axis=0))
    except np.linalg.LinAlgError:
        normalized_mean = np.full(len(candidate_x), float(y_normalized.mean()), dtype=float)
        normalized_variance = np.full(len(candidate_x), float(y_normalized.var() if len(y_normalized) > 1 else 1.0), dtype=float)

    return normalized_mean * y_std + y_mean, np.sqrt(np.maximum(normalized_variance, 0.0)) * y_std


def _expected_improvement(mu: np.ndarray, sigma: np.ndarray, best_y: float, xi: float = 0.01) -> np.ndarray:
    improvement = mu - best_y - xi
    safe_sigma = np.maximum(sigma, 1e-12)
    z = improvement / safe_sigma
    normal_pdf = np.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)
    normal_cdf = np.vectorize(lambda value: 0.5 * (1.0 + math.erf(value / math.sqrt(2.0))))(z)
    return improvement * normal_cdf + safe_sigma * normal_pdf


def _suggest_bayesian_trainable_params(
    strategy_class,
    completed_trials: List[Dict[str, object]],
    rng: random.Random,
    np_rng: np.random.Generator,
) -> tuple[Dict[str, int | float], str]:
    parameter_space = _strategy_parameter_space(strategy_class)
    warmup_trials = min(TRAINING_BAYESIAN_MIN_WARMUP_TRIALS, max(2, len(parameter_space)))

    completed_candidates = [trial for trial in completed_trials if trial.get("status") == "completed"]
    if len(completed_candidates) < warmup_trials:
        return _sample_parameters_from_space(parameter_space, rng), "random_warmup"

    train_x = np.asarray([
        _trainable_params_to_vector(dict(trial["params"]), parameter_space)
        for trial in completed_candidates
    ], dtype=float)
    train_y = np.asarray([float(trial["objective_value"]) for trial in completed_candidates], dtype=float)

    candidate_params: List[Dict[str, int | float]] = []
    candidate_vectors: List[np.ndarray] = []
    candidate_sources: List[str] = []

    random_candidate_count = max(TRAINING_BAYESIAN_CANDIDATE_POOL_SIZE, len(parameter_space) * 8)
    for _ in range(random_candidate_count):
        params = _sample_parameters_from_space(parameter_space, rng)
        candidate_params.append(params)
        candidate_vectors.append(_trainable_params_to_vector(params, parameter_space))
        candidate_sources.append("random")

    best_trial_index = int(np.argmax(train_y))
    best_vector = train_x[best_trial_index]
    local_candidate_count = max(TRAINING_BAYESIAN_LOCAL_CANDIDATE_COUNT, len(parameter_space) * 2)
    for _ in range(local_candidate_count):
        perturbation = np_rng.normal(0.0, TRAINING_BAYESIAN_LOCAL_JITTER, size=len(parameter_space))
        candidate_vector = np.clip(best_vector + perturbation, 0.0, 1.0)
        params = _vector_to_trainable_params(candidate_vector, parameter_space)
        candidate_params.append(params)
        candidate_vectors.append(_trainable_params_to_vector(params, parameter_space))
        candidate_sources.append("local")

    candidate_matrix = np.asarray(candidate_vectors, dtype=float)
    predicted_mean, predicted_sigma = _predict_gaussian_process(
        train_x=train_x,
        train_y=train_y,
        candidate_x=candidate_matrix,
        length_scale=TRAINING_BAYESIAN_LENGTH_SCALE,
        observation_noise=TRAINING_BAYESIAN_OBSERVATION_NOISE,
    )
    acquisition = _expected_improvement(predicted_mean, predicted_sigma, float(np.max(train_y)))
    if not np.isfinite(acquisition).any():
        return _sample_parameters_from_space(parameter_space, rng), "random_fallback"

    best_candidate_index = int(np.nanargmax(acquisition))
    return candidate_params[best_candidate_index], f"bayesian_ei/{candidate_sources[best_candidate_index]}"


def _objective_from_score(score: tuple[float, int, int]) -> float:
    return float(score[0])


def _training_benchmark_symbol(relative_to: int | str) -> str:
    return "SPY" if relative_to == 0 else str(relative_to)


def _training_symbol_subset(symbols: List[str], target_count: int, benchmark_symbol: str, rng: random.Random) -> List[str]:
    pool = list(dict.fromkeys(symbols))
    if benchmark_symbol in pool:
        pool.remove(benchmark_symbol)

    sample_size = min(len(pool), max(0, target_count - 1))
    subset = rng.sample(pool, sample_size) if sample_size > 0 else []
    if benchmark_symbol not in subset:
        subset.append(benchmark_symbol)
    return sorted(subset)


def _training_window_subset(sorted_timestamps: List[datetime], months: int, rng: random.Random) -> List[datetime]:
    if not sorted_timestamps:
        return []

    window_length = timedelta(days=max(1, months) * 30)
    latest_start = sorted_timestamps[-1] - window_length
    eligible_starts = [timestamp for timestamp in sorted_timestamps if timestamp <= latest_start]
    start_timestamp = rng.choice(eligible_starts) if eligible_starts else sorted_timestamps[0]
    end_timestamp = start_timestamp + window_length
    return [timestamp for timestamp in sorted_timestamps if start_timestamp <= timestamp <= end_timestamp]


def _training_profit_amount(candidate_metrics: Dict, benchmark_metrics: Dict, relative_to: int | str) -> float:
    candidate_profit = float(candidate_metrics.get("total_return", 0.0))
    if relative_to not in (0, "0", None, False):
        return candidate_profit - float(benchmark_metrics.get("total_return", 0.0))
    return candidate_profit


def _score_training_candidate(
    candidate_metrics: Dict,
    benchmark_metrics: Dict,
    transaction_cost: float,
    relative_to: int | str,
) -> tuple[float, int, int]:
    buy_trades = int(candidate_metrics.get("buy_trades", candidate_metrics.get("total_trades", 0)))
    relative_profit_amount = _training_profit_amount(candidate_metrics, benchmark_metrics, relative_to)
    return (
        relative_profit_amount - (buy_trades * transaction_cost),
        -buy_trades,
        -int(candidate_metrics.get("total_trades", 0)),
    )


def _format_trainable_params(params: Dict[str, int | float]) -> str:
    if not params:
        return "<no parameters>"
    return ", ".join(f"{key}={value}" for key, value in sorted(params.items()))


def _format_training_timestamp(timestamp: datetime) -> str:
    return timestamp.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _format_training_symbols(trial_symbols: List[str], limit: int = 20) -> str:
    if not trial_symbols:
        return "<none>"
    if len(trial_symbols) <= limit:
        return ", ".join(trial_symbols)
    head = ", ".join(trial_symbols[:limit])
    return f"{head}, ... (+{len(trial_symbols) - limit} more)"


def _format_param_changes(current_params: Dict[str, int | float], previous_params: Dict[str, int | float] | None) -> str:
    if not previous_params:
        return "initial sample"

    changes = []
    for key in sorted(set(current_params) | set(previous_params)):
        previous_value = previous_params.get(key)
        current_value = current_params.get(key)
        if previous_value == current_value:
            continue
        if key not in previous_params:
            changes.append(f"{key}: <new> -> {current_value}")
        elif key not in current_params:
            changes.append(f"{key}: {previous_value} -> <removed>")
        else:
            changes.append(f"{key}: {previous_value} -> {current_value}")

    return "; ".join(changes) if changes else "no parameter change"


def _format_trainable_parameter_delta_report(trained_parameters: Dict[str, Dict[str, object]]) -> str:
    lines: List[str] = [
        f"Trainable parameter delta report generated at {datetime.now(timezone.utc).isoformat()}",
        "Format: initial -> after_training",
    ]

    # List every parameter and its change; alias handling is unnecessary.

    for strategy_name in sorted(trained_parameters):
        strategy_result = trained_parameters.get(strategy_name, {})
        initial_params = dict(strategy_result.get("initial_params") or {})
        final_params = dict(strategy_result.get("best_params") or {})

        lines.append("")
        lines.append(f"{strategy_name}:")
        all_keys = set(initial_params) | set(final_params)
        if not all_keys:
            lines.append("  <no parameters>")
            continue

        for key in sorted(all_keys):
            initial_value = initial_params.get(key, "<missing>")
            final_value = final_params.get(key, "<missing>")
            lines.append(f"  {key}: {initial_value} -> {final_value}")

    return "\n".join(lines) + "\n"


def _penguin_history_requirements(penguin) -> tuple[int, int]:
    """Return (visible history window, minimum history before trading)."""
    try:
        lookback_bars = int(getattr(penguin, "LOOKBACK_BARS", 1000))
    except (TypeError, ValueError):
        lookback_bars = 1000

    try:
        min_history_required = int(getattr(penguin, "MIN_HISTORY_REQUIRED", 0))
    except (TypeError, ValueError):
        min_history_required = 0

    lookback_bars = max(1, lookback_bars)
    min_history_required = max(0, min_history_required)
    required_history_bars = max(lookback_bars, min_history_required)
    return lookback_bars, required_history_bars


def _binning_to_minutes(binning: str) -> int:
    mapping = {
        "1m": 1,
        "5m": 5,
        "15m": 15,
        "1h": 60,
        "1d": 1440,
    }
    try:
        return mapping[binning.strip().lower()]
    except KeyError as exc:
        raise ValueError(f"Unsupported binning: {binning}") from exc


def _history_warmup_bars(penguin_classes: List) -> int:
    warmup_bars = 0
    for penguin_class in penguin_classes:
        _, required_history_bars = _penguin_history_requirements(penguin_class)
        warmup_bars = max(warmup_bars, required_history_bars)
    return warmup_bars


def prepare_training_context(
    symbols: List[str],
    start_datetime: datetime,
    end_datetime: datetime,
    binning: str,
    penguin_classes: List,
) -> tuple[List[str], List[datetime], List[datetime], str]:
    """Load the data context needed by the standalone training script."""
    if start_datetime.tzinfo is None:
        start_datetime = start_datetime.replace(tzinfo=timezone.utc)
    if end_datetime.tzinfo is None:
        end_datetime = end_datetime.replace(tzinfo=timezone.utc)

    start_datetime_utc = start_datetime.astimezone(timezone.utc)
    end_datetime_utc = end_datetime.astimezone(timezone.utc)

    warmup_bars = _history_warmup_bars(penguin_classes)
    warmup_minutes = _binning_to_minutes(binning)
    warmup_start_datetime_utc = start_datetime_utc - timedelta(minutes=warmup_bars * warmup_minutes)

    restricted_sets = []
    all_restricted = True
    for penguin_class in penguin_classes:
        traded = getattr(penguin_class, "TRADED_SYMBOLS", None)
        if traded is None:
            all_restricted = False
            break

        restricted_sets.append(set(traded))

    if all_restricted and restricted_sets:
        requested_symbols = sorted(set().union(*restricted_sets).intersection(set(symbols)))
        if requested_symbols:
            symbols = requested_symbols

    loader = DataLoader()
    try:
        data, sparse_warning = loader.load_bars(
            symbols,
            warmup_start_datetime_utc,
            end_datetime_utc,
            binning,
            enable_data_quality_checks=True,
        )
        if sparse_warning:
            print(sparse_warning)
        quality_report_text = loader.get_quality_report_text()
    except Exception as e:
        print(f"Error loading data: {e}")
        print("Make sure APCA_API_KEY_ID and APCA_API_SECRET_KEY are set.")
        sys.exit(1)

    valid_symbols, stale_symbols = loader.detect_stale_data(data)
    print(f"  Valid symbols: {len(valid_symbols)}")
    if stale_symbols:
        print(f"  Stale symbols ({len(stale_symbols)}): {', '.join(stale_symbols)}")

    if not valid_symbols:
        print("No valid symbols to trade!")
        sys.exit(1)

    all_timestamps = set()
    for symbol_data in data.values():
        all_timestamps.update(symbol_data.keys())

    sorted_timestamps = sorted(all_timestamps)
    print(f"\n  Total bars across all symbols: {len(sorted_timestamps)}")
    tradeable_timestamps = [timestamp for timestamp in sorted_timestamps if timestamp >= start_datetime_utc]
    print(f"  Tradeable bars from configured start: {len(tradeable_timestamps)}")

    return valid_symbols, sorted_timestamps, tradeable_timestamps, quality_report_text


def _train_trainable_penguins(
    trainable_strategy_classes,
    symbols,
    tradeable_timestamps,
    binning,
    initial_capital,
    transaction_cost,
):
    rng = random.Random(TRAINING_RANDOM_SEED)
    np_rng = np.random.default_rng(TRAINING_RANDOM_SEED)
    trained_parameters = {}
    log_lines = []
    parameter_history = []
    pareto_history = {}

    header = (
        f"Step 3b: Training {len(trainable_strategy_classes)} trainable strategy(ies) "
        f"for {TRAINING_ITERATIONS} round(s) on {TRAINING_SUBSET_MONTHS} month(s) x {TRAINING_SUBSET_STOCKS} stock(s)..."
    )
    log_lines.append(header)
    log_lines.append("TRAINING CONFIGURATION")
    log_lines.append(f"  Relative To:       {TRAINING_RELATIVE_TO}")
    log_lines.append(f"  Training Steps:    {TRAINING_ITERATIONS}")
    log_lines.append(f"  Training Sample:   {TRAINING_SUBSET_STOCKS} stocks x {TRAINING_SUBSET_MONTHS} month(s)")
    log_lines.append(f"  Training Cost:     ${TRAINING_TRANSACTION_COST:.2f}")
    log_lines.append(f"  Training Seed:     {TRAINING_RANDOM_SEED}")
    log_lines.append("=" * 80)
    log_lines.append("  Resampling cadence: one fresh stock subset and one fresh time window per trial")
    log_lines.append("  Parameter search: random warm-up followed by Bayesian expected improvement")
    log_lines.append(f"  Training window length: {TRAINING_SUBSET_MONTHS} month(s) per trial")
    log_lines.append(f"  Training stock subset size: {TRAINING_SUBSET_STOCKS} symbol(s) per trial")

    for strategy_class in trainable_strategy_classes:
        best_metrics = None
        best_score = None
        best_params = {}
        initial_params = {}
        previous_trial_params = None
        completed_trials = []
        pareto_history[strategy_class.__name__] = []

        baseline_instance = strategy_class()
        if hasattr(baseline_instance, "params"):
            try:
                best_params = asdict(baseline_instance.params)
            except Exception:
                best_params = dict(getattr(baseline_instance.params, "__dict__", {}))
        initial_params = dict(best_params)

        strategy_header = f"  Optimizing {strategy_class.__name__}"
        log_lines.append("")
        log_lines.append(strategy_header)
        trial_iterator = tqdm(range(1, TRAINING_ITERATIONS + 1), desc=strategy_class.__name__, leave=False)
        for trial_number in trial_iterator:
            benchmark_symbol = _training_benchmark_symbol(TRAINING_RELATIVE_TO)
            trial_symbols = _training_symbol_subset(symbols, TRAINING_SUBSET_STOCKS, benchmark_symbol, rng)
            trial_timestamps = _training_window_subset(tradeable_timestamps, TRAINING_SUBSET_MONTHS, rng)

            if not trial_symbols or not trial_timestamps:
                log_lines.append(f"    Trial {trial_number:03d}: skipped (no subset available)")
                trial_iterator.set_postfix_str("skipped empty subset")
                parameter_history.append({"strategy": strategy_class.__name__, "trial": trial_number, "status": "skipped"})
                continue

            params, proposal_source = _suggest_bayesian_trainable_params(
                strategy_class=strategy_class,
                completed_trials=completed_trials,
                rng=rng,
                np_rng=np_rng,
            )
            candidate = strategy_class(**params)
            trial_window_start = trial_timestamps[0]
            trial_window_end = trial_timestamps[-1]
            selected_month_list = sorted({timestamp.astimezone(timezone.utc).strftime("%Y-%m") for timestamp in trial_timestamps})
            selected_months = ", ".join(selected_month_list)
            selected_symbols = _format_training_symbols(trial_symbols)
            param_changes = _format_param_changes(params, previous_trial_params)

            with open(os.devnull, "w", encoding="utf-8") as devnull, redirect_stdout(devnull), redirect_stderr(devnull):
                results, _, _, _, _, _ = run_backtest(
                    symbols=trial_symbols,
                    start_datetime=trial_window_start,
                    end_datetime=trial_window_end,
                    binning=binning,
                    initial_capital=initial_capital,
                    transaction_cost=TRAINING_TRANSACTION_COST,
                    penguin_classes=[candidate, SP500],
                    training_step_allowed=False,
                )

            candidate_metrics = results[candidate.name][1]
            benchmark_metrics = results[SP500().name][1]
            profit_amount = float(candidate_metrics.get("total_return", 0.0))
            benchmark_profit_amount = float(benchmark_metrics.get("total_return", 0.0))
            relative_profit_amount = _training_profit_amount(candidate_metrics, benchmark_metrics, TRAINING_RELATIVE_TO)
            score = _score_training_candidate(candidate_metrics, benchmark_metrics, TRAINING_TRANSACTION_COST, TRAINING_RELATIVE_TO)
            objective_value = _objective_from_score(score)
            final_value = float(candidate_metrics.get("final_value", 0.0))
            buy_trades = int(candidate_metrics.get("buy_trades", 0))

            if buy_trades > 0 and (best_score is None or score > best_score):
                best_score = score
                best_metrics = candidate_metrics
                best_params = params

            log_lines.append(
                f"    Trial {trial_number:03d}: window={_format_training_timestamp(trial_window_start)}"
                f" -> {_format_training_timestamp(trial_window_end)}, months=[{selected_months}],"
                f" symbols=[{selected_symbols}], proposal={proposal_source}"
            )
            log_lines.append(f"      params={_format_trainable_params(params)}")
            log_lines.append(f"      change_vs_previous={param_changes}")
            log_lines.append(
                f"      relative_profit=${relative_profit_amount:,.2f}, absolute_profit=${profit_amount:,.2f}, buys={buy_trades}, score={score}, objective={objective_value:,.2f}"
            )
            trial_iterator.set_postfix_str(f"profit={relative_profit_amount:.2f}, buys={buy_trades}")
            pareto_history[strategy_class.__name__].append(
                {
                    "trial": trial_number,
                    "buy_trades": int(candidate_metrics.get("buy_trades", 0)),
                    "total_trades": int(candidate_metrics.get("total_trades", 0)),
                    "profit_amount": profit_amount,
                    "benchmark_profit_amount": benchmark_profit_amount,
                    "relative_profit_amount": relative_profit_amount,
                    "relative_to": TRAINING_RELATIVE_TO,
                    "final_value": final_value,
                    "score": list(score),
                    "status": "completed",
                }
            )
            parameter_history.append(
                {
                    "strategy": strategy_class.__name__,
                    "trial": trial_number,
                    "status": "completed",
                    "proposal_source": proposal_source,
                    "window_start": trial_window_start,
                    "window_end": trial_window_end,
                    "selected_months": selected_month_list,
                    "selected_symbols": trial_symbols,
                    "params": params,
                    "param_changes_vs_previous": param_changes,
                    "profit_amount": profit_amount,
                    "benchmark_profit_amount": benchmark_profit_amount,
                    "relative_profit_amount": relative_profit_amount,
                    "relative_to": TRAINING_RELATIVE_TO,
                    "final_value": final_value,
                    "objective_value": objective_value,
                    "relative_value": float(score[0]),
                    "relative_net_gain": float(score[0]),
                    "buy_trades": buy_trades,
                    "total_trades": int(candidate_metrics.get("total_trades", 0)),
                    "score": list(score),
                }
            )
            completed_trials.append({"status": "completed", "params": dict(params), "objective_value": objective_value})
            previous_trial_params = params

        trained_parameters[str(strategy_class.__name__)] = {
            "initial_params": initial_params,
            "best_params": best_params,
            "best_metrics": best_metrics,
            "best_score": list(best_score) if best_score is not None else None,
        }
        if best_score is None:
            log_lines.append(
                f"  Best {strategy_class.__name__}: no qualifying trial with buys, params={_format_trainable_params(best_params)}"
            )
        else:
            log_lines.append(
                f"  Best {strategy_class.__name__}: relative_net=${best_score[0]:,.2f}, trades={(best_metrics or {}).get('total_trades', 0)}, params={_format_trainable_params(best_params)}"
            )

    return trained_parameters, log_lines, parameter_history, pareto_history


def _training_pareto_output_path(artifacts_dir: Path | None = None) -> Path:
    output_dir = (
        Path(artifacts_dir).parent
        if artifacts_dir is not None
        else Path(__file__).resolve().parent.parent / "run_test"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / TRAINING_PARETO_FILENAME


def run_training_step(
    trainable_strategy_classes,
    symbols,
    tradeable_timestamps,
    binning,
    initial_capital,
    artifacts_dir: Path | None = None,
):
    if not trainable_strategy_classes:
        print("No trainable penguins are configured.")
        return {}

    if artifacts_dir is None:
        artifacts_dir = Path(__file__).resolve().parent.parent / "run_test" / "artifacts"

    _print_training_configuration()
    training_start = datetime.now(timezone.utc)
    trained_parameters, training_log_lines, training_parameter_history, training_pareto_history = _train_trainable_penguins(
        trainable_strategy_classes=trainable_strategy_classes,
        symbols=symbols,
        tradeable_timestamps=tradeable_timestamps,
        binning=binning,
        initial_capital=initial_capital,
        transaction_cost=TRAINING_TRANSACTION_COST,
    )
    training_end = datetime.now(timezone.utc)
    training_elapsed = training_end - training_start
    total_seconds = int(training_elapsed.total_seconds())
    hrs, rem = divmod(total_seconds, 3600)
    mins, secs = divmod(rem, 60)
    training_duration_str = f"{hrs}:{mins:02d}:{secs:02d}"

    training_output_dir = artifacts_dir / "json"
    training_output_dir.mkdir(parents=True, exist_ok=True)
    benchmark_symbol = _training_benchmark_symbol(TRAINING_RELATIVE_TO)
    training_output_path = training_output_dir / TRAINING_RESULTS_FILENAME
    training_parameter_log_path = training_output_dir / TRAINING_PARAMETER_LOG_FILENAME
    training_parameter_delta_path = artifacts_dir / TRAINING_PARAMETER_DELTA_FILENAME
    training_log_path = artifacts_dir / TRAINING_LOG_FILENAME
    training_pareto_path = _training_pareto_output_path(artifacts_dir)

    with open(training_output_path, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "iterations": TRAINING_ITERATIONS,
                "subset_months": TRAINING_SUBSET_MONTHS,
                "subset_stocks": TRAINING_SUBSET_STOCKS,
                "relative_to": TRAINING_RELATIVE_TO,
                "benchmark_symbol": benchmark_symbol,
                "training_transaction_cost": TRAINING_TRANSACTION_COST,
                "trainable_strategies": trained_parameters,
            },
            handle,
            indent=2,
            default=str,
        )

    with open(training_parameter_log_path, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "iterations": TRAINING_ITERATIONS,
                "subset_months": TRAINING_SUBSET_MONTHS,
                "subset_stocks": TRAINING_SUBSET_STOCKS,
                "relative_to": TRAINING_RELATIVE_TO,
                "benchmark_symbol": benchmark_symbol,
                "training_transaction_cost": TRAINING_TRANSACTION_COST,
                "resampling_cadence": "one fresh stock subset and one fresh time window per trial",
                "trial_history": training_parameter_history,
            },
            handle,
            indent=2,
            default=str,
        )

    with open(training_parameter_delta_path, "w", encoding="utf-8") as handle:
        handle.write(_format_trainable_parameter_delta_report(trained_parameters))

    with open(training_log_path, "w", encoding="utf-8") as handle:
        handle.write(
            "\n".join(
                [
                    f"Training completed at {datetime.now(timezone.utc).isoformat()}",
                    f"Total training time: {training_duration_str} (H:MM:SS)",
                    f"Relative to: {TRAINING_RELATIVE_TO}",
                    f"Benchmark symbol: {benchmark_symbol}",
                    f"Training transaction cost: {TRAINING_TRANSACTION_COST}",
                    f"Parameter log: {TRAINING_PARAMETER_LOG_FILENAME}",
                    f"Parameter delta report: {TRAINING_PARAMETER_DELTA_FILENAME}",
                    "",
                    *training_log_lines,
                ]
            )
            + "\n"
        )

    if PLOT_PARETO:
        create_training_pareto_pdf(
            training_pareto_history,
            training_parameter_history,
            trained_parameters,
            training_pareto_path,
            relative_to=TRAINING_RELATIVE_TO,
            transaction_cost=TRAINING_TRANSACTION_COST,
        )

    print(f"\nSaved training parameters to {training_output_path}")
    print(f"Saved trainable parameter log to {training_parameter_log_path}")
    print(f"Saved trainable parameter delta report to {training_parameter_delta_path}")
    print(f"Saved training log to {training_log_path}")
    if PLOT_PARETO:
        print(f"Saved training Pareto PDF to {training_pareto_path}")
    print(f"Total training time: {training_duration_str} (H:MM:SS)")
    print("\nTrainable values selected at the end:")
    for strategy_name, training_result in trained_parameters.items():
        print(f"  {strategy_name}: {_format_trainable_params(training_result.get('best_params', {}))}")

    return trained_parameters


def main() -> None:
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass

    try:
        start_dt = parse_datetime_string(TRAINING_START_DATE)
        end_dt = parse_datetime_string(TRAINING_STOP_DATE)
    except ValueError as exc:
        print(f"Error parsing config dates: {exc}")
        print(f"  TRAINING_START_DATE: {TRAINING_START_DATE}")
        print(f"  TRAINING_STOP_DATE: {TRAINING_STOP_DATE}")
        sys.exit(1)

    print("\n" + "=" * 80)
    print("PENGUIN CAPITALIST - TRAINABLE PENGUIN TRAINING")
    print("=" * 80)

    base_dir = Path(__file__).resolve().parent.parent
    run_dir = base_dir / "run_test"
    run_artifacts_dir = run_dir / "artifacts"
    run_artifacts_dir.mkdir(parents=True, exist_ok=True)

    print("Step 1: Preparing training data...")
    valid_symbols, _sorted_timestamps, tradeable_timestamps, quality_report_text = prepare_training_context(
        symbols=SYMBOLS,
        start_datetime=start_dt,
        end_datetime=end_dt,
        binning=BINNING,
        penguin_classes=TRAINABLE_PENGUINS,
    )

    if quality_report_text:
        warnings_path = run_artifacts_dir / "consistency_warnings.txt"
        with open(warnings_path, "w", encoding="utf-8") as handle:
            handle.write(quality_report_text)
            handle.write("\n")

    active_trainables = [strategy for strategy in TRAINABLE_PENGUINS if getattr(strategy, "TRAINABLE", False)]
    if not active_trainables:
        print("No trainable penguins are configured.")
        sys.exit(1)

    print(
        f"\nStep 2: Training {len(active_trainables)} trainable strategy(ies) "
        f"for the configured optimization rounds..."
    )
    run_training_step(
        trainable_strategy_classes=active_trainables,
        symbols=valid_symbols,
        tradeable_timestamps=tradeable_timestamps,
        binning=BINNING,
        initial_capital=INITIAL_CAPITAL,
        transaction_cost=TRAINING_TRANSACTION_COST,
        artifacts_dir=run_artifacts_dir,
    )


if __name__ == "__main__":
    main()
