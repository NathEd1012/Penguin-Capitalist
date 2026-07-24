"""Standalone training entry point for the trainable penguin strategies."""
from contextlib import redirect_stderr, redirect_stdout
import json
import os
import random
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    INITIAL_CAPITAL,
    BINNING,
    START_DATE,
    STOP_DATE,
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
from run_simulation import (
    _format_trainable_params,
    _format_trainable_parameter_delta_report,
    _training_benchmark_symbol,
    _training_symbol_subset,
    _training_window_subset,
    _training_profit_amount,
    _score_training_candidate,
    _suggest_bayesian_trainable_params,
    _objective_from_score,
    _format_training_timestamp,
    _format_training_symbols,
    _format_param_changes,
    parse_datetime_string,
    prepare_training_context,
    run_backtest,
)
from penguins import SP500
from scripts.plotting import create_training_pareto_pdf


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
                    transaction_cost=transaction_cost,
                    penguin_classes=[candidate, SP500],
                    training_step_allowed=False,
                )

            candidate_metrics = results[candidate.name][1]
            benchmark_metrics = results[SP500().name][1]
            profit_amount = float(candidate_metrics.get("total_return", 0.0))
            benchmark_profit_amount = float(benchmark_metrics.get("total_return", 0.0))
            relative_profit_amount = _training_profit_amount(candidate_metrics, benchmark_metrics, TRAINING_RELATIVE_TO)
            score = _score_training_candidate(candidate_metrics, benchmark_metrics, transaction_cost, TRAINING_RELATIVE_TO)
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


def main() -> None:
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass

    try:
        start_dt = parse_datetime_string(START_DATE)
        end_dt = parse_datetime_string(STOP_DATE)
    except ValueError as exc:
        print(f"Error parsing config dates: {exc}")
        print(f"  START_DATE: {START_DATE}")
        print(f"  STOP_DATE: {STOP_DATE}")
        sys.exit(1)

    print("\n" + "=" * 80)
    print("PENGUIN CAPITALIST - TRAINABLE PENGUIN TRAINING")
    print("=" * 80)

    base_dir = Path(__file__).resolve().parent.parent
    current_dir = base_dir / "run_current"
    current_artifacts_dir = current_dir / "artifacts"
    current_artifacts_dir.mkdir(parents=True, exist_ok=True)

    print("Step 1: Preparing training data...")
    valid_symbols, _sorted_timestamps, tradeable_timestamps, quality_report_text = prepare_training_context(
        symbols=SYMBOLS,
        start_datetime=start_dt,
        end_datetime=end_dt,
        binning=BINNING,
        penguin_classes=TRAINABLE_PENGUINS,
    )

    if quality_report_text:
        warnings_path = current_artifacts_dir / "consistency_warnings.txt"
        with open(warnings_path, "w", encoding="utf-8") as handle:
            handle.write(quality_report_text)
            handle.write("\n")

    active_trainables = list(dict.fromkeys(TRAINABLE_PENGUINS))
    if not active_trainables:
        print("No trainable penguins are configured.")
        sys.exit(1)

    print(
        f"\nStep 2: Training {len(active_trainables)} trainable strategy(ies) "
        f"for the configured optimization rounds..."
    )
    training_start = datetime.now(timezone.utc)
    trained_parameters, training_log_lines, training_parameter_history, training_pareto_history = _train_trainable_penguins(
        trainable_strategy_classes=active_trainables,
        symbols=valid_symbols,
        tradeable_timestamps=tradeable_timestamps,
        binning=BINNING,
        initial_capital=INITIAL_CAPITAL,
        transaction_cost=TRAINING_TRANSACTION_COST,
    )
    training_end = datetime.now(timezone.utc)
    training_elapsed = training_end - training_start
    total_seconds = int(training_elapsed.total_seconds())
    hrs, rem = divmod(total_seconds, 3600)
    mins, secs = divmod(rem, 60)
    training_duration_str = f"{hrs}:{mins:02d}:{secs:02d}"

    training_output_dir = current_artifacts_dir / "json"
    training_output_dir.mkdir(parents=True, exist_ok=True)
    benchmark_symbol = _training_benchmark_symbol(TRAINING_RELATIVE_TO)
    training_output_path = training_output_dir / TRAINING_RESULTS_FILENAME
    training_parameter_log_path = training_output_dir / TRAINING_PARAMETER_LOG_FILENAME
    training_parameter_delta_path = current_artifacts_dir / TRAINING_PARAMETER_DELTA_FILENAME
    training_log_path = current_artifacts_dir / TRAINING_LOG_FILENAME
    training_pareto_path = current_artifacts_dir.parent / TRAINING_PARETO_FILENAME

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


if __name__ == "__main__":
    main()
