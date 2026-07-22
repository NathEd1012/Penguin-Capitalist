"""Main entry point for historical backtesting simulation."""
import json
from contextlib import redirect_stderr, redirect_stdout
import os
import random
import shutil
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Tuple, List
from collections import defaultdict
import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

mpl_config_dir = Path(os.environ.get("MPLCONFIGDIR", "/private/tmp/penguin_mplconfig"))
xdg_cache_dir = Path(os.environ.get("XDG_CACHE_HOME", "/private/tmp/penguin_xdg_cache"))
try:
    mpl_config_dir.mkdir(parents=True, exist_ok=True)
    xdg_cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_config_dir))
    os.environ.setdefault("XDG_CACHE_HOME", str(xdg_cache_dir))
    os.environ.setdefault("MPLBACKEND", "Agg")
except Exception:
    pass

from tqdm import tqdm
from backtest.portfolio import Portfolio
from backtest.data_loader import DataLoader
from backtest.evaluator import Evaluator
from scripts.data_fixes.synthetic_spread_model import SyntheticSpreadModel
from penguins import SP500
from config import (
    SYMBOLS,
    ACTIVE_SYMBOL_LIST,
    INITIAL_CAPITAL,
    EXEC_TRANSACTION_COST,
    TRAINING_TRANSACTION_COST,
    START_DATE,
    STOP_DATE,
    BINNING,
    ACTIVE_PENGUINS,
    SAVE_TO_RUN_OLD,
    TRAINING_STEP_ENABLED,
    TRAINING_ITERATIONS,
    TRAINING_SUBSET_MONTHS,
    TRAINING_SUBSET_STOCKS,
    TRAINING_RELATIVE_TO,
    TRAINING_RANDOM_SEED,
    TRAINABLE_PENGUINS,
    PLOT_PARETO,
    TRAINING_RESULTS_FILENAME,
    TRAINING_LOG_FILENAME,
    TRAINING_PARAMETER_LOG_FILENAME,
    TRAINING_PARAMETER_DELTA_FILENAME,
    TRAINING_PARETO_FILENAME,
)
from scripts.plotting import create_training_pareto_pdf


def percent_progress(iterable, desc: str):
    total = len(iterable)
    if total == 0:
        return

    progress = tqdm(total=total, desc=desc)
    last_percent = -1

    try:
        for index, item in enumerate(iterable, start=1):
            percent = (index * 100) // total
            if percent != last_percent:
                progress.update(index - progress.n)
                last_percent = percent
            yield index - 1, item

        if progress.n < total:
            progress.update(total - progress.n)
    finally:
        progress.close()


def parse_datetime_string(dt_str: str) -> datetime:
    """
    Parse datetime from config format string.
    
    Accepts:
    - ISO format: "2026-02-20 14:30:00"
    - With timezone: "2026-02-20 14:30:00+01:00"
    - Special keyword: "TODAY" (resolves to yesterday at 23:50:00 UTC to avoid recent SIP data restrictions)
    
    Assumes UTC if no timezone specified.
    """
    # If caller already passed a datetime, normalize and return it
    if isinstance(dt_str, datetime):
        dt = dt_str
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    dt_str = dt_str.strip()
    
    # Handle special keyword "TODAY"
    if dt_str.upper() == "TODAY":
        # Use yesterday at 23:50 UTC to avoid recent SIP data restrictions
        yesterday = datetime.now(timezone.utc).replace(hour=23, minute=50, second=0, microsecond=0) - timedelta(days=1)
        return yesterday
    
    # Try parsing with timezone first
    for fmt in ["%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S"]:
        try:
            dt = datetime.strptime(dt_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    
    raise ValueError(f"Cannot parse datetime: {dt_str}")


def get_next_run_number(run_old_dir: Path) -> int:
    """Get the next run number for archives (e.g., run1, run2, run3, ...)."""
    current_date = datetime.now().strftime("%y%m%d")
    date_dir = run_old_dir / current_date
    date_dir.mkdir(parents=True, exist_ok=True)
    
    # Find all existing run folders
    existing_runs = [d for d in date_dir.iterdir() if d.is_dir() and d.name.startswith("run")]
    
    if not existing_runs:
        return 1
    
    # Extract numbers and find max
    run_numbers = []
    for run_dir in existing_runs:
        try:
            num = int(run_dir.name[3:])  # Extract number from "runX"
            run_numbers.append(num)
        except ValueError:
            continue
    
    return max(run_numbers) + 1 if run_numbers else 1


def _training_window_subset(sorted_timestamps: List[datetime], months: int, rng: random.Random) -> List[datetime]:
    if not sorted_timestamps:
        return []

    window_length = timedelta(days=max(1, months) * 30)
    latest_start = sorted_timestamps[-1] - window_length
    eligible_starts = [timestamp for timestamp in sorted_timestamps if timestamp <= latest_start]
    start_timestamp = rng.choice(eligible_starts) if eligible_starts else sorted_timestamps[0]
    end_timestamp = start_timestamp + window_length
    return [timestamp for timestamp in sorted_timestamps if start_timestamp <= timestamp <= end_timestamp]


def _training_symbol_subset(symbols: List[str], target_count: int, benchmark_symbol: str, rng: random.Random) -> List[str]:
    pool = list(dict.fromkeys(symbols))
    if benchmark_symbol in pool:
        pool.remove(benchmark_symbol)

    sample_size = min(len(pool), max(0, target_count - 1))
    subset = rng.sample(pool, sample_size) if sample_size > 0 else []
    if benchmark_symbol not in subset:
        subset.append(benchmark_symbol)
    return sorted(subset)


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


def _training_benchmark_symbol(relative_to: int | str) -> str:
    return "SPY" if relative_to == 0 else str(relative_to)


def _sample_trainable_params(strategy_class, rng: random.Random) -> Dict[str, int | float]:
    strategy_name = strategy_class.__name__
    if strategy_name.endswith("OG_TP1") or strategy_name.endswith("OG_TP1_Manual") or strategy_name.endswith("TrainablePenguin1") or strategy_name.endswith("TrainablePenguin1_Manual"):
        buy_rsi = rng.uniform(18.0, 42.0)
        sell_rsi = rng.uniform(max(buy_rsi + 8.0, 55.0), 88.0)
        return {
            "rsi_period": rng.randint(7, 28),
            "buy_rsi": round(buy_rsi, 2),
            "sell_rsi": round(sell_rsi, 2),
            "adx_period": rng.randint(7, 28),
            "adx_threshold": round(rng.uniform(10.0, 40.0), 2),
            "max_cash_fraction_per_trade": round(rng.uniform(0.02, 0.20), 4),
            "stop_loss_pct": round(rng.uniform(0.01, 0.10), 4),
            "take_profit_pct": round(rng.uniform(0.02, 0.20), 4),
            "cooldown_bars": rng.randint(0, 30),
            "strength_cap": round(rng.uniform(1.0, 2.0), 2),
        }
    if strategy_name.endswith("OG_TP2") or strategy_name.endswith("OG_TP2_Manual") or strategy_name.endswith("TrainablePenguin2") or strategy_name.endswith("TrainablePenguin2_Manual"):
        return {
            "bb_period": rng.randint(10, 40),
            "bb_stddev": round(rng.uniform(1.0, 3.5), 2),
            "adx_period": rng.randint(7, 28),
            "adx_threshold": round(rng.uniform(10.0, 40.0), 2),
            "max_cash_fraction_per_trade": round(rng.uniform(0.02, 0.20), 4),
            "stop_loss_pct": round(rng.uniform(0.01, 0.10), 4),
            "take_profit_pct": round(rng.uniform(0.02, 0.20), 4),
            "cooldown_bars": rng.randint(0, 30),
            "strength_cap": round(rng.uniform(1.0, 2.0), 2),
        }
    if strategy_name.endswith("OG_TP3") or strategy_name.endswith("OG_TP3_Manual") or strategy_name.endswith("TrainablePenguin3") or strategy_name.endswith("TrainablePenguin3_Manual"):
        return {
            "bb_period": rng.randint(10, 40),
            "bb_stddev": round(rng.uniform(1.0, 3.5), 2),
            "adx_period": rng.randint(7, 28),
            "adx_threshold": round(rng.uniform(10.0, 40.0), 2),
            "max_cash_fraction_per_trade": round(rng.uniform(0.02, 0.20), 4),
            "stop_loss_pct": round(rng.uniform(0.01, 0.10), 4),
            "take_profit_pct": round(rng.uniform(0.02, 0.20), 4),
            "cooldown_bars": rng.randint(0, 30),
            "strength_cap": round(rng.uniform(1.0, 2.0), 2),
        }
    if strategy_name.endswith("OG_TP4") or strategy_name.endswith("OG_TP4_Manual") or strategy_name.endswith("TrainablePenguin4") or strategy_name.endswith("TrainablePenguin4_Manual"):
        buy_rsi = rng.uniform(18.0, 42.0)
        sell_rsi = rng.uniform(max(buy_rsi + 8.0, 55.0), 88.0)
        return {
            "rsi_period": rng.randint(7, 28),
            "buy_rsi": round(buy_rsi, 2),
            "sell_rsi": round(sell_rsi, 2),
            "max_cash_fraction_per_trade": round(rng.uniform(0.02, 0.20), 4),
            "stop_loss_pct": round(rng.uniform(0.01, 0.10), 4),
            "take_profit_pct": round(rng.uniform(0.02, 0.20), 4),
            "cooldown_bars": rng.randint(0, 30),
            "strength_cap": round(rng.uniform(1.0, 2.0), 2),
        }
    raise ValueError(f"No parameter sampler is defined for {strategy_name}")


def _replace_trainable_penguin_params(penguin, params: Dict[str, int | float]):
    try:
        updated_penguin = penguin.__class__(name=penguin.name, **params)
        if hasattr(penguin, "record_history"):
            updated_penguin.record_history = bool(getattr(penguin, "record_history"))
        return updated_penguin
    except Exception:
        if hasattr(penguin, "params"):
            for key, value in params.items():
                setattr(penguin.params, key, value)
        return penguin


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


def _format_trainable_params(params: Dict[str, int | float]) -> str:
    if not params:
        return "<no parameters>"
    return ", ".join(f"{key}={value}" for key, value in sorted(params.items()))


def _format_training_timestamp(timestamp: datetime) -> str:
    return timestamp.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _format_training_months(trial_timestamps: List[datetime]) -> str:
    months = sorted({timestamp.astimezone(timezone.utc).strftime("%Y-%m") for timestamp in trial_timestamps})
    return ", ".join(months) if months else "<none>"


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

    for strategy_name in sorted(trained_parameters):
        strategy_result = trained_parameters.get(strategy_name, {})
        initial_params = dict(strategy_result.get("initial_params") or {})
        final_params = dict(strategy_result.get("best_params") or {})

        lines.append("")
        lines.append(f"{strategy_name}:")
        param_keys = sorted(set(initial_params) | set(final_params))
        if not param_keys:
            lines.append("  <no parameters>")
            continue

        for key in param_keys:
            initial_value = initial_params.get(key, "<missing>")
            final_value = final_params.get(key, "<missing>")
            lines.append(f"  {key}: {initial_value} -> {final_value}")

    return "\n".join(lines) + "\n"


def _train_trainable_penguins(
    trainable_strategy_classes: List,
    symbols: List[str],
    tradeable_timestamps: List[datetime],
    binning: str,
    initial_capital: float,
    transaction_cost: float,
) -> Tuple[Dict[str, Dict[str, object]], List[str], List[Dict[str, object]], Dict[str, List[Dict[str, object]]]]:
    rng = random.Random(TRAINING_RANDOM_SEED)
    trained_parameters: Dict[str, Dict[str, object]] = {}
    log_lines: List[str] = []
    parameter_history: List[Dict[str, object]] = []
    pareto_history: Dict[str, List[Dict[str, object]]] = {}

    header = (
        f"Step 3b: Training {len(trainable_strategy_classes)} trainable strategy(ies) "
        f"for {TRAINING_ITERATIONS} round(s) on {TRAINING_SUBSET_MONTHS} month(s) x {TRAINING_SUBSET_STOCKS} stock(s)..."
    )
    log_lines.append(header)
    log_lines.append("  Resampling cadence: one fresh stock subset and one fresh time window per trial")
    log_lines.append(f"  Training window length: {TRAINING_SUBSET_MONTHS} month(s) per trial")
    log_lines.append(f"  Training stock subset size: {TRAINING_SUBSET_STOCKS} symbol(s) per trial")

    for strategy_class in trainable_strategy_classes:
        best_metrics = None
        best_score = None
        best_params: Dict[str, int | float] = {}
        initial_params: Dict[str, int | float] = {}
        previous_trial_params: Dict[str, int | float] | None = None
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
        trial_iterator = tqdm(
            range(1, TRAINING_ITERATIONS + 1),
            desc=strategy_class.__name__,
            leave=False,
        )
        for trial_number in trial_iterator:
            benchmark_symbol = _training_benchmark_symbol(TRAINING_RELATIVE_TO)
            trial_symbols = _training_symbol_subset(symbols, TRAINING_SUBSET_STOCKS, benchmark_symbol, rng)
            trial_timestamps = _training_window_subset(tradeable_timestamps, TRAINING_SUBSET_MONTHS, rng)

            if not trial_symbols or not trial_timestamps:
                skipped_line = f"    Trial {trial_number:03d}: skipped (no subset available)"
                log_lines.append(skipped_line)
                trial_iterator.set_postfix_str("skipped empty subset")
                parameter_history.append(
                    {
                        "strategy": strategy_class.__name__,
                        "trial": trial_number,
                        "status": "skipped",
                    }
                )
                continue

            params = _sample_trainable_params(strategy_class, rng)
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
                    transaction_cost=transaction_cost,
                    penguin_classes=[candidate, SP500],
                    enable_training_step=False,
                )

            candidate_metrics = results[candidate.name][1]
            benchmark_metrics = results[SP500().name][1]
            profit_amount = float(candidate_metrics.get("total_return", 0.0))
            benchmark_profit_amount = float(benchmark_metrics.get("total_return", 0.0))
            relative_profit_amount = _training_profit_amount(candidate_metrics, benchmark_metrics, TRAINING_RELATIVE_TO)
            score = _score_training_candidate(candidate_metrics, benchmark_metrics, transaction_cost, TRAINING_RELATIVE_TO)
            final_value = float(candidate_metrics.get("final_value", 0.0))

            if best_score is None or score > best_score:
                best_score = score
                best_metrics = candidate_metrics
                best_params = params

            selection_line = (
                f"    Trial {trial_number:03d}: window={_format_training_timestamp(trial_window_start)}"
                f" -> {_format_training_timestamp(trial_window_end)}, months=[{selected_months}],"
                f" symbols=[{selected_symbols}]"
            )
            params_line = f"      params={_format_trainable_params(params)}"
            change_line = f"      change_vs_previous={param_changes}"
            trial_line = (
                f"      relative_profit=${relative_profit_amount:,.2f}, absolute_profit=${profit_amount:,.2f}, buys={candidate_metrics.get('buy_trades', 0)}, score={score}"
            )
            trial_iterator.set_postfix_str(
                f"profit={relative_profit_amount:.2f}, buys={candidate_metrics.get('buy_trades', 0)}"
            )
            log_lines.append(selection_line)
            log_lines.append(params_line)
            log_lines.append(change_line)
            log_lines.append(trial_line)
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
                    "relative_value": float(score[0]),
                    "relative_net_gain": float(score[0]),
                    "buy_trades": int(candidate_metrics.get("buy_trades", 0)),
                    "total_trades": int(candidate_metrics.get("total_trades", 0)),
                    "score": list(score),
                }
            )
            previous_trial_params = params

        trained_parameters[strategy_class.__name__] = {
            "initial_params": initial_params,
            "best_params": best_params,
            "best_metrics": best_metrics,
            "best_score": list(best_score) if best_score is not None else None,
        }
        best_line = (
            f"  Best {strategy_class.__name__}: relative_net=${(best_score[0] if best_score else 0.0):,.2f}, "
            f"trades={(best_metrics or {}).get('total_trades', 0)}, params={_format_trainable_params(best_params)}"
        )
        log_lines.append(best_line)

    return trained_parameters, log_lines, parameter_history, pareto_history


def run_backtest(
    symbols: List[str],
    start_datetime: datetime,
    end_datetime: datetime,
    binning: str,
    initial_capital: float,
    transaction_cost: float,
    penguin_classes: List,
    enable_training_step: bool = False,
    artifacts_dir: Path | None = None,
) -> Tuple[
    Dict[str, Tuple[Portfolio, Dict]],
    Dict,
    List[datetime],
    Dict[str, Dict],
    Dict[str, List[Tuple[datetime, float]]],
    str,
]:
    """
    Run historical backtest.
    
    Args:
        symbols: List of symbols to trade
        start_datetime: Start datetime (UTC)
        end_datetime: End datetime (UTC)
        binning: Timeframe string ("1m", "5m", "15m", "1h", "1d")
        initial_capital: Initial capital
        transaction_cost: Transaction cost per trade
        penguin_classes: List of penguin strategy classes
    
    Returns:
        Dict[penguin_name] = (portfolio, metrics)
    """
    
    # Ensure both datetimes are UTC
    if start_datetime.tzinfo is None:
        start_datetime = start_datetime.replace(tzinfo=timezone.utc)
    if end_datetime.tzinfo is None:
        end_datetime = end_datetime.replace(tzinfo=timezone.utc)
    
    # Convert to UTC if needed
    start_datetime_utc = start_datetime.astimezone(timezone.utc)
    end_datetime_utc = end_datetime.astimezone(timezone.utc)

    warmup_bars = _history_warmup_bars(penguin_classes)
    warmup_minutes = _binning_to_minutes(binning)
    warmup_start_datetime_utc = start_datetime_utc - timedelta(minutes=warmup_bars * warmup_minutes)
    
    # Determine required symbols from active penguins when possible.
    # If every active penguin declares TRADED_SYMBOLS, we only load that union.
    # If at least one penguin is unrestricted, keep the full configured symbol list.
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

    print(f"\n{'='*80}")
    print(f"BACKTEST CONFIGURATION")
    print(f"{'='*80}")
    print(f"Start Time (UTC):  {start_datetime_utc}")
    print(f"End Time (UTC):    {end_datetime_utc}")
    print(f"Binning:           {binning}")
    print(f"\nPORTFOLIO CONFIGURATION")
    print(f"Initial Capital:   ${initial_capital:,.2f}")
    print(f"Transaction Cost:  ${transaction_cost:.2f}")
    print(f"Symbol List:       {ACTIVE_SYMBOL_LIST}")
    print(f"Symbols:           {len(symbols)}")
    if enable_training_step:
        print(f"\nTRAINING CONFIGURATION")
        print(f"Relative To:       {TRAINING_RELATIVE_TO}")
        print(f"Training Steps:    {TRAINING_ITERATIONS}")
        print(f"Training Sample:   {TRAINING_SUBSET_STOCKS} stocks x {TRAINING_SUBSET_MONTHS} month(s)")
        print(f"Training Cost:     ${TRAINING_TRANSACTION_COST:.2f}")
        print(f"Training Seed:     {TRAINING_RANDOM_SEED}")
    print(f"{'='*80}\n")
    
    # Load data
    print("Step 1: Loading historical data from Alpaca...")
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
        if quality_report_text:
            if artifacts_dir is not None:
                warnings_path = artifacts_dir / "consistency_warnings.txt"
                with open(warnings_path, "w") as f:
                    f.write(quality_report_text)
                    f.write("\n")
    except Exception as e:
        print(f"Error loading data: {e}")
        print("Make sure APCA_API_KEY_ID and APCA_API_SECRET_KEY are set.")
        sys.exit(1)
    
    ################################ STEP 2 ################################

    # Detect stale data
    print("\nStep 2: Detecting stale data...")
    valid_symbols, stale_symbols = loader.detect_stale_data(data)
    
    print(f"  Valid symbols: {len(valid_symbols)}")
    if stale_symbols:
        print(f"  Stale symbols ({len(stale_symbols)}): {', '.join(stale_symbols)}")
    
    symbols = valid_symbols
    if not symbols:
        print("No valid symbols to trade!")
        sys.exit(1)
    
    # Get sorted timestamps for all symbols
    all_timestamps = set()
    for symbol_data in data.values():
        all_timestamps.update(symbol_data.keys())
    
    sorted_timestamps = sorted(all_timestamps)
    print(f"\n  Total bars across all symbols: {len(sorted_timestamps)}")
    tradeable_timestamps = [timestamp for timestamp in sorted_timestamps if timestamp >= start_datetime_utc]
    print(f"  Tradeable bars from configured start: {len(tradeable_timestamps)}")
    
    symbol_close_series: Dict[str, List[Tuple[datetime, float]]] = {}
    # Initialize portfolios and penguins
    portfolios = {}
    penguins = {}
    
    # Initialize synthetic spread model for realistic bid/ask
    spread_model = SyntheticSpreadModel()
    trained_parameters: Dict[str, Dict[str, object]] = {}

    ################################ STEP 3 ################################


    print(f"\nStep 3: Initializing {len(penguin_classes)} strategies...")
    for penguin_spec in tqdm(penguin_classes, desc="Initializing strategies"):
        try:
            if isinstance(penguin_spec, type):
                penguin = penguin_spec()
            elif hasattr(penguin_spec, "decide"):
                penguin = penguin_spec
            else:
                penguin = penguin_spec()
            pen_name = penguin.name
            portfolios[pen_name] = Portfolio(initial_capital, transaction_cost)
            portfolios[pen_name].max_leverage = float(getattr(penguin, "MAX_LEVERAGE", 1.0))
            penguins[pen_name] = penguin
        except Exception as e:
            penguin_name = getattr(penguin_spec, "__name__", getattr(penguin_spec, "name", str(penguin_spec)))
            print(f"  ✗ {penguin_name}: {e}")

    if enable_training_step:
        active_trainables = []
        seen_trainable_classes = set()
        for penguin in penguins.values():
            penguin_class = penguin.__class__
            if penguin_class in set(TRAINABLE_PENGUINS) and penguin_class not in seen_trainable_classes:
                active_trainables.append(penguin_class)
                seen_trainable_classes.add(penguin_class)
        if active_trainables:
            training_start = datetime.now(timezone.utc)
            trained_parameters, training_log_lines, training_parameter_history, training_pareto_history = _train_trainable_penguins(
                trainable_strategy_classes=active_trainables,
                symbols=symbols,
                tradeable_timestamps=tradeable_timestamps,
                binning=binning,
                initial_capital=initial_capital,
                transaction_cost=TRAINING_TRANSACTION_COST,
            )
            training_end = datetime.now(timezone.utc)
            training_elapsed = training_end - training_start
            # Format elapsed as H:MM:SS
            total_seconds = int(training_elapsed.total_seconds())
            hrs, rem = divmod(total_seconds, 3600)
            mins, secs = divmod(rem, 60)
            training_duration_str = f"{hrs}:{mins:02d}:{secs:02d}"

            for penguin_name, penguin in list(penguins.items()):
                strategy_name = penguin.__class__.__name__
                if strategy_name in trained_parameters:
                    penguins[penguin_name] = _replace_trainable_penguin_params(
                        penguin,
                        trained_parameters[strategy_name]["best_params"],
                    )

            training_artifacts_dir = Path(artifacts_dir) if artifacts_dir is not None else Path(__file__).parent / "run_current" / "artifacts"
            training_output_dir = training_artifacts_dir / "json"
            training_output_dir.mkdir(parents=True, exist_ok=True)
            benchmark_symbol = _training_benchmark_symbol(TRAINING_RELATIVE_TO)
            training_output_path = training_output_dir / TRAINING_RESULTS_FILENAME
            training_parameter_log_path = training_output_dir / TRAINING_PARAMETER_LOG_FILENAME
            training_parameter_delta_path = training_artifacts_dir / TRAINING_PARAMETER_DELTA_FILENAME
            training_log_path = training_artifacts_dir / TRAINING_LOG_FILENAME
            training_pareto_path = training_artifacts_dir.parent / TRAINING_PARETO_FILENAME
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
                            f"Step 3b training completed at {datetime.now(timezone.utc).isoformat()}",
                            f"Total training time: {training_duration_str} (H:MM:SS)",
                            f"Iterations: {TRAINING_ITERATIONS}",
                            f"Subset months: {TRAINING_SUBSET_MONTHS}",
                            f"Subset stocks: {TRAINING_SUBSET_STOCKS}",
                            f"Relative to: {TRAINING_RELATIVE_TO}",
                            f"Benchmark symbol: {benchmark_symbol}",
                            f"Training transaction cost: {TRAINING_TRANSACTION_COST}",
                            f"Resampling cadence: one fresh stock subset and one fresh time window per trial",
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

    ################################ STEP 4 ################################


    # Run simulation
    print(f"\nStep 4: Running backtest ({len(sorted_timestamps)} bars)...\n")
    
    # Prepare price history for each symbol
    price_history = defaultdict(list)
    
    # Track trades by bar for detailed logging
    trades_by_bar = defaultdict(list)
    trade_bar_idx = -1
    
    for bar_idx, timestamp in percent_progress(sorted_timestamps, desc="Executing bars"):
        # Get current prices
        current_prices = {}
        for symbol in symbols:
            bar = data[symbol].get(timestamp)
            if bar and bar.get("data_quality", "OK") == "OK":
                current_prices[symbol] = bar['close']
        
        if not current_prices:
            continue
        
        # Update price history for each symbol
        for symbol in symbols:
            bar = data[symbol].get(timestamp)
            if bar is None:
                if symbol in price_history and price_history[symbol]:
                    # Keep last known price if data is missing entirely.
                    price_history[symbol].append(price_history[symbol][-1])
                else:
                    price_history[symbol].append(current_prices.get(symbol, 0))
            elif bar.get("data_quality", "OK") == "OK":
                price_history[symbol].append(bar['close'])
            else:
                # Quarantined bars are removed from the strategy-visible history.
                continue

        if timestamp < start_datetime_utc:
            continue

        trade_bar_idx += 1
        
        # Let each penguin make decisions
        quotes = {}
        for symbol in current_prices:
            bar = data[symbol][timestamp]
            bid, ask, _ = spread_model.get_bid_ask(
                mid_price=bar["close"],
                high=bar["high"],
                low=bar["low"],
                timestamp=timestamp,
                volume=bar.get("volume", 0),
                symbol=symbol,
            )
            quotes[symbol] = (bid, ask)

        for penguin_name, penguin in penguins.items():
            portfolio = portfolios[penguin_name]
            
            if hasattr(penguin, "set_current_timestamp"):
                penguin.set_current_timestamp(timestamp)

            if bar_idx == len(sorted_timestamps) - 1:
                continue

            lookback_bars, required_history_bars = _penguin_history_requirements(penguin)
            penguin_symbols = getattr(penguin, "TRADED_SYMBOLS", None)
            if penguin_symbols is not None:
                symbols_for_penguin = [s for s in symbols if s in penguin_symbols]
            else:
                symbols_for_penguin = symbols

            if hasattr(penguin, "decide_batch"):
                ready_symbols = [
                    symbol
                    for symbol in symbols_for_penguin
                    if symbol in quotes and len(price_history[symbol]) >= required_history_bars
                ]
                ready_quotes = {symbol: quotes[symbol] for symbol in ready_symbols}

                batch_orders = penguin.decide_batch(ready_symbols, ready_quotes, portfolio)
                for order_symbol, action, quantity in batch_orders:
                    if order_symbol not in ready_quotes or quantity <= 0:
                        continue

                    bid, ask = ready_quotes[order_symbol]
                    if action == "BUY":
                        if portfolio.buy(order_symbol, quantity, ask, timestamp):
                            trades_by_bar[trade_bar_idx].append(
                                f"  {penguin_name}: BUY {quantity} {order_symbol} @ ${ask:.2f}"
                            )
                    elif action == "SELL":
                        if portfolio.sell(order_symbol, quantity, bid, timestamp):
                            trades_by_bar[trade_bar_idx].append(
                                f"  {penguin_name}: SELL {quantity} {order_symbol} @ ${bid:.2f}"
                            )

                value = portfolio.get_total_value(current_prices)
                portfolio.add_value_snapshot(value)
                continue
            
            for symbol in symbols_for_penguin:
                if symbol not in current_prices:
                    continue
                
                # Pass only data-backed windows to strategies. No penguin may trade
                # until its configured lookback/minimum history is available.
                full_history = price_history[symbol]
                if len(full_history) < required_history_bars:
                    continue
                
                mid_prices = full_history[-lookback_bars:]
                bid, ask = quotes[symbol]
                
                try:
                    action, quantity = penguin.decide(
                        symbol,
                        mid_prices,
                        bid,
                        ask,
                        portfolio
                    )
                    
                    if action == "BUY" and quantity > 0:
                        if portfolio.buy(symbol, quantity, ask, timestamp):
                            trades_by_bar[trade_bar_idx].append(
                                f"  {penguin_name}: BUY {quantity} {symbol} @ ${ask:.2f}"
                            )
                    elif action == "SELL" and quantity > 0:
                        if portfolio.sell(symbol, quantity, bid, timestamp):
                            trades_by_bar[trade_bar_idx].append(
                                f"  {penguin_name}: SELL {quantity} {symbol} @ ${bid:.2f}"
                            )
                
                except Exception as e:
                    # Silently skip errors to continue backtest
                    pass
            
            # Record portfolio value
            value = portfolio.get_total_value(current_prices)
            portfolio.add_value_snapshot(value)
        
    # ======================== FINAL LIQUIDATION ========================
    # CRITICAL CONSTRAINTS for end-of-backtest liquidation:
    # 1. DO NOT call penguin.decide() or any signal evaluation methods
    # 2. DO NOT rerank penguins
    # 3. DO NOT recompute indicators during liquidation
    # 4. ONLY close existing open positions at fair prices
    #
    # This ensures final positions are closed cleanly without artificially
    # triggering new trades or changing strategy rankings based on final-bar behavior.
    # ===================================================================
    
    print("\nClosing all positions...")
    
    for penguin_name, portfolio in tqdm(portfolios.items(), desc="Closing positions"):
        # For each open position in this portfolio, close it cleanly.
        # Use average price from last 10 bars to smooth final closing price
        # and avoid unrealistic single-bar spikes.
        for symbol, quantity in list(portfolio.positions.items()):
            if quantity > 0:
                # Get price history for this SPECIFIC symbol (last_price_by_symbol)
                symbol_prices = price_history[symbol][-10:] if symbol in price_history else []
                
                if symbol_prices:
                    # Use average of last 10 bars for smooth liquidation
                    close_price = np.mean(symbol_prices)
                else:
                    # Fallback: use final available price for this symbol
                    close_price = price_history[symbol][-1] if symbol in price_history else 0
                
                # Execute closing sell only if we have a valid price
                if close_price > 0:
                    portfolio.sell(symbol, quantity, close_price, sorted_timestamps[-1])
        
        # Record final portfolio value using symbol-specific price averaging
        # (previous_close_by_symbol)
        final_prices = {}
        for symbol in symbols:
            if symbol in price_history and price_history[symbol]:
                # Average last 10 bars for each symbol independently
                final_prices[symbol] = np.mean(price_history[symbol][-10:])
        
        final_value = portfolio.get_total_value(final_prices)
        portfolio.add_value_snapshot(final_value)
    
    # Calculate metrics
    print("\nCalculating performance metrics...")
    results = {}
    for penguin_name, portfolio in tqdm(portfolios.items(), desc="Computing metrics"):
        metrics = Evaluator.calculate_metrics(portfolio, initial_capital)
        results[penguin_name] = (portfolio, metrics)
    
    cleanup_start = time.perf_counter()
    print("\nReleasing large backtest buffers before returning...", flush=True)
    data = None
    price_history = None
    all_timestamps = None
    penguins = None
    portfolios = None
    loader = None
    spread_model = None
    symbol_data = None
    full_history = None
    mid_prices = None
    current_prices = None
    quotes = None
    final_prices = None
    symbol_prices = None
    bar = None
    print(f"Released large backtest buffers in {time.perf_counter() - cleanup_start:.2f}s", flush=True)
    return results, trades_by_bar, tradeable_timestamps, {}, symbol_close_series, quality_report_text


def main():
    """Main entry point."""
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass

    # Parse config dates
    try:
        start_dt = parse_datetime_string(START_DATE)
        end_dt = parse_datetime_string(STOP_DATE)
    except ValueError as e:
        print(f"Error parsing config dates: {e}")
        print(f"  START_DATE: {START_DATE}")
        print(f"  STOP_DATE: {STOP_DATE}")
        sys.exit(1)
    
    print("\n" + "="*80)
    print("PENGUIN CAPITALIST - HISTORICAL BACKTEST")
    print("="*80)

    base_dir = Path(__file__).parent
    current_dir = base_dir / "run_current"
    current_artifacts_dir = current_dir / "artifacts"
    current_artifacts_dir.mkdir(parents=True, exist_ok=True)
    enable_training_step = TRAINING_STEP_ENABLED
    
    ################ Run backtest ################
    results, trades_by_bar, bar_timestamps, _unused_histories, _symbol_close_series, data_quality_report = run_backtest(
        symbols=SYMBOLS,
        start_datetime=start_dt,
        end_datetime=end_dt,
        binning=BINNING,
        initial_capital=INITIAL_CAPITAL,
        transaction_cost=EXEC_TRANSACTION_COST,
        penguin_classes=ACTIVE_PENGUINS,
        enable_training_step=TRAINING_STEP_ENABLED,
        artifacts_dir=current_artifacts_dir,
    )
    print("\nrun_backtest() returned; generating results...", flush=True)
    
    # Generate report
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    
    Evaluator.print_summary(results)

    # Conditionally set up archive directory based on config
    if SAVE_TO_RUN_OLD:
        run_old_base = base_dir / "run_old"
        next_run_num = get_next_run_number(run_old_base)
        current_date = datetime.now().strftime("%y%m%d")
        archive_dir = run_old_base / current_date / f"run{next_run_num}"
        archived_run_num = next_run_num
    else:
        archive_dir = None
        archived_run_num = None
    
    # Always write run_current first.
    Evaluator.save_results(results, None, current_artifacts_dir, trades_by_bar, bar_timestamps)

    # SMA artifact export intentionally disabled.
    print("\nSkipping SMA artifact export (no sma folder requested)")
    
    # Generate plots
    print("\nGenerating visualization...")
    current_plot = current_artifacts_dir / "capital_curves.png"
    
    # Get number of bars from first portfolio
    num_bars = None
    for portfolio, _ in results.values():
        num_bars = len(portfolio.value_history)
        break
    
    Evaluator.plot_capital_curves(
        results,
        current_plot,
        num_bars,
        BINNING,
        START_DATE,
        STOP_DATE,
        bar_timestamps,
        ACTIVE_SYMBOL_LIST,
    )
    
    # Generate PDF reports
    print("\nGenerating PDF report...")
    current_pdf = current_dir / "report.pdf"
    # Ensure matplotlib has sensible fallback fonts on systems missing DejaVu.
    try:
        import matplotlib
        matplotlib.rcParams.setdefault("font.family", "sans-serif")
        matplotlib.rcParams.setdefault("font.sans-serif", ["Helvetica", "Arial", "DejaVu Sans", "Liberation Sans"])
        matplotlib.rcParams.setdefault("mathtext.fontset", "stix")
    except Exception:
        # If matplotlib isn't available here, PDF generation will fail later and be handled below.
        pass

    try:
        Evaluator.generate_pdf_report(
            results,
            current_pdf,
            current_plot,
            num_bars,
            BINNING,
            START_DATE,
            STOP_DATE,
            bar_timestamps,
            current_artifacts_dir,
            ACTIVE_SYMBOL_LIST,
        )
    except Exception as e:
        print(f"\n⚠️  PDF generation failed: {e}")
        print("Skipping PDF report (fonts or rendering issue).")
    
    # Mirror run_current into run_old only after current run is fully written.
    if archive_dir:
        archive_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(current_dir, archive_dir)

    print(f"\n✅ Backtest complete!")
    
    if archive_dir:
        print(f"\nArchive saved to:  {archive_dir}")
        print(f"  - report.pdf")
        if enable_training_step and PLOT_PARETO:
            print(f"  - artifacts/{TRAINING_PARETO_FILENAME}")
        print(f"  - artifacts/capital_curves.png")
        print(f"  - artifacts/json/curves_data.json")
        print(f"  - artifacts/json/metrics_summary.json")
        print(f"  - artifacts/trades_log.txt")
        print(f"  - artifacts/consistency_warnings.txt (if residual jumps)")
    
    print(f"\nCurrent run saved to: {current_dir}")
    print(f"  - report.pdf")
    if enable_training_step and PLOT_PARETO:
        print(f"  - artifacts/{TRAINING_PARETO_FILENAME}")
    print(f"  - artifacts/capital_curves.png")
    print(f"  - artifacts/json/curves_data.json")
    print(f"  - artifacts/json/metrics_summary.json")
    print(f"  - artifacts/trades_log.txt")
    print(f"  - artifacts/consistency_warnings.txt (if residual jumps)")
    
    print(f"\n{'='*80}")
    if archive_dir:
        print(f"Run #{archived_run_num} archived")
    else:
        print("Run updated (not archived - SAVE_TO_RUN_OLD is False)")

    # Attempt a clean shutdown: close plotting resources and detect background threads.
    try:
        import threading
        try:
            import matplotlib.pyplot as plt
            plt.close('all')
        except Exception:
            pass

        non_main = [t for t in threading.enumerate() if t is not threading.main_thread()]
        non_daemon = [t.name for t in non_main if not t.daemon and t.is_alive()]
        if non_daemon:
            print(f"\nNote: {len(non_daemon)} non-daemon background thread(s) still running: {non_daemon}")
            print("If you want the process to exit immediately, run with CTRL+C or enable forced exit in the runner.")
    except Exception:
        # Defensive: don't raise from shutdown diagnostics
        pass

    # Exit explicitly to avoid waiting for non-daemon threads in some environments.
    sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user. Backtest stopped.")
        sys.exit(130)
