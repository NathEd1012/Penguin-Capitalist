"""Compare each strategy's training winner and validation winner on its original test window.

The shell launcher discovers MasterPeng* folders and submits one Slurm array task
per run. This entry point also supports a single run and a read-only --dry-run.
Identical parameter dictionaries produce only one curve. When every pair matches,
the original saved test curves are replotted without running the backtest again.
"""

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import sys


PROJECT_DIR = Path(__file__).resolve().parents[1]
REPORT_NAME = "tra_vs_val_report.pdf"
PARAMETER_LOG = "trainable_penguin_parameter_log.json"


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def discover_runs(run_log, pattern="MasterPeng*"):
    """Find nested runs under matching experiment folders, ignoring unfinished training."""
    runs = set()
    for folder in sorted(run_log.glob(pattern)):
        if not folder.is_dir():
            continue
        for selection in folder.rglob("artifacts/json/validation_selection.json"):
            if (selection.parent / PARAMETER_LOG).is_file():
                runs.add(selection.parents[2].resolve())
    return sorted(runs)


def score_key(trial, field):
    score = trial.get(field)
    if field == "score" and not score:
        score = [trial.get("objective_value")]
    if not isinstance(score, (list, tuple)) or not score:
        raise ValueError(f"Missing {field} for trial {trial.get('trial')}")
    values = tuple(float(value) for value in score)
    if not all(math.isfinite(value) for value in values):
        raise ValueError(f"Non-finite {field} for trial {trial.get('trial')}")
    return values


def select_winners(run_dir):
    """Use the same lexicographic score ranking as training and validation."""
    json_dir = run_dir / "artifacts/json"
    history = load_json(json_dir / PARAMETER_LOG).get("trial_history", [])
    validation = load_json(json_dir / "validation_selection.json").get("selection", {})
    by_strategy = {}
    for trial in history:
        if trial.get("status") == "completed" and trial.get("params"):
            by_strategy.setdefault(trial["strategy"], []).append(trial)
    strategies = sorted(set(by_strategy) | set(validation))
    if not strategies:
        raise ValueError(f"No completed training/validation candidates in {run_dir}")
    winners = []
    for strategy in strategies:
        training_trials = by_strategy.get(strategy, [])
        validation_trials = [trial for trial in validation.get(strategy, []) if trial.get("params")]
        if not training_trials or not validation_trials:
            raise ValueError(f"Missing training or validation candidates for {strategy} in {run_dir}")
        training = max(training_trials, key=lambda trial: score_key(trial, "score"))
        validated = max(validation_trials, key=lambda trial: score_key(trial, "validation_score"))
        winners.append({
            "strategy": strategy,
            "training": training,
            "validation": validated,
            "same_parameters": training["params"] == validated["params"],
        })
    return winners


def execution_settings(run_dir):
    """Read the original execution settings rather than using today's config defaults."""
    fields = {
        "start": "Start Time (UTC)", "stop": "End Time (UTC)",
        "binning": "Binning", "initial_capital": "Initial Capital",
        "transaction_cost": "Transaction Cost", "symbol_list": "Symbol List",
        "t_plus_x": "T_PLUS_X (bars)",
    }
    log_path = run_dir / "artifacts/log.out"
    settings = {}
    # The configuration precedes all backtest data and can be read without loading
    # a multi-gigabyte execution log into memory.
    with log_path.open(encoding="utf-8", errors="replace") as log:
        for line in log:
            for key, label in fields.items():
                match = re.match(r"^" + re.escape(label) + r":\s*(.*?)\s*$", line)
                if match and key not in settings:
                    settings[key] = match.group(1)
            if len(settings) == len(fields):
                break
    missing = fields.keys() - settings.keys()
    if missing:
        raise ValueError(f"Missing execution settings in {log_path}: {', '.join(sorted(missing))}")
    for key in ("initial_capital", "transaction_cost"):
        settings[key] = float(settings[key].replace("$", "").replace(",", ""))
    settings["t_plus_x"] = int(settings["t_plus_x"])
    if parse_datetime(settings["stop"]) <= parse_datetime(settings["start"]):
        raise ValueError(f"Invalid execution window in {log_path}")
    return settings


def parse_datetime(value):
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def report_entries(winners):
    entries = []
    for winner in winners:
        strategy = winner["strategy"]
        training = {**winner["training"], "strategy": strategy}
        validated = {**winner["validation"], "strategy": strategy}
        if winner["same_parameters"]:
            entries.append((f"{strategy}_TrainingAndValidation", training))
        else:
            entries.extend([
                (f"{strategy}_BestValidation", validated),
                (f"{strategy}_BestTraining", training),
            ])
    return entries


def saved_primary_results(run_dir, winners):
    """Reuse only the original primary strategies; omit all saved secondary variants."""
    json_dir = run_dir / "artifacts/json"
    curves = load_json(json_dir / "curves_data.json")
    metrics = load_json(json_dir / "metrics_summary.json")
    timestamps = load_json(json_dir / "curve_timestamps.json")
    names = [(f"{winner['strategy']}_TrainingAndValidation",
              winner["validation"].get("penguin_name", winner["strategy"])) for winner in winners]
    names.append(("SP500", "SP500"))
    selected_curves, selected_metrics, selected_timestamps = {}, {}, {}
    for target, source in names:
        if not curves.get(source) or source not in metrics or source not in timestamps:
            raise ValueError(f"Saved primary results missing for {source} in {run_dir}")
        if len(curves[source]) != len(timestamps[source]):
            raise ValueError(f"Saved curve/timestamp length mismatch for {source}")
        selected_curves[target] = curves[source]
        selected_metrics[target] = metrics[source]
        selected_timestamps[target] = [parse_datetime(value) for value in timestamps[source]]
    return selected_curves, selected_metrics, selected_timestamps


def reexecute(run_dir, winners, settings, artifacts_dir):
    if str(PROJECT_DIR) not in sys.path:
        sys.path.insert(0, str(PROJECT_DIR))
    # Set environment-backed settings before importing the simulation/config modules.
    os.environ.update({
        "ACTIVE_SYMBOL_LIST": settings["symbol_list"],
        "FIXED_START": settings["start"], "FIXED_STOP": settings["stop"],
        "BINNING": settings["binning"], "T_PLUS_X": str(settings["t_plus_x"]),
        "FIXED_EXEC_TC": str(settings["transaction_cost"]),
    })
    import penguins
    from backtest.evaluator import Evaluator
    from config import SYMBOL_LISTS
    from run_simulation import run_backtest

    instances = []
    for name, trial in report_entries(winners):
        strategy_class = getattr(penguins, trial["strategy"])
        instance = strategy_class(name=name, **trial["params"])
        # Some strategy constructors normalize names; keep the two picks distinct.
        instance.name = name
        instances.append(instance)
    instances.append(penguins.SP500())
    results, trades, timestamps, _, _, quality_report = run_backtest(
        symbols=SYMBOL_LISTS[settings["symbol_list"]],
        start_datetime=parse_datetime(settings["start"]),
        end_datetime=parse_datetime(settings["stop"]),
        binning=settings["binning"], initial_capital=settings["initial_capital"],
        transaction_cost=settings["transaction_cost"], penguin_classes=instances,
        artifacts_dir=artifacts_dir, training_step_allowed=False,
        t_plus_x=settings["t_plus_x"],
    )
    expected_names = {instance.name for instance in instances}
    if set(results) != expected_names:
        raise RuntimeError(f"Backtest did not return all selected strategies: {expected_names - set(results)}")
    Evaluator.save_results(results, None, run_dir, trades, timestamps, artifacts_dir=artifacts_dir)
    if quality_report:
        (artifacts_dir / "consistency_warnings.txt").write_text(quality_report + "\n", encoding="utf-8")
    return ({name: portfolio.value_history for name, (portfolio, _) in results.items()},
            {name: metrics for name, (_, metrics) in results.items()}, timestamps)


def render_report(path, winners, settings, curves, metrics, timestamps):
    """Plot an overview and one comparison page per strategy, with saved test metrics."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    for name, values in curves.items():
        if not values or len(values) != len(timestamps[name]):
            raise ValueError(f"Empty or misaligned execution curve for {name}")

    def plot_curves(ax, names):
        for name in names:
            ax.plot(timestamps[name], curves[name], label=name,
                    linestyle="--" if name.endswith("_BestTraining") else "-", linewidth=1.2)
        ax.axhline(settings["initial_capital"], color="gray", linestyle=":", linewidth=0.8)
        ax.set_ylabel("Total capital ($)")
        ax.set_xlabel("Test date (UTC)")
        locator = mdates.AutoDateLocator()
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
        ax.grid(alpha=0.25)
        ax.legend(fontsize=8)

    with PdfPages(path) as pdf:
        fig, ax = plt.subplots(figsize=(14, 8))
        plot_curves(ax, curves)
        ax.set_title("Best training vs. best validation: test execution\n"
                     f"{settings['start']} to {settings['stop']} | {settings['symbol_list']}")
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        entries = report_entries(winners)
        for winner in winners:
            strategy = winner["strategy"]
            names = [name for name, _ in entries if name.startswith(strategy + "_")]
            fig, ax = plt.subplots(figsize=(14, 8))
            plot_curves(ax, names + ["SP500"])
            fig.suptitle(strategy + (": same training and validation parameters"
                                    if winner["same_parameters"] else ": selected parameter comparison"))
            lines = [f"Training winner: trial {winner['training']['trial']}    |    "
                     f"Validation winner: trial {winner['validation']['trial']}"]
            for name in names + ["SP500"]:
                values = metrics[name]
                lines.append(f"{name}: test return {values['return_pct']:+.2f}% | "
                             f"final ${values['final_value']:,.2f} | "
                             f"drawdown {values['max_drawdown']:.2f}% | "
                             f"trades {values['total_trades']}")
            fig.text(0.08, 0.9, "\n".join(lines), va="top", fontsize=9)
            fig.subplots_adjust(top=0.73, bottom=0.12, left=0.08, right=0.97)
            pdf.savefig(fig)
            plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run-dir", type=Path, help="One original run to compare")
    mode.add_argument("--list-runs", action="store_true", help="Print discovered absolute run paths")
    parser.add_argument("--run-log", type=Path, default=PROJECT_DIR / "run_log")
    parser.add_argument("--folder-pattern", default="MasterPeng*")
    parser.add_argument("--dry-run", action="store_true", help="Print settings and selections without execution or writes")
    args = parser.parse_args()
    if args.list_runs:
        for run_dir in discover_runs(args.run_log.expanduser().resolve(), args.folder_pattern):
            print(run_dir)
        return
    run_dir = args.run_dir.expanduser().resolve()
    winners = select_winners(run_dir)
    settings = execution_settings(run_dir)
    all_same = all(winner["same_parameters"] for winner in winners)
    mode_name = "replot_saved_results" if all_same else "reexecute_distinct_winners"
    print(f"Run: {run_dir}\nMode: {mode_name}\nTest: {settings['start']} to {settings['stop']}")
    for winner in winners:
        print(f"  {winner['strategy']}: training trial {winner['training']['trial']}, "
              f"validation trial {winner['validation']['trial']}"
              + (" (identical parameters; one curve)" if winner["same_parameters"] else " (two curves)"))
    if args.dry_run:
        return
    artifacts_dir = run_dir / "artifacts/tra_vs_val"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    if all_same:
        try:
            curves, metrics, timestamps = saved_primary_results(run_dir, winners)
        except (FileNotFoundError, ValueError, KeyError) as exc:
            print(f"Saved primary results unavailable ({exc}); re-executing unique winners.")
            mode_name = "reexecute_distinct_winners"
            curves, metrics, timestamps = reexecute(run_dir, winners, settings, artifacts_dir)
    else:
        curves, metrics, timestamps = reexecute(run_dir, winners, settings, artifacts_dir)
    selection = {"source_run": str(run_dir), "mode": mode_name, "execution": settings, "winners": winners}
    (artifacts_dir / "selection.json").write_text(json.dumps(selection, indent=2) + "\n", encoding="utf-8")
    # Replace a previous comparison only after a complete PDF has been written.
    temporary_pdf = artifacts_dir / "tra_vs_val_report.pending.pdf"
    render_report(temporary_pdf, winners, settings, curves, metrics, timestamps)
    report_path = run_dir / REPORT_NAME
    temporary_pdf.replace(report_path)
    print(f"Saved {report_path}")


if __name__ == "__main__":
    main()
