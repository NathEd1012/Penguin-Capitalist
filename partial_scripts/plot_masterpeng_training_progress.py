"""Plot seed-averaged best-so-far MasterPeng training objectives at 50-step intervals.

From the project root (matplotlib is available in devel/python/3.13.1):
    python partial_scripts/plot_masterpeng_training_progress.py

Creates three strategy figures with five start-year panels each. All optimization
methods share each panel. Each seed contributes max(objective_value[1:N]) at
N = 50, 100, ..., 500; averaging happens AFTER finding these seed-level maxima.
The objective is relative profit versus SPY minus the saved activity penalty ($).
No backtests are rerun. All five seeds must have complete training histories.
"""

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import fmean, stdev

try:
    from .export_masterpeng_performance import METHODS, PROJECT, SEEDS, STRATEGIES, YEARS
except ImportError:
    from export_masterpeng_performance import METHODS, PROJECT, SEEDS, STRATEGIES, YEARS


DEFAULT_ROOT = PROJECT / "run_log/Done_usefull/MasterPeng_ALL_RUNS_TC1.0_TS500"
BASE_STRATEGIES = tuple(dict.fromkeys(base for base, _ in STRATEGIES))
CHECKPOINTS = tuple(range(50, 501, 50))
COLORS = ("#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00")
MARKERS = ("o", "s", "^", "D", "v")


def checkpoint_bests(history):
    """Return cumulative best objectives, counting skipped trials in the budget."""
    trials = {strategy: {} for strategy in BASE_STRATEGIES}
    for row in history:
        strategy, trial = row["strategy"], row["trial"]
        if strategy not in trials:
            raise ValueError(f"Unexpected training strategy: {strategy}")
        if type(trial) is not int or not 1 <= trial <= CHECKPOINTS[-1]:
            raise ValueError(f"Invalid trial number for {strategy}: {trial}")
        if trial in trials[strategy]:
            raise ValueError(f"Duplicate trial {trial} for {strategy}")
        value = None
        if row["status"] == "completed":
            value = row["objective_value"]
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value)):
                raise ValueError(f"Invalid objective for {strategy}, trial {trial}: {value}")
        elif row["status"] != "skipped":
            raise ValueError(f"Unexpected trial status for {strategy}, trial {trial}: {row['status']}")
        trials[strategy][trial] = value

    points = []
    for strategy, values in trials.items():
        missing = sorted(set(range(1, CHECKPOINTS[-1] + 1)) - values.keys())
        if missing:
            raise ValueError(f"Incomplete history for {strategy}; missing trials: {missing}")
        best = None
        for trial in range(1, CHECKPOINTS[-1] + 1):
            value = values[trial]
            if value is not None:
                best = value if best is None else max(best, value)
            if trial in CHECKPOINTS:
                if best is None:
                    raise ValueError(f"No completed trials for {strategy} by {trial} steps")
                points.append({"strategy": strategy, "training_steps": trial,
                               "best_objective": best})
    return points


def collect(root):
    records = []
    for year in YEARS:
        for method, _ in METHODS:
            for seed in SEEDS:
                run = root / f"Year{year}/RS_{seed}/MR_{year}_broad_{method}_500_RS_{seed}"
                source = run / "artifacts/json/trainable_penguin_parameter_log.json"
                data = json.loads(source.read_text(encoding="utf-8"))
                if data.get("iterations") != CHECKPOINTS[-1] or data.get("relative_to") != "SPY":
                    raise ValueError(f"Expected 500 training steps relative to SPY: {source}")
                try:
                    points = checkpoint_bests(data["trial_history"])
                except (ValueError, KeyError) as error:
                    raise ValueError(f"{source}: {error}") from error
                records.extend({"year": year, "method": method, "seed": seed,
                                **point, "source_file": str(source)} for point in points)
    return records


def summarize(records):
    """Average per-seed maxima within each year/method/strategy/checkpoint."""
    groups = defaultdict(dict)
    for row in records:
        key = tuple(row[field] for field in ("strategy", "year", "method", "training_steps"))
        seed = row["seed"]
        if seed not in SEEDS or seed in groups[key]:
            raise ValueError(f"Unexpected or duplicate seed {seed} for {key}")
        value = row["best_objective"]
        if not math.isfinite(value):
            raise ValueError(f"Invalid best objective for {key}, seed {seed}")
        groups[key][seed] = value
    cells = []
    for (strategy, year, method, steps), seeds in sorted(groups.items()):
        if set(seeds) != set(SEEDS):
            raise ValueError(f"Missing seeds for {(strategy, year, method, steps)}")
        values = list(seeds.values())
        cells.append({"strategy": strategy, "year": year, "method": method,
                      "training_steps": steps, "n": len(values),
                      "mean_best_objective": fmean(values),
                      "standard_error": stdev(values) / math.sqrt(len(values))})
    return cells


def write_plots(output, cells):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.ticker import StrMethodFormatter

    lookup = {(c["strategy"], c["year"], c["method"], c["training_steps"]): c for c in cells}
    combined = output / "masterpeng_training_progress.pdf"
    with PdfPages(combined) as pdf:
        for strategy in BASE_STRATEGIES:
            figure, axes = plt.subplots(2, 3, figsize=(17, 10))
            figure.suptitle(f"{strategy} | best training performance", fontsize=22, weight="bold", y=0.96)
            figure.text(0.5, 0.91,
                        "Cumulative best at 50, 100, …, 500 training steps · mean ± standard error across seeds",
                        ha="center", fontsize=13, color="#43596a")
            handles = []
            for index, (year, axis) in enumerate(zip(YEARS, axes.flat)):
                for (method, label), color, marker in zip(METHODS, COLORS, MARKERS):
                    points = [lookup[(strategy, year, method, step)] for step in CHECKPOINTS]
                    means = [point["mean_best_objective"] for point in points]
                    errors = [point["standard_error"] for point in points]
                    line, = axis.plot(CHECKPOINTS, means, color=color, marker=marker,
                                      label=label, linewidth=2, markersize=4)
                    axis.fill_between(CHECKPOINTS,
                                      [mean - error for mean, error in zip(means, errors)],
                                      [mean + error for mean, error in zip(means, errors)],
                                      color=color, alpha=0.10, linewidth=0)
                    if index == 0:
                        handles.append(line)
                axis.set_title(f"Start year {year} · n = {len(SEEDS)} seeds / method",
                               fontsize=12, weight="bold", pad=10)
                axis.set_xticks(CHECKPOINTS)
                axis.set_xlim(40, 510)
                axis.set_xlabel("Training steps", fontsize=11)
                axis.set_ylabel("Best training objective ($)", fontsize=11)
                axis.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
                axis.tick_params(labelsize=9)
                axis.grid(alpha=0.22)
                axis.spines[["top", "right"]].set_visible(False)
            notes = axes.flat[-1]
            notes.axis("off")
            legend = notes.legend(handles=handles, loc="upper left", frameon=False,
                                  fontsize=12, title="Optimization method", title_fontsize=13)
            legend.get_title().set_weight("bold")
            notes.text(0.025, 0.36,
                       "Each point = mean across seeds of the best\n"
                       "objective among trials 1 through N.\n\n"
                       "Objective = profit relative to SPY\n"
                       "minus the activity penalty, in dollars.\n\n"
                       f"Seeds: {', '.join(map(str, SEEDS))}\n"
                       "Shading: ±1 standard error; higher is better.",
                       transform=notes.transAxes, va="top", fontsize=11,
                       color="#43596a", linespacing=1.5)
            figure.subplots_adjust(left=0.075, right=0.975, bottom=0.08, top=0.84,
                                   hspace=0.43, wspace=0.30)
            stem = output / f"masterpeng_training_progress_{strategy}"
            figure.savefig(stem.with_suffix(".png"), dpi=180, facecolor="white")
            figure.savefig(stem.with_suffix(".pdf"), facecolor="white")
            pdf.savefig(figure, facecolor="white")
            plt.close(figure)
    return combined


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT,
                        help="MasterPeng collection containing Year*/RS_*/MR_* runs.")
    parser.add_argument("--output-dir", type=Path,
                        help="Default: performance_tables/training_progress beneath --root.")
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    records = collect(root)
    cells = summarize(records)
    output = (args.output_dir.expanduser().resolve() if args.output_dir
              else root / "performance_tables/training_progress")
    output.mkdir(parents=True, exist_ok=True)
    combined = write_plots(output, cells)
    write_csv(output / "masterpeng_training_progress_seed_checkpoints.csv", records)
    write_csv(output / "masterpeng_training_progress_means.csv", cells)
    (output / "masterpeng_training_progress.json").write_text(json.dumps({
        "root": str(root), "checkpoints": CHECKPOINTS, "seeds": SEEDS,
        "years": YEARS, "strategies": BASE_STRATEGIES, "methods": METHODS,
        "metric": "objective_value", "units": "USD",
        "objective": "profit relative to SPY minus activity penalty",
        "aggregation": "per year and method: mean over seeds of max(objective_value for trials 1..N)",
        "standard_error": "sample standard deviation of seed maxima / sqrt(n), ddof=1",
        "cells": cells,
    }, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Saved {combined} (3 pages), three strategy PDFs/PNGs, and CSV/JSON statistics.")
    print(f"Validated {len(records)} seed checkpoints; all {len(SEEDS)} seeds in every mean.")


if __name__ == "__main__":
    main()
