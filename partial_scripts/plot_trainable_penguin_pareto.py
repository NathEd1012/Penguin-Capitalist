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


# Update this directory when you want to point the script at a different run.
LOGFILE_DIR = Path("/home/hd/hd_hd/hd_qp268/Penguin-Capitalist/run_log/ManualTuning_St100_t24-267/artifacts")
LOGFILE_NAME = "trainable_penguin_training.log"
OUTPUT_NAME = "trainable_penguin_pareto_distance.png"

# Use the optimization score from the log by default. Switch to
# "relative_profit" if you want the raw training PnL on the y-axis instead.
Y_METRIC = "objective"


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


def normalized_l2_distance(current: dict[str, float | int | str], optimal: dict[str, float | int | str]) -> float:
    if not current or not optimal:
        return float("nan")

    squared_distance = 0.0
    for key in sorted(set(current) | set(optimal)):
        current_value = current.get(key)
        optimal_value = optimal.get(key)
        try:
            current_float = float(current_value)
            optimal_float = float(optimal_value)
        except (TypeError, ValueError):
            continue
        squared_distance += (current_float - optimal_float) ** 2
    return math.sqrt(squared_distance)


def parse_log_file(log_file: Path) -> list[dict[str, object]]:
    trials: list[dict[str, object]] = []
    current_strategy = "unknown"
    current_trial: dict[str, object] | None = None
    best_params_by_strategy: dict[str, dict[str, float | int | str]] = {}

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
            trials.append(current_trial)
            current_trial = None

    for trial in trials:
        strategy = str(trial["strategy"])
        optimal_params = best_params_by_strategy.get(strategy, {})
        trial["distance"] = normalized_l2_distance(
            trial.get("params", {}),
            optimal_params,
        )

    return trials


def plot_trials(trials: list[dict[str, object]], output_path: Path) -> None:
    if not trials:
        raise ValueError("No completed trials were found in the training log.")

    fig, ax = plt.subplots(figsize=(11, 7))

    strategies = sorted({str(trial["strategy"]) for trial in trials})
    palette = list(plt.get_cmap("tab10").colors)
    color_map = {strategy: palette[index % len(palette)] for index, strategy in enumerate(strategies)}

    for strategy in strategies:
        strategy_trials = [trial for trial in trials if trial["strategy"] == strategy]
        x_values = [float(trial["distance"]) for trial in strategy_trials]
        y_values = [float(trial[Y_METRIC]) for trial in strategy_trials]
        trial_labels = [int(trial["trial"]) for trial in strategy_trials]

        ax.scatter(
            x_values,
            y_values,
            s=55,
            alpha=0.85,
            label=strategy,
            color=color_map[strategy],
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

    ax.set_title("Trainable Penguin Pareto Distance Plot")
    ax.set_xlabel("L2 distance to best parameters")
    ax.set_ylabel("Training objective" if Y_METRIC == "objective" else "Relative profit ($)")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


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
        help="Output image path. Defaults next to the first log file found.",
    )
    args = parser.parse_args()

    log_files = find_log_files(args.logfile_dir)
    if not log_files:
        raise FileNotFoundError(f"No {LOGFILE_NAME} files found under {args.logfile_dir}")

    for log_file in log_files:
        trials = parse_log_file(log_file)
        output_path = args.output or log_file.with_name(OUTPUT_NAME)
        plot_trials(trials, output_path)
        print(f"Saved {output_path}")


if __name__ == "__main__":
    main()