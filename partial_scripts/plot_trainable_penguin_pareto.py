"""Plot training performance against distance to the best parameter set.

Set `LOGFILE_DIR` to the directory that contains `trainable_penguin_training.log`
files, then run this script to generate a scatter plot of trial performance vs.
parameter distance to the best trial for each strategy.
"""

from __future__ import annotations

import argparse
import math
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.ticker import MaxNLocator


# Update this directory when you want to point the script at a different run.
LOGFILE_DIR = Path("/home/hd/hd_hd/hd_qp268/Penguin-Capitalist/run_log/ManualTuning_St100_t24-267/artifacts")
LOGFILE_NAME = "trainable_penguin_training.log"
OUTPUT_NAME = "trainable_penguin_pareto_distance.pdf"

# Use the optimization score from the log by default. Switch to
# "relative_profit" if you want the raw training PnL on the y-axis instead.
Y_METRIC = "objective"

# Set this to "BEST" to measure distance to the best parameter vector for the
# strategy, or "ZERO" to measure distance to the origin.
RELATIVE_TO = "BEST"


TRIAL_RE = re.compile(r"^\s*Trial\s+(?P<trial>\d+):")
STRATEGY_RE = re.compile(r"^\s*Optimizing\s+(?P<strategy>\S+)\s*$")
PARAMS_RE = re.compile(r"^\s*params=(?P<params>.+?)\s*$")
RESULT_RE = re.compile(
    r"^\s*relative_profit=\$(?P<relative_profit>[-\d,\.]+),\s*"
    r"absolute_profit=\$(?P<absolute_profit>[-\d,\.]+),\s*"
    r"buys=(?P<buys>\d+),\s*"
    r"score=\((?P<score>[^)]+)\),\s*"
    r"objective=(?P<objective>[-\d,\.]+)"
)
BEST_RE = re.compile(r"^\s*Best\s+(?P<strategy>[^:]+):\s+.*params=(?P<params>.+?)\s*$")


def parse_number(raw_value: str) -> float | int | str:
    cleaned = raw_value.strip().replace("$", "").replace(",", "")
    try:
        number = float(cleaned)
    except ValueError:
        return raw_value.strip()
    return int(number) if number.is_integer() else number


def parse_params(raw_params: str) -> dict[str, float | int | str]:
    params: dict[str, float | int | str] = {}
    for part in raw_params.split(","):
        if "=" not in part:
            continue
        key, raw_value = part.split("=", 1)
        params[key.strip()] = parse_number(raw_value)
    return params


def normalized_l2_distance(
    current: dict[str, float | int | str],
    relative_to: dict[str, float | int | str] | None,
) -> float:
    if not current:
        return float("nan")

    squared_distance = 0.0
    reference = relative_to or {}
    for key in sorted(set(current) | set(reference)):
        current_value = current.get(key)
        reference_value = reference.get(key, 0.0)
        try:
            current_float = float(current_value)
            reference_float = float(reference_value)
        except (TypeError, ValueError):
            continue
        squared_distance += (current_float - reference_float) ** 2
    return math.sqrt(squared_distance)


def parse_log_file(log_file: Path, relative_to: str) -> list[dict[str, object]]:
    trials: list[dict[str, object]] = []
    current_strategy = "unknown"
    current_trial: dict[str, object] | None = None
    best_params_by_strategy: dict[str, dict[str, float | int | str]] = {}
    best_trial_number_by_strategy: dict[str, int] = {}

    for raw_line in log_file.read_text(encoding="utf-8", errors="replace").splitlines():
        strategy_match = STRATEGY_RE.match(raw_line)
        if strategy_match:
            current_strategy = strategy_match.group("strategy")
            continue

        best_match = BEST_RE.match(raw_line)
        if best_match:
            strategy = best_match.group("strategy").strip()
            best_params_by_strategy[strategy] = parse_params(best_match.group("params"))
            continue

        trial_match = TRIAL_RE.match(raw_line)
        if trial_match:
            current_trial = {
                "strategy": current_strategy,
                "trial": int(trial_match.group("trial")),
            }
            continue

        if current_trial is None:
            continue

        params_match = PARAMS_RE.match(raw_line)
        if params_match:
            current_trial["params"] = parse_params(params_match.group("params"))
            continue

        result_match = RESULT_RE.match(raw_line)
        if result_match:
            current_trial["relative_profit"] = parse_number(result_match.group("relative_profit"))
            current_trial["absolute_profit"] = parse_number(result_match.group("absolute_profit"))
            current_trial["objective"] = parse_number(result_match.group("objective"))
            current_trial["buys"] = int(result_match.group("buys"))
            strategy = str(current_trial["strategy"])
            current_score = float(current_trial["objective"])
            previous_best_trial = best_trial_number_by_strategy.get(strategy)
            if previous_best_trial is None:
                best_trial_number_by_strategy[strategy] = int(current_trial["trial"])
            else:
                previous_best = next(
                    (trial for trial in trials if trial["strategy"] == strategy and int(trial["trial"]) == previous_best_trial),
                    None,
                )
                if previous_best is not None and current_score > float(previous_best["objective"]):
                    best_trial_number_by_strategy[strategy] = int(current_trial["trial"])
            trials.append(current_trial)
            current_trial = None

    relative_to_mode = relative_to.upper()
    for trial in trials:
        strategy = str(trial["strategy"])
        if relative_to_mode == "ZERO":
            optimal_params: dict[str, float | int | str] | None = {}
        else:
            optimal_params = best_params_by_strategy.get(strategy, {})
        trial["distance"] = normalized_l2_distance(
            trial.get("params", {}),
            optimal_params,
        )

    for trial in trials:
        strategy = str(trial["strategy"])
        trial["is_best"] = int(trial["trial"]) == best_trial_number_by_strategy.get(strategy)

    return trials


def plot_strategy_trials(strategy: str, trials: list[dict[str, object]], title_suffix: str = ""):
    if not trials:
        raise ValueError("No completed trials were found in the training log.")

    fig, ax = plt.subplots(figsize=(11, 7))

    palette = list(plt.get_cmap("tab10").colors)
    color = palette[0]

    regular_trials = [trial for trial in trials if not trial.get("is_best")]
    best_trials = [trial for trial in trials if trial.get("is_best")]

    if regular_trials:
        x_values = [float(trial["distance"]) for trial in regular_trials]
        y_values = [float(trial[Y_METRIC]) for trial in regular_trials]
        trial_labels = [int(trial["trial"]) for trial in regular_trials]

        ax.scatter(
            x_values,
            y_values,
            s=55,
            alpha=0.85,
            label=strategy,
            color=color,
            edgecolors="black",
            linewidths=0.5,
        )

        for x_value, y_value, trial_label in zip(x_values, y_values, trial_labels):
            ax.annotate(
                str(trial_label),
                (x_value, y_value),
                textcoords="offset points",
                xytext=(5, 4),
                fontsize=8,
            )

    if best_trials:
        best_trial = best_trials[0]
        ax.scatter(
            [float(best_trial["distance"])],
            [float(best_trial[Y_METRIC])],
            s=130,
            color="red",
            edgecolors="black",
            linewidths=1.0,
            zorder=5,
            label="Best trial",
        )
        ax.annotate(
            f"Best {int(best_trial['trial'])}",
            (float(best_trial["distance"]), float(best_trial[Y_METRIC])),
            textcoords="offset points",
            xytext=(8, 8),
            fontsize=9,
            fontweight="bold",
            color="red",
        )

    title = "Trainable Penguin Pareto Distance Plot"
    if title_suffix:
        title = f"{title} ({title_suffix})"
    ax.set_title(title)
    ax.set_xlabel("L2 distance to best parameters")
    ax.set_ylabel("Training objective" if Y_METRIC == "objective" else "Relative profit ($)")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()

    return fig


def plot_training_performance(
    trials_by_strategy: dict[str, list[dict[str, object]]],
    title_suffix: str = "",
):
    """Plot each strategy's benchmark-relative performance by training step."""
    fig, ax = plt.subplots(figsize=(11, 7))

    for strategy, trials in sorted(trials_by_strategy.items()):
        x_values = [int(trial["trial"]) for trial in trials]
        y_values = [float(trial["relative_profit"]) for trial in trials]
        ax.plot(
            x_values,
            y_values,
            marker="o",
            linewidth=1.3,
            markersize=3.5,
            label=strategy,
        )

    title = "Training Performance Relative to Benchmark"
    if title_suffix:
        title = f"{title} ({title_suffix})"
    ax.set_title(title)
    ax.set_xlabel("Training step")
    ax.set_ylabel("Performance relative to benchmark ($)")
    ax.xaxis.set_major_locator(MaxNLocator(nbins=10, integer=True))
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    return fig


def find_log_files(log_dir: Path) -> list[Path]:
    if log_dir.is_file():
        return [log_dir]
    if not log_dir.exists():
        raise FileNotFoundError(f"Log directory does not exist: {log_dir}")
    return sorted(log_dir.rglob(LOGFILE_NAME))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--logfile-dir",
        type=Path,
        default=LOGFILE_DIR,
        help="Directory that contains trainable_penguin_training.log files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output PDF path. Defaults to the run directory when available.",
    )
    parser.add_argument(
        "--relative-to",
        choices=["BEST", "ZERO"],
        default=RELATIVE_TO,
        help="Measure distance to the best parameter vector or the origin.",
    )
    args = parser.parse_args()

    log_files = find_log_files(args.logfile_dir)
    if not log_files:
        raise FileNotFoundError(f"No {LOGFILE_NAME} files found under {args.logfile_dir}")

    if args.output is not None:
        output_path = args.output
    elif args.logfile_dir.is_dir() and args.logfile_dir.name == "artifacts":
        output_path = args.logfile_dir.parent / OUTPUT_NAME
    elif args.logfile_dir.is_file():
        output_path = args.logfile_dir.with_name(OUTPUT_NAME)
    else:
        output_path = args.logfile_dir / OUTPUT_NAME

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with PdfPages(output_path) as pdf:
        for log_file in log_files:
            trials = parse_log_file(log_file, args.relative_to)
            try:
                log_label = log_file.relative_to(args.logfile_dir).as_posix()
            except ValueError:
                log_label = log_file.name

            trials_by_strategy: dict[str, list[dict[str, object]]] = {}
            for trial in trials:
                strategy = str(trial.get("strategy", "unknown"))
                trials_by_strategy.setdefault(strategy, []).append(trial)

            performance_fig = plot_training_performance(
                trials_by_strategy,
                title_suffix=log_label,
            )
            pdf.savefig(performance_fig, bbox_inches="tight")
            plt.close(performance_fig)
            print(f"Added performance overview :: {log_file}")

            for strategy in sorted(trials_by_strategy):
                fig = plot_strategy_trials(
                    strategy,
                    trials_by_strategy[strategy],
                    title_suffix=f"{log_label} | {args.relative_to}",
                )
                pdf.savefig(fig, bbox_inches="tight")
                plt.close(fig)
                print(f"Added {log_file} :: {strategy}")

    print(f"Saved {output_path}")


if __name__ == "__main__":
    main()