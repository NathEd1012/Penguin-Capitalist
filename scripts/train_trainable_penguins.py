"""Standalone training entry point for the trainable penguin strategies."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

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
    _train_trainable_penguins,
    _training_benchmark_symbol,
    parse_datetime_string,
    prepare_training_context,
)
from scripts.plotting import create_training_pareto_pdf


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
