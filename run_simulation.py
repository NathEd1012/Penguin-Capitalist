"""Main entry point for historical backtesting simulation."""
import os
import sys
import time
import gc
import ctypes
import random
import multiprocessing as mp
import contextlib
import io
import queue
import resource
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Tuple, List
from collections import defaultdict, deque
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
from backtest.finalized_data_cache import load as load_finalized_data
from backtest.finalized_data_cache import save as save_finalized_data
from backtest.evaluator import Evaluator
from backtest.history import binning_to_minutes, history_warmup_bars, penguin_history_requirements
from scripts.data_fixes.synthetic_spread_model import SyntheticSpreadModel
from scripts.data_fixes.corporate_actions import get_price_adjustment_events
from penguins.decision_utils import call_penguin_decide
from config import (
    SYMBOLS,
    ACTIVE_SYMBOL_LIST,
    INITIAL_CAPITAL,
    EXEC_TRANSACTION_COST,
    START_DATE,
    STOP_DATE,
    BINNING,
    T_PLUS_X,
    ACTIVE_PENGUINS,
    RUN_LOG_NAME,
    SAVE_CSV,
    get_run_output_dir,
    TRAINING_STEP_ENABLED,
    TRAINING_ITERATIONS,
    TRAINING_SUBSET_MONTHS,
    TRAINING_SUBSET_STOCKS,
    TRAINING_RELATIVE_TO,
    TRAINING_RANDOM_SEED,
    TRAINING_START_DATE,
    TRAINING_STOP_DATE,
    TRAINING_TRANSACTION_COST,
    VALIDATION_START_DATE,
    VALIDATION_STOP_DATE,
    VALIDATION_CANDIDATES,
    VALIDATION_PARETO_FILENAME,
    PLOT_PARETO,
)
from config.parameter_search_con import (
    PARAMETERS_EXECUTED,
    PARAMETER_SEARCH_BAYESIAN_ACQUISITION,
    PARAMETER_SEARCH_BAYESIAN_SAMPLER,
    PARAMETER_SEARCH_BAYESIAN_UCB_KAPPA,
    PARAMETER_SEARCH_METHOD,
    PARAMETER_SEARCH_RANGE_SET,
    PARAMETER_SEARCH_WARMUP_TRIALS,
    MAX_PERIOD,
    max_period_for_strategies,
    has_parameter_search_space,
)
from scripts.parameter_search import suggest_parameters
from penguins import SP500


_PARALLEL_BACKTEST_CONTEXT = None


def _parallel_worker_count(strategy_count: int) -> int:
    configured = os.environ.get("PENGUIN_WORKERS")
    if configured:
        try:
            requested = int(configured)
        except ValueError as exc:
            raise ValueError("PENGUIN_WORKERS must be a positive integer") from exc
        if requested < 1:
            raise ValueError("PENGUIN_WORKERS must be a positive integer")
    else:
        requested = int(os.environ.get("SLURM_CPUS_PER_TASK", "1"))
    return _memory_aware_worker_count(strategy_count, requested, "backtest")


def _memory_limit_gb() -> float | None:
    """Return the job/container memory limit in GiB when it is discoverable."""
    configured = os.environ.get("PENGUIN_MEMORY_LIMIT_GB")
    if configured:
        try:
            memory_limit_gb = float(configured)
        except ValueError as exc:
            raise ValueError("PENGUIN_MEMORY_LIMIT_GB must be positive") from exc
        if memory_limit_gb <= 0:
            raise ValueError("PENGUIN_MEMORY_LIMIT_GB must be positive")
        return memory_limit_gb

    for variable in ("SLURM_MEM_PER_NODE", "SLURM_MEM_PER_CPU"):
        value = os.environ.get(variable)
        if value:
            try:
                memory_mb = float(value)
                if variable == "SLURM_MEM_PER_CPU":
                    memory_mb *= int(os.environ.get("SLURM_CPUS_PER_TASK", "1"))
                return memory_mb / 1024
            except ValueError:
                pass

    for path in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        try:
            raw_value = Path(path).read_text(encoding="ascii").strip()
            if raw_value != "max":
                value = int(raw_value)
                if value > 0:
                    return value / (1024**3)
        except (OSError, ValueError):
            pass
    return None


def _memory_aware_worker_count(strategy_count: int, requested: int, workload: str) -> int:
    """Limit parallel workers so estimated peak memory stays below the job limit."""
    worker_memory_gb = float(os.environ.get("PENGUIN_MEMORY_PER_WORKER_GB", "40"))
    reserve_fraction = float(os.environ.get("PENGUIN_MEMORY_RESERVE_FRACTION", "0"))
    if worker_memory_gb <= 0 or not 0 <= reserve_fraction < 1:
        raise ValueError(
            "PENGUIN_MEMORY_PER_WORKER_GB must be positive and "
            "PENGUIN_MEMORY_RESERVE_FRACTION must be between 0 and 1"
        )

    memory_limit_gb = _memory_limit_gb()
    memory_cap = requested
    if memory_limit_gb is not None:
        usable_memory_gb = memory_limit_gb * (1 - reserve_fraction)
        memory_cap = max(1, int(usable_memory_gb // worker_memory_gb))
        if memory_cap < requested:
            print(
                f"Memory-aware {workload} parallelism: limiting workers to {memory_cap} "
                f"(limit={memory_limit_gb:.1f} GiB, "
                f"estimated={worker_memory_gb:.1f} GiB/worker, "
                f"reserve={reserve_fraction:.0%})",
                flush=True,
            )
    return max(1, min(strategy_count, requested, memory_cap))


def _process_memory_mb() -> float:
    try:
        with open("/proc/self/statm", encoding="ascii") as handle:
            resident_pages = int(handle.read().split()[1])
        return resident_pages * os.sysconf("SC_PAGE_SIZE") / (1024 * 1024)
    except (OSError, IndexError, ValueError):
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def _parallel_worker_log(message: str, include_memory: bool = False) -> None:
    context = _PARALLEL_BACKTEST_CONTEXT
    if context is not None:
        memory_mb = _process_memory_mb() if include_memory else None
        context["log_queue"].put((memory_mb, message))


def _shutdown_parallel_pool(pool, graceful: bool) -> None:
    """Stop workers without allowing queue flushing to block forever."""
    context = _PARALLEL_BACKTEST_CONTEXT
    queues = (
        (context["progress_queue"], context["log_queue"])
        if context is not None
        else ()
    )
    timeout = float(os.environ.get("PENGUIN_POOL_SHUTDOWN_TIMEOUT", "30"))
    if timeout <= 0:
        raise ValueError("PENGUIN_POOL_SHUTDOWN_TIMEOUT must be positive")

    if graceful:
        pool.close()
    else:
        pool.terminate()

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for message_queue in queues:
            while True:
                try:
                    message_queue.get_nowait()
                except queue.Empty:
                    break
        alive = [process for process in pool._pool if process.is_alive()]
        if not alive:
            break
        for process in alive:
            process.join(timeout=min(0.2, max(0.0, deadline - time.monotonic())))

    alive = [process for process in pool._pool if process.is_alive()]
    if alive:
        print(
            f"  Parallel pool shutdown exceeded {timeout:.0f}s; "
            f"terminating {len(alive)} worker(s).",
            flush=True,
        )
        pool.terminate()
        for process in alive:
            process.join(timeout=1)

    for message_queue in queues:
        message_queue.cancel_join_thread()
        message_queue.close()
    pool.join()


def _run_parallel_strategy_worker(strategy_name: str):
    context = _PARALLEL_BACKTEST_CONTEXT
    if context is None:
        raise RuntimeError("Parallel backtest worker context was not initialized")

    _parallel_worker_log(f"strategy={strategy_name}")
    penguin = context["penguins"][strategy_name]
    traded_symbols = getattr(penguin, "TRADED_SYMBOLS", None)
    worker_symbols = (
        sorted(set(context["symbols"]).intersection(traded_symbols))
        if traded_symbols is not None
        else context["symbols"]
    )
    # The parent process owns progress rendering. Capturing both streams keeps
    # worker-local bars from interleaving and making the log unreadable.
    def report_progress(percent: int, elapsed: float, remaining: float | None, rate: float | None):
        context["progress_queue"].put((strategy_name, percent, elapsed, remaining, rate))

    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = run_backtest(
                symbols=worker_symbols,
                start_datetime=context["start_datetime"],
                end_datetime=context["end_datetime"],
                binning=context["binning"],
                initial_capital=context["initial_capital"],
                transaction_cost=context["transaction_cost"],
                penguin_classes=[penguin],
                artifacts_dir=None,
                training_step_allowed=False,
                collect_trade_details=context["collect_trade_details"],
                t_plus_x=context["t_plus_x"],
                backtest_label=context["backtest_label"],
                loaded_data=context["data"],
                loaded_valid_symbols=context["symbols"],
                loaded_price_basis_adjusted=context["price_basis_adjusted"],
                progress_callback=report_progress,
            )
        _parallel_worker_log(
            f"completed strategy={strategy_name}",
            include_memory=True,
        )
        return strategy_name, result
    except Exception:
        _parallel_worker_log(
            f"failed strategy={strategy_name}\n{traceback.format_exc()}",
            include_memory=True,
        )
        raise


def percent_progress(iterable, desc: str, progress_callback=None):
    total = len(iterable)
    if total == 0:
        return

    progress = tqdm(total=total, desc=desc)
    last_percent = -1
    next_report = 0
    progress_start = time.perf_counter()
    if progress_callback is not None:
        progress_callback(0, 0.0, None, None)

    try:
        for index, item in enumerate(iterable, start=1):
            percent = (index * 100) // total
            if percent != last_percent:
                progress.update(index - progress.n)
                last_percent = percent
            if progress_callback is not None and percent >= next_report:
                while next_report <= percent:
                    elapsed = time.perf_counter() - progress_start
                    rate = index / elapsed if elapsed > 0 else None
                    remaining = (
                        (total - index) / rate
                        if rate and rate > 0
                        else None
                    )
                    progress_callback(next_report, elapsed, remaining, rate)
                    next_report += 10
            yield index - 1, item

        if progress.n < total:
            progress.update(total - progress.n)
        if progress_callback is not None and next_report <= 100:
            elapsed = time.perf_counter() - progress_start
            rate = total / elapsed if elapsed > 0 else None
            progress_callback(100, elapsed, 0.0, rate)
    finally:
        progress.close()


def _format_progress_duration(seconds: float | None) -> str:
    if seconds is None:
        return "?"
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"


def parse_datetime_string(dt_str: str) -> datetime:
    """
    Parse datetime from config format string.

    Accepts:
    - ISO format: "2026-02-20 14:30:00"
    - With timezone: "2026-02-20 14:30:00+01:00"
    - Special keyword: "TODAY" (resolves to yesterday at 23:50:00 UTC to avoid recent SIP data restrictions)

    Assumes UTC if no timezone specified.
    """
    if isinstance(dt_str, datetime):
        dt = dt_str
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    dt_str = dt_str.strip()

    if dt_str.upper() == "TODAY":
        yesterday = datetime.now(timezone.utc).replace(hour=23, minute=50, second=0, microsecond=0) - timedelta(days=1)
        return yesterday

    for fmt in ["%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S"]:
        try:
            dt = datetime.strptime(dt_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue

    raise ValueError(f"Cannot parse datetime: {dt_str}")


def _format_runtime_configuration_banner(
    *,
    start_datetime_utc,
    end_datetime_utc,
    binning,
    initial_capital,
    transaction_cost,
    symbols,
    active_symbol_list,
    training_step_enabled,
    training_relative_to,
    training_iterations,
    training_subset_stocks,
    training_subset_months,
    training_transaction_cost,
    max_period=MAX_PERIOD,
    training_random_seed,
    parameter_search_method,
    parameter_search_range_set="broad",
    parameter_search_warmup_trials,
    training_start_datetime_utc,
    training_end_datetime_utc,
    t_plus_x=T_PLUS_X,
    parameter_search_bayesian_sampler="gp",
    parameter_search_bayesian_acquisition="ei",
    parameter_search_bayesian_ucb_kappa=2.0,
    validation_start_datetime_utc=None,
    validation_end_datetime_utc=None,
    validation_candidates=VALIDATION_CANDIDATES,
    parameters_executed=PARAMETERS_EXECUTED,
) -> str:
    """Return the runtime banner text for backtest and training configuration."""

    lines = [
        f"{'=' * 80}",
        "BACKTEST CONFIGURATION",
        f"{'=' * 80}",
        f"Start Time (UTC):  {start_datetime_utc}",
        f"End Time (UTC):    {end_datetime_utc}",
        f"Binning:           {binning}",
        "",
        "PORTFOLIO CONFIGURATION",
        f"Initial Capital:   ${initial_capital:,.2f}",
        f"Transaction Cost:  ${transaction_cost:.2f}",
        f"Symbol List:       {active_symbol_list}",
        f"Symbols:           {len(symbols)}",
        f"{'=' * 80}",
        "",
        f"{'=' * 80}",
        "TRAINING CONFIGURATION",
        f"{'=' * 80}",
        f"Training Step Enabled: {str(training_step_enabled).lower()}",
        f"Training Relative To:  {training_relative_to}",
        f"Training Steps:        {training_iterations}",
        f"Training Sample:       {training_subset_stocks} stocks x {training_subset_months} month(s)",
        f"Training Transaction Cost: ${training_transaction_cost:.2f}",
        f"Maximum Period:       {max_period}",
        f"T_PLUS_X (bars):      {t_plus_x}",
        f"Training Seed:         {training_random_seed}",
        f"Parameter Search:      {parameter_search_method}",
        f"Parameter Range Set:   {parameter_search_range_set}",
        f"Bayesian Sampler:      {parameter_search_bayesian_sampler}",
        f"Acquisition Function:  {parameter_search_bayesian_acquisition}",
        f"UCB Kappa:             {parameter_search_bayesian_ucb_kappa}",
        f"Search Warmup Trials:  {parameter_search_warmup_trials}",
        f"Training Start (UTC):  {training_start_datetime_utc}",
        f"Training End (UTC):    {training_end_datetime_utc}",
        f"Validation Start (UTC): {validation_start_datetime_utc}",
        f"Validation End (UTC):   {validation_end_datetime_utc}",
        f"Validation Candidates:   {validation_candidates}",
        f"Parameters Executed:     {parameters_executed}",
        f"{'=' * 80}",
    ]
    return "\n".join(lines)


def _replace_trainable_penguin_params(penguin, params: Dict[str, int | float], name: str | None = None):
    requested_name = name or penguin.name
    try:
        updated_penguin = penguin.__class__(name=requested_name, **params)
        # Some BasePenguin implementations normalize the constructor name.
        updated_penguin.name = requested_name
        if hasattr(penguin, "record_history"):
            updated_penguin.record_history = bool(getattr(penguin, "record_history"))
        return updated_penguin
    except Exception:
        if hasattr(penguin, "params"):
            for key, value in params.items():
                setattr(penguin.params, key, value)
        penguin.name = requested_name
        return penguin


def _instantiate_penguin(penguin_spec):
    if not isinstance(penguin_spec, type):
        return penguin_spec if hasattr(penguin_spec, "decide") else penguin_spec()

    if has_parameter_search_space(penguin_spec):
        parameters, _ = suggest_parameters(
            strategy_class=penguin_spec,
            completed_trials=[],
            rng=random.Random(TRAINING_RANDOM_SEED),
        )
        return penguin_spec(**parameters)

    return penguin_spec()


def run_backtest(
    symbols: List[str],
    start_datetime: datetime,
    end_datetime: datetime,
    binning: str,
    initial_capital: float,
    transaction_cost: float,
    penguin_classes: List,
    artifacts_dir: Path | None = None,
    training_step_allowed: bool = True,
    collect_trade_details: bool = True,
    t_plus_x: int = T_PLUS_X,
    backtest_label: str = "test",
    loaded_data: Dict[str, Dict[datetime, Dict]] | None = None,
    loaded_valid_symbols: List[str] | None = None,
    loaded_price_basis_adjusted: Dict[str, bool] | None = None,
    progress_callback=None,
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

    if t_plus_x < 0:
        raise ValueError("t_plus_x must be a nonnegative integer")
    
    # Ensure both datetimes are UTC
    if start_datetime.tzinfo is None:
        start_datetime = start_datetime.replace(tzinfo=timezone.utc)
    if end_datetime.tzinfo is None:
        end_datetime = end_datetime.replace(tzinfo=timezone.utc)
    
    # Convert to UTC if needed
    start_datetime_utc = start_datetime.astimezone(timezone.utc)
    end_datetime_utc = end_datetime.astimezone(timezone.utc)

    max_period = max_period_for_strategies(penguin_classes)
    warmup_bars = history_warmup_bars(penguin_classes, max_period=max_period)
    warmup_minutes = binning_to_minutes(binning)
    warmup_start_datetime_utc = start_datetime_utc - timedelta(minutes=warmup_bars * warmup_minutes)

    if training_step_allowed and TRAINING_STEP_ENABLED:
        trainable_classes = [
            penguin_class
            for penguin_class in penguin_classes
            if has_parameter_search_space(penguin_class)
        ]
        if trainable_classes:
            training_start_datetime_utc = parse_datetime_string(TRAINING_START_DATE).astimezone(timezone.utc)
            training_warmup = history_warmup_bars(
                trainable_classes,
                max_period=max_period_for_strategies(trainable_classes),
            )
            training_warmup_start = training_start_datetime_utc - timedelta(
                minutes=training_warmup * warmup_minutes
            )
            warmup_start_datetime_utc = min(warmup_start_datetime_utc, training_warmup_start)
    
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

    reuse_requested = loaded_data is not None and loaded_valid_symbols is not None
    if not reuse_requested:
        print("\n" + _format_runtime_configuration_banner(
            start_datetime_utc=start_datetime_utc,
            end_datetime_utc=end_datetime_utc,
            binning=binning,
            initial_capital=initial_capital,
            transaction_cost=transaction_cost,
            symbols=symbols,
            active_symbol_list=ACTIVE_SYMBOL_LIST,
            training_step_enabled=TRAINING_STEP_ENABLED,
            training_relative_to=TRAINING_RELATIVE_TO,
            training_iterations=TRAINING_ITERATIONS,
            training_subset_stocks=TRAINING_SUBSET_STOCKS,
            training_subset_months=TRAINING_SUBSET_MONTHS,
            training_transaction_cost=TRAINING_TRANSACTION_COST,
            max_period=max_period,
            training_random_seed=TRAINING_RANDOM_SEED,
            parameter_search_method=PARAMETER_SEARCH_METHOD,
            parameter_search_range_set=PARAMETER_SEARCH_RANGE_SET,
            parameter_search_warmup_trials=PARAMETER_SEARCH_WARMUP_TRIALS,
            parameter_search_bayesian_sampler=PARAMETER_SEARCH_BAYESIAN_SAMPLER,
            parameter_search_bayesian_acquisition=PARAMETER_SEARCH_BAYESIAN_ACQUISITION,
            parameter_search_bayesian_ucb_kappa=PARAMETER_SEARCH_BAYESIAN_UCB_KAPPA,
            training_start_datetime_utc=TRAINING_START_DATE,
            training_end_datetime_utc=TRAINING_STOP_DATE,
            validation_start_datetime_utc=VALIDATION_START_DATE,
            validation_end_datetime_utc=VALIDATION_STOP_DATE,
            validation_candidates=VALIDATION_CANDIDATES,
            parameters_executed=PARAMETERS_EXECUTED,
            t_plus_x=t_plus_x,
        ))
    
    quality_report_text = ""
    price_basis_adjusted = dict(loaded_price_basis_adjusted or {})
    reuse_loaded_data = loaded_data is not None and loaded_valid_symbols is not None
    if reuse_loaded_data:
        source_timestamps = [
            timestamp
            for symbol_data in loaded_data.values()
            for timestamp in symbol_data
        ]
        reuse_loaded_data = bool(source_timestamps) and min(source_timestamps) <= warmup_start_datetime_utc
        if reuse_loaded_data:
            data = {
                symbol: {
                    timestamp: bar
                    for timestamp, bar in loaded_data[symbol].items()
                    if warmup_start_datetime_utc <= timestamp < end_datetime_utc
                }
                for symbol in loaded_valid_symbols
                if symbol in loaded_data
            }
            data_timestamps = [
                timestamp
                for symbol_data in data.values()
                for timestamp in symbol_data
            ]
            reuse_loaded_data = bool(data_timestamps) and max(data_timestamps) >= start_datetime_utc

    if not reuse_loaded_data:
        # Load data
        finalized_cache_dir = Path(
            os.environ.get(
                "PENGUIN_FINALIZED_CACHE_DIR",
                Path(__file__).parent / "data_cache" / "finalized_step1",
            )
        ).expanduser()
        training_start_for_cache = parse_datetime_string(
            TRAINING_START_DATE
        ).astimezone(timezone.utc)
        training_end_for_cache = parse_datetime_string(
            TRAINING_STOP_DATE
        ).astimezone(timezone.utc)
        validation_start_for_cache = parse_datetime_string(
            VALIDATION_START_DATE
        ).astimezone(timezone.utc)
        validation_end_for_cache = parse_datetime_string(
            VALIDATION_STOP_DATE
        ).astimezone(timezone.utc)
        cache_warmup_bars = 1000
        cache_anchor = min(start_datetime_utc, training_start_for_cache)
        canonical_cache_start = cache_anchor - timedelta(
            minutes=cache_warmup_bars * warmup_minutes
        )
        load_start = min(warmup_start_datetime_utc, canonical_cache_start)
        cached_step1 = load_finalized_data(
            finalized_cache_dir,
            symbols,
            load_start,
            end_datetime_utc,
            binning,
            cache_start_date=canonical_cache_start,
            training_start_date=training_start_for_cache,
            training_end_date=training_end_for_cache,
            validation_start_date=validation_start_for_cache,
            validation_end_date=validation_end_for_cache,
            warmup_bars=cache_warmup_bars,
        )
        if cached_step1 is not None:
            print("Step 1: Loaded finalized historical data from local cache.")
            data = {
                symbol: {
                    timestamp: bar
                    for timestamp, bar in symbol_data.items()
                    if warmup_start_datetime_utc <= timestamp < end_datetime_utc
                }
                for symbol, symbol_data in cached_step1["data"].items()
            }
            sparse_warning = cached_step1["sparse_warning"]
            price_basis_adjusted = cached_step1["price_basis_adjusted"]
            quality_report_text = cached_step1["quality_report_text"]
            loader = None
        else:
            print("Step 1: Loading historical data from Alpaca...")
            loader = DataLoader()
            try:
                data, sparse_warning = loader.load_bars(
                    symbols,
                    load_start,
                    end_datetime_utc,
                    binning,
                    enable_data_quality_checks=True,
                )
                price_basis_adjusted = dict(loader.last_price_basis_adjusted)
                quality_report_text = loader.get_quality_report_text()
            except Exception as e:
                raise RuntimeError(
                    f"Error loading data: {e}. "
                    "Make sure APCA_API_KEY_ID and APCA_API_SECRET_KEY are set."
                ) from e
            try:
                save_finalized_data(
                    finalized_cache_dir,
                    symbols,
                    load_start,
                    end_datetime_utc,
                    binning,
                    {
                        "data": data,
                        "sparse_warning": sparse_warning,
                        "price_basis_adjusted": price_basis_adjusted,
                        "quality_report_text": quality_report_text,
                    },
                    cache_start_date=canonical_cache_start,
                    training_start_date=training_start_for_cache,
                    training_end_date=training_end_for_cache,
                    validation_start_date=validation_start_for_cache,
                    validation_end_date=validation_end_for_cache,
                    warmup_bars=cache_warmup_bars,
                )
                print("  Saved finalized Step 1 data to local cache.")
            except OSError as e:
                print(f"  Warning: could not save finalized Step 1 cache: {e}")
            if sparse_warning:
                print(sparse_warning)
        data = {
            symbol: {
                timestamp: bar
                for timestamp, bar in symbol_data.items()
                if warmup_start_datetime_utc <= timestamp < end_datetime_utc
            }
            for symbol, symbol_data in data.items()
        }
        if quality_report_text and artifacts_dir is not None:
            warnings_path = Path(artifacts_dir) / "consistency_warnings.txt"
            warnings_path.parent.mkdir(parents=True, exist_ok=True)
            with open(warnings_path, "w") as f:
                f.write(quality_report_text)
                f.write("\n")
    
    ################################ STEP 2 ################################

    # Detect stale data
    if not reuse_loaded_data:
        print("\nStep 2: Detecting stale data...")
    if reuse_loaded_data:
        valid_symbols = [symbol for symbol in loaded_valid_symbols if symbol in data]
        stale_symbols = []
    else:
        valid_symbols, stale_symbols = DataLoader.detect_stale_data(data)
    
    if not reuse_loaded_data:
        print(f"  Valid symbols: {len(valid_symbols)}")
        if stale_symbols:
            print(f"  Stale symbols ({len(stale_symbols)}): {', '.join(stale_symbols)}")
    
    symbols = valid_symbols
    if not symbols:
        raise RuntimeError("No valid symbols to trade!")
    
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

    ################################ STEP 3 ################################


    print(f"\nStep 3: Initializing {len(penguin_classes)} strategies")
    for penguin_spec in penguin_classes:
        try:
            penguin = _instantiate_penguin(penguin_spec)
            pen_name = penguin.name
            portfolios[pen_name] = Portfolio(
                initial_capital,
                transaction_cost,
                record_trades=collect_trade_details,
            )
            portfolios[pen_name].max_leverage = float(getattr(penguin, "MAX_LEVERAGE", 1.0))
            penguins[pen_name] = penguin
        except Exception as e:
            penguin_name = getattr(penguin_spec, "__name__", getattr(penguin_spec, "name", str(penguin_spec)))
            print(f"  ✗ {penguin_name}: {e}")
    print("  Done")

    ################################ STEP 3b ################################

    if training_step_allowed and TRAINING_STEP_ENABLED:
        active_trainables = []
        seen_trainable_classes = set()
        for penguin in penguins.values():
            penguin_class = penguin.__class__
            if has_parameter_search_space(penguin_class) and penguin_class not in seen_trainable_classes:
                active_trainables.append(penguin_class)
                seen_trainable_classes.add(penguin_class)

        if active_trainables:
            from scripts.train_trainable_penguins import prepare_training_context, run_training_step

            training_start_dt = parse_datetime_string(TRAINING_START_DATE)
            training_end_dt = parse_datetime_string(TRAINING_STOP_DATE)
            training_symbols, _training_sorted_timestamps, training_tradeable_timestamps, training_quality_report_text = prepare_training_context(
                symbols=symbols,
                start_datetime=training_start_dt,
                end_datetime=training_end_dt,
                binning=binning,
                penguin_classes=active_trainables,
                loaded_data=data if training_start_dt >= start_datetime_utc else None,
                loaded_quality_report_text=quality_report_text,
            )

            if training_quality_report_text and artifacts_dir is not None:
                training_warnings_path = Path(artifacts_dir) / "consistency_warnings.txt"
                with open(training_warnings_path, "a") as f:
                    f.write("\n" + "=" * 80 + "\n")
                    f.write("TRAINING CONSISTENCY WARNINGS\n")
                    f.write("=" * 80 + "\n")
                    f.write(training_quality_report_text)
                    f.write("\n")

            training_artifacts_dir = Path(artifacts_dir) if artifacts_dir is not None else Path(__file__).parent / "run_test" / "artifacts"
            trained_parameters = run_training_step(
                trainable_strategy_classes=active_trainables,
                symbols=training_symbols,
                tradeable_timestamps=training_tradeable_timestamps,
                binning=binning,
                initial_capital=initial_capital,
                artifacts_dir=training_artifacts_dir,
                t_plus_x=t_plus_x,
                loaded_data=data if training_start_dt >= start_datetime_utc else None,
                loaded_valid_symbols=symbols if training_start_dt >= start_datetime_utc else None,
                loaded_price_basis_adjusted=price_basis_adjusted,
            )

            validation_specs = []
            for penguin_name, penguin in list(penguins.items()):
                strategy_name = penguin.__class__.__name__
                if strategy_name not in trained_parameters:
                    continue

                training_result = trained_parameters[strategy_name]
                validation_candidates = training_result.get("validation_params") or training_result.get("top_params") or [
                    {"params": training_result.get("best_params", {})}
                ]
                for rank, candidate in enumerate(validation_candidates[:VALIDATION_CANDIDATES], start=1):
                    training_step = int(candidate.get("trial", rank))
                    validation_name = f"{strategy_name}__validation_{training_step:03d}"
                    validation_penguin = _replace_trainable_penguin_params(
                        penguin,
                        candidate.get("params", {}),
                        name=validation_name,
                    )
                    validation_specs.append(
                        (strategy_name, penguin_name, candidate, validation_penguin)
                    )

            if validation_specs:
                from scripts.train_trainable_penguins import _score_training_candidate
                from scripts.train_trainable_penguins import _training_profit_amount
                from scripts.plotting import create_training_pareto_pdf

                print(
                    f"\nValidation: evaluating {len(validation_specs)} candidate(s) "
                    f"from {VALIDATION_START_DATE} to {VALIDATION_STOP_DATE}..."
                )
                validation_results, _, _, _, _, _ = run_backtest(
                    symbols=symbols,
                    start_datetime=parse_datetime_string(VALIDATION_START_DATE),
                    end_datetime=parse_datetime_string(VALIDATION_STOP_DATE),
                    binning=binning,
                    initial_capital=initial_capital,
                    transaction_cost=transaction_cost,
                    penguin_classes=[spec[3] for spec in validation_specs] + [SP500],
                    training_step_allowed=False,
                    collect_trade_details=False,
                    t_plus_x=t_plus_x,
                    backtest_label="validation",
                    loaded_data=data,
                    loaded_valid_symbols=symbols,
                    loaded_price_basis_adjusted=price_basis_adjusted,
                )
                benchmark_metrics = validation_results[SP500().name][1]
                ranked_by_strategy = defaultdict(list)
                validation_pareto_history = defaultdict(list)
                validation_parameter_history = []
                for strategy_name, penguin_name, candidate, validation_penguin in validation_specs:
                    metrics = validation_results[validation_penguin.name][1]
                    score = _score_training_candidate(
                        metrics,
                        benchmark_metrics,
                        transaction_cost,
                        TRAINING_RELATIVE_TO,
                        initial_capital,
                    )
                    ranked_by_strategy[strategy_name].append(
                        {
                            "params": dict(candidate.get("params", {})),
                            "trial": int(candidate.get("trial", 0)),
                            "training_score": candidate.get("score"),
                            "validation_score": list(score),
                            "validation_metrics": metrics,
                            "penguin_name": penguin_name,
                        }
                    )
                    validation_pareto_history[strategy_name].append(
                        {
                            "trial": int(candidate.get("trial", 0)),
                            "status": "completed",
                            "buy_trades": int(metrics.get("buy_trades", metrics.get("total_trades", 0))),
                            "total_trades": int(metrics.get("total_trades", 0)),
                            "profit_amount": float(metrics.get("total_return", 0.0)),
                            "relative_profit_amount": _training_profit_amount(
                                metrics,
                                benchmark_metrics,
                                TRAINING_RELATIVE_TO,
                                initial_capital,
                            ),
                            "score": list(score),
                        }
                    )
                    validation_parameter_history.append(
                        {
                            "strategy": strategy_name,
                            "trial": int(candidate.get("trial", 0)),
                            "params": dict(candidate.get("params", {})),
                        }
                    )

                validation_selection = {}
                validation_trained_parameters = {}
                for strategy_name, ranked_candidates in ranked_by_strategy.items():
                    ranked_candidates.sort(
                        key=lambda candidate: tuple(candidate["validation_score"]),
                        reverse=True,
                    )
                    selected_candidates = ranked_candidates[:PARAMETERS_EXECUTED]
                    validation_selection[strategy_name] = selected_candidates
                    validation_trained_parameters[strategy_name] = {
                        "best_params": dict(ranked_candidates[0]["params"]) if ranked_candidates else {}
                    }
                    original_name = selected_candidates[0]["penguin_name"] if selected_candidates else None
                    original_penguin = penguins.pop(original_name, None) if original_name else None
                    portfolios.pop(original_name, None) if original_name else None
                    if original_penguin is None:
                        continue
                    for rank, selected in enumerate(selected_candidates, start=1):
                        variant_name = (
                            original_name
                            if rank == 1
                            else f"{original_name}_{int(selected['trial']):03d}"
                        )
                        variant = _replace_trainable_penguin_params(
                            original_penguin,
                            selected["params"],
                            name=variant_name,
                        )
                        penguins[variant_name] = variant
                        portfolios[variant_name] = Portfolio(initial_capital, transaction_cost)
                        portfolios[variant_name].max_leverage = float(
                            getattr(variant, "MAX_LEVERAGE", 1.0)
                        )

                if PLOT_PARETO and artifacts_dir is not None:
                    validation_pareto_path = Path(artifacts_dir).parent / VALIDATION_PARETO_FILENAME
                    create_training_pareto_pdf(
                        dict(validation_pareto_history),
                        validation_parameter_history,
                        validation_trained_parameters,
                        validation_pareto_path,
                        title="Validation Pareto Front",
                        relative_to=TRAINING_RELATIVE_TO,
                        transaction_cost=transaction_cost,
                    )

                if artifacts_dir is not None:
                    validation_path = Path(artifacts_dir) / "json" / "validation_selection.json"
                    validation_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(validation_path, "w", encoding="utf-8") as handle:
                        import json
                        json.dump(
                            {
                                "validation_start": VALIDATION_START_DATE,
                                "validation_stop": VALIDATION_STOP_DATE,
                                "validation_candidates": VALIDATION_CANDIDATES,
                                "parameters_executed": PARAMETERS_EXECUTED,
                                "selection": validation_selection,
                            },
                            handle,
                            indent=2,
                            default=str,
                        )
                del validation_results
            else:
                print("No training candidates are available for validation; using base strategies.")
        else:
            print("No trainable penguins are active; skipping Step 3b training.")

    worker_count = _parallel_worker_count(len(penguins))
    parallel_enabled = (
        worker_count > 1
        and os.environ.get("PENGUIN_PARALLEL", "1").lower()
        not in {"0", "false", "no"}
    )
    if parallel_enabled:
        if "fork" not in mp.get_all_start_methods():
            raise RuntimeError(
                "Parallel strategy backtests require the fork multiprocessing start method"
            )

        global _PARALLEL_BACKTEST_CONTEXT
        parallel_context = mp.get_context("fork")
        _PARALLEL_BACKTEST_CONTEXT = {
            "symbols": symbols,
            "start_datetime": start_datetime,
            "end_datetime": end_datetime,
            "binning": binning,
            "initial_capital": initial_capital,
            "transaction_cost": transaction_cost,
            "t_plus_x": t_plus_x,
            "backtest_label": backtest_label,
            "collect_trade_details": collect_trade_details,
            "data": data,
            "valid_symbols": valid_symbols,
            "price_basis_adjusted": price_basis_adjusted,
            "penguins": penguins,
            "progress_queue": parallel_context.Queue(),
            "log_queue": parallel_context.Queue(),
        }
        print(
            f"\nStep {5 if backtest_label.casefold() == 'test' else 4}: "
            f"Running {len(penguins)} strategies "
            f"({worker_count} parallel workers)"
        )
        strategy_results = {}
        trades_by_bar = {}
        tradeable_timestamps = []
        quality_report_text = ""
        strategy_names = sorted(
            penguins,
            key=lambda name: (0 if name == "SP500" else 1, name),
        )
        completed_strategies = set()
        last_progress = {}
        progress_details = {}
        display_index = 0
        displayed_progress = {}
        # Pool.maxtasksperchild is the multiprocessing.Pool equivalent of
        # ProcessPoolExecutor(max_tasks_per_child=1) and remains compatible
        # with fork, allowing workers to inherit the already-loaded dataset.
        pool = parallel_context.Pool(processes=worker_count, maxtasksperchild=1)
        try:
            pending_results = {}
            next_strategy_index = 0
            last_worker_activity = time.monotonic()
            worker_timeout = float(os.environ.get("PENGUIN_WORKER_TIMEOUT", "3600"))
            if worker_timeout <= 0:
                raise ValueError("PENGUIN_WORKER_TIMEOUT must be positive")
            shutdown_gracefully = True
            print("  Strategy progress (10% steps):", flush=True)
            while len(completed_strategies) < len(strategy_names):
                while (
                    next_strategy_index < len(strategy_names)
                    and len(pending_results) < worker_count
                ):
                    strategy_name = strategy_names[next_strategy_index]
                    pending_results[strategy_name] = pool.apply_async(
                        _run_parallel_strategy_worker, (strategy_name,)
                    )
                    next_strategy_index += 1
                _parallel_worker_log(
                    f"pending={len(pending_results)} "
                    f"completed={len(completed_strategies)}/{len(strategy_names)}"
                )
                while True:
                    completed_now = False
                    try:
                        (
                            strategy_name,
                            percent,
                            elapsed,
                            remaining,
                            rate,
                        ) = _PARALLEL_BACKTEST_CONTEXT["progress_queue"].get(
                            timeout=0.5
                        )
                        last_progress[strategy_name] = max(
                            percent,
                            last_progress.get(strategy_name, -1),
                        )
                        progress_details[strategy_name] = (elapsed, remaining, rate)
                        last_worker_activity = time.monotonic()
                    except queue.Empty:
                        pass

                    for strategy_name, async_result in list(pending_results.items()):
                        if not async_result.ready():
                            continue
                        worker_strategy_name, worker_result = async_result.get()
                        if worker_strategy_name != strategy_name:
                            raise RuntimeError(
                                "Parallel strategy worker returned an unexpected strategy: "
                                f"expected {strategy_name}, got {worker_strategy_name}"
                            )
                        (
                            worker_strategy_results,
                            worker_trades_by_bar,
                            worker_tradeable_timestamps,
                            _worker_unused,
                            _worker_close_series,
                            worker_quality_report,
                        ) = worker_result
                        strategy_results.update(worker_strategy_results)
                        for bar_idx, trades in worker_trades_by_bar.items():
                            trades_by_bar.setdefault(bar_idx, []).extend(trades)
                        if not tradeable_timestamps:
                            tradeable_timestamps = worker_tradeable_timestamps
                        quality_report_text = quality_report_text or worker_quality_report
                        del worker_result, worker_strategy_results, worker_trades_by_bar
                        del worker_tradeable_timestamps, worker_quality_report
                        del pending_results[strategy_name]
                        gc.collect()
                        last_progress[strategy_name] = 100
                        completed_strategies.add(strategy_name)
                        last_worker_activity = time.monotonic()
                        completed_now = True

                    while display_index < len(strategy_names):
                        active_strategy = strategy_names[display_index]
                        active_percent = last_progress.get(active_strategy, 0)
                        if active_percent > displayed_progress.get(active_strategy, 0):
                            for percent in range(
                                max(10, displayed_progress.get(active_strategy, 0) + 10),
                                active_percent + 1,
                                10,
                            ):
                                elapsed, remaining, rate = progress_details.get(
                                    active_strategy,
                                    (None, None, None),
                                )
                                rate_text = f"{rate:.2f}it/s" if rate is not None else "?it/s"
                                print(
                                    f"    {active_strategy}: {percent:3d}% "
                                    f"[{_format_progress_duration(elapsed)}"
                                    f"<{_format_progress_duration(remaining)}, "
                                    f"{rate_text}]",
                                    flush=True,
                                )
                            displayed_progress[active_strategy] = active_percent

                        if active_strategy not in completed_strategies:
                            break

                        if displayed_progress.get(active_strategy, 0) < 100:
                            print(f"    {active_strategy}: 100%", flush=True)
                            displayed_progress[active_strategy] = 100
                        print(
                            f"    {len(completed_strategies)}/{len(strategy_names)} complete",
                            flush=True,
                        )
                        display_index += 1
                    try:
                        memory_mb, message = _PARALLEL_BACKTEST_CONTEXT["log_queue"].get_nowait()
                        if memory_mb is None:
                            print(f"    {message}", flush=True)
                        else:
                            print(
                                f"    {message} rss={memory_mb / 1024:.1f}GiB",
                                flush=True,
                            )
                    except queue.Empty:
                        pass
                    if len(completed_strategies) == len(strategy_names):
                        break
                    if time.monotonic() - last_worker_activity > worker_timeout:
                        raise RuntimeError(
                            f"Parallel strategy execution stalled for {worker_timeout:.0f}s "
                            f"without worker progress; pending={sorted(pending_results)}; "
                            f"progress={{{', '.join(f'{name}={last_progress.get(name, 0)}%' for name in sorted(pending_results))}}}"
                        )
                    if not pending_results:
                        raise RuntimeError(
                            "Parallel strategy execution lost all pending workers "
                            f"with {len(completed_strategies)}/{len(strategy_names)} complete"
                        )
                    failed_workers = [
                        process.pid
                        for process in pool._pool
                        if process.exitcode not in (None, 0)
                    ]
                    if failed_workers:
                        raise RuntimeError(
                            "Parallel strategy worker process(es) exited unexpectedly: "
                            f"{failed_workers}; pending={sorted(pending_results)}"
                        )
                    if completed_now:
                        break
                    time.sleep(0.2)
        except Exception:
            for strategy_name, async_result in pending_results.items():
                if async_result.ready():
                    try:
                        async_result.get()
                    except Exception:
                        pass
            shutdown_gracefully = False
            _PARALLEL_BACKTEST_CONTEXT = None
            raise
        finally:
            _shutdown_parallel_pool(pool, graceful=shutdown_gracefully)
        _PARALLEL_BACKTEST_CONTEXT = None

        return (
            strategy_results,
            trades_by_bar,
            tradeable_timestamps,
            {},
            {},
            quality_report_text,
        )

    backtest_step = 5 if backtest_label.casefold() == "test" else 4


    # Run simulation
    print(
        f"\nStep {backtest_step}: Running {backtest_label} backtest "
        f"({len(sorted_timestamps)} bars)...\n"
    )
    
    # Keep enough history for the active parameter ranges and each strategy's lookback,
    # but do not retain the entire backtest in memory.
    history_capacity = max(
        [max_period + 2]
        + [
            penguin_history_requirements(penguin, max_period)[1]
            for penguin in penguins.values()
        ]
    )
    price_history = defaultdict(lambda: deque(maxlen=history_capacity))
    volume_history = defaultdict(lambda: deque(maxlen=history_capacity))
    price_adjustment_events = {
        symbol: get_price_adjustment_events(symbol)
        for symbol in symbols
        if not price_basis_adjusted.get(symbol, False)
    }
    
    # Track trades by bar for detailed logging
    trades_by_bar = defaultdict(list)
    trade_bar_idx = -1
    pending_orders = defaultdict(list)

    def execute_orders(penguin_name, orders, quotes, portfolio, timestamp):
        for order_symbol, action, quantity in orders:
            if order_symbol not in quotes or quantity <= 0:
                continue

            bid, ask = quotes[order_symbol]
            if action == "BUY":
                if order_symbol == "SPY" and ask > 0 and portfolio.max_leverage <= 1.0:
                    quantity = int(max(portfolio.cash - portfolio.transaction_cost, 0) // ask)
                if portfolio.buy(order_symbol, quantity, ask, timestamp):
                    if collect_trade_details:
                        trades_by_bar[trade_bar_idx].append(
                            f"  {penguin_name}: BUY {quantity} {order_symbol} @ ${ask:.2f}"
                        )
            elif action == "SELL":
                if portfolio.sell(order_symbol, quantity, bid, timestamp):
                    if collect_trade_details:
                        trades_by_bar[trade_bar_idx].append(
                            f"  {penguin_name}: SELL {quantity} {order_symbol} @ ${bid:.2f}"
                        )
    
    for bar_idx, timestamp in percent_progress(
        sorted_timestamps,
        desc="Executing bars",
        progress_callback=progress_callback,
    ):
        # Get current prices
        current_prices = {}
        for symbol in symbols:
            bar = data[symbol].get(timestamp)
            if bar and bar.get("data_quality", "OK") == "OK":
                current_prices[symbol] = bar['close']
        
        if not current_prices:
            continue

        for portfolio in portfolios.values():
            portfolio.apply_price_adjustments(timestamp, price_adjustment_events)
        
        # Update price history for each symbol
        for symbol in symbols:
            bar = data[symbol].get(timestamp)
            if bar is None:
                if symbol in price_history and price_history[symbol]:
                    # Keep last known price if data is missing entirely.
                    price_history[symbol].append(price_history[symbol][-1])
                else:
                    price_history[symbol].append(current_prices.get(symbol, 0))
                if symbol in volume_history and volume_history[symbol]:
                    volume_history[symbol].append(volume_history[symbol][-1])
                else:
                    volume_history[symbol].append(0.0)
            elif bar.get("data_quality", "OK") == "OK":
                price_history[symbol].append(bar['close'])
                volume_history[symbol].append(bar.get('volume', 0))
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

            # Orders are decided on bar t and executed at the configured later bar.
            execute_orders(
                penguin_name,
                pending_orders.pop((penguin_name, trade_bar_idx), []),
                quotes,
                portfolio,
                timestamp,
            )
            
            if hasattr(penguin, "set_current_timestamp"):
                penguin.set_current_timestamp(timestamp)

            if bar_idx == len(sorted_timestamps) - 1:
                continue

            lookback_bars, required_history_bars = penguin_history_requirements(
                penguin,
                max_period,
            )
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
                pending_orders[(penguin_name, trade_bar_idx + t_plus_x)].extend(batch_orders)
                if t_plus_x == 0:
                    execute_orders(
                        penguin_name,
                        pending_orders.pop((penguin_name, trade_bar_idx), []),
                        quotes,
                        portfolio,
                        timestamp,
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
                
                mid_prices = list(full_history)[-lookback_bars:]
                spy_prices = price_history.get("SPY", [])
                spy_window = (
                    list(spy_prices)[-lookback_bars:]
                    if len(spy_prices) > lookback_bars
                    else list(spy_prices)
                )
                volumes = volume_history[symbol]
                volumes_window = (
                    list(volumes)[-lookback_bars:]
                    if len(volumes) > lookback_bars
                    else list(volumes)
                )
                bid, ask = quotes[symbol]
                
                try:
                    action, quantity = call_penguin_decide(
                        penguin,
                        symbol,
                        mid_prices,
                        bid,
                        ask,
                        portfolio,
                        spy_prices=spy_window,
                        volumes=volumes_window,
                    )
                    
                    if action in {"BUY", "SELL"} and quantity > 0:
                        pending_orders[(penguin_name, trade_bar_idx + t_plus_x)].append(
                            (symbol, action, quantity)
                        )
                        if t_plus_x == 0:
                            execute_orders(
                                penguin_name,
                                pending_orders.pop((penguin_name, trade_bar_idx), []),
                                quotes,
                                portfolio,
                                timestamp,
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
                symbol_prices = (
                    list(price_history[symbol])[-10:]
                    if symbol in price_history
                    else []
                )
                
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
                final_prices[symbol] = np.mean(list(price_history[symbol])[-10:])
        
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
    run_output_dir = get_run_output_dir(base_dir, RUN_LOG_NAME)
    run_artifacts_dir = run_output_dir / "artifacts"
    run_artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Training is executed inside `run_backtest` as Step 3b when enabled.
    
    ################ Run backtest ################
    results, trades_by_bar, bar_timestamps, _, _, _ = run_backtest(
        symbols=SYMBOLS,
        start_datetime=start_dt,
        end_datetime=end_dt,
        binning=BINNING,
        initial_capital=INITIAL_CAPITAL,
        transaction_cost=EXEC_TRANSACTION_COST,
        penguin_classes=ACTIVE_PENGUINS,
        artifacts_dir=run_artifacts_dir,
        training_step_allowed=TRAINING_STEP_ENABLED,
    )
    print("\nrun_backtest() returned; generating results...", flush=True)
    
    # Generate report
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    
    Evaluator.print_summary(results)

    Evaluator.save_results(
        results,
        None,
        run_output_dir,
        trades_by_bar,
        bar_timestamps,
        artifacts_dir=run_artifacts_dir,
    )

    # SMA artifact export intentionally disabled.
    print("\nSkipping SMA artifact export (no sma folder requested)")
    
    # Generate plots
    print("\nGenerating visualization...")
    run_plot = run_artifacts_dir / "capital_curves.png"
    
    # Get number of bars from first portfolio
    num_bars = None
    for portfolio, _ in results.values():
        num_bars = len(portfolio.value_history)
        break
    
    Evaluator.plot_capital_curves(
        results,
        run_plot,
        num_bars,
        BINNING,
        START_DATE,
        STOP_DATE,
        bar_timestamps,
        ACTIVE_SYMBOL_LIST,
    )
    
    # Generate PDF reports
    print("\nGenerating PDF report...")
    run_pdf = run_output_dir / "report.pdf"
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
            run_pdf,
            run_plot,
            num_bars,
            BINNING,
            START_DATE,
            STOP_DATE,
            bar_timestamps,
            run_artifacts_dir,
            ACTIVE_SYMBOL_LIST,
        )
    except Exception as e:
        print(f"\n⚠️  PDF generation failed: {e}")
        print("Skipping PDF report (fonts or rendering issue).")
    
    print(f"\n✅ Backtest complete!")

    if RUN_LOG_NAME != "0":
        print(f"\nLog saved to:  {run_output_dir}")
    else:
        print(f"\nTest run saved to: {run_output_dir}")
    print(f"  - report.pdf")
    print(f"  - artifacts/capital_curves.png")
    print(f"  - artifacts/json/curves_data.json")
    print(f"  - artifacts/json/metrics_summary.json")
    print(f"  - artifacts/trades_log.txt")
    print(f"  - artifacts/consistency_warnings.txt (if residual jumps)")
    if SAVE_CSV:
        print(f"  - artifacts/csv/*_summary.csv")
    
    print(f"\n{'='*80}")
    if RUN_LOG_NAME != "0":
        print("Run archived in run_log")
    else:
        print("Run saved in run_test")

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
