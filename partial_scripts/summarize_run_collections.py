"""Create MasterPeng-style performance PDFs directly from saved run collections.

Usage:
    python partial_scripts/summarize_run_collections.py run_log/GP_BP_UCB_mb100_p0.1_TC1.0_TS500
    python partial_scripts/summarize_run_collections.py run_log/Lower_Mean_GP_1.0_TS500 --methods gpei gpucb gpbpucb

Each collection gets absolute and SPY-relative PDFs at its root, with seed-level
CSV and cell statistics in performance_tables. Missing runs are excluded from
averages and displayed through n = completed / expected seeds.
"""

import argparse
import csv
import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

try:
    from .export_masterpeng_performance import FIELDS, NUMERIC_FIELDS, STRATEGIES
    from .plot_masterpeng_mean_performance import METRICS, METHOD_LABELS, cell_statistics, write_pdf
except ImportError:
    from export_masterpeng_performance import FIELDS, NUMERIC_FIELDS, STRATEGIES
    from plot_masterpeng_mean_performance import METRICS, METHOD_LABELS, cell_statistics, write_pdf


RUN_NAME = re.compile(
    r"(?:^|_)MR_(?P<year>\d{4})_(?P<range>\w+)_(?P<method>random|cmaes|tpe|gpei|gpucb|gpbpucb)_"
    r"(?P<steps>\d+)_RS_(?P<seed>\d+)(?:_\d+)?$"
)
STRATEGY_NAME = re.compile(r"(EmperorPenguin|GentooPenguin|RockhopperPenguin)(?:_\d+)?$")


def collect(root, methods=None):
    """Discover prefixed run names, checking coordinates and strategy coverage."""
    root = Path(root).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Collection not found: {root}")
    runs, configurations = {}, set()
    years = sorted(int(p.name[4:]) for p in root.glob("Year*")
                   if p.is_dir() and re.fullmatch(r"Year\d{4}", p.name))
    seeds = sorted({int(p.name[3:]) for p in root.glob("Year*/RS_*")
                    if p.is_dir() and re.fullmatch(r"RS_\d+", p.name)})
    for run in sorted(root.glob("Year*/RS_*/*")):
        if not run.is_dir() or not (run / "artifacts").is_dir():
            continue
        match = RUN_NAME.search(run.name)
        if not match:
            raise ValueError(f"Unrecognized run name: {run}")
        year, method, seed = int(match["year"]), match["method"], int(match["seed"])
        if run.parent.name != f"RS_{seed}" or run.parent.parent.name != f"Year{year}":
            raise ValueError(f"Run name disagrees with year/seed folders: {run}")
        key = (year, method, seed)
        if key in runs:
            raise ValueError(f"Duplicate year/method/seed: {runs[key]} and {run}")
        runs[key] = run
        configurations.add((match["range"], int(match["steps"])))
    if not runs or not years or not seeds:
        raise ValueError(f"No Year*/RS_* runs found: {root}")
    if len(configurations) != 1:
        raise ValueError(f"Mixed search ranges/training steps in {root}: {configurations}")
    present_methods = {key[1] for key in runs}
    selected_methods = present_methods if methods is None else set(methods)
    if not present_methods <= selected_methods or not selected_methods <= METHOD_LABELS.keys():
        raise ValueError(f"Method selection omits runs or contains unknown methods: {selected_methods}")
    method_labels = [(key, label) for key, label in METHOD_LABELS.items() if key in selected_methods]
    records, counts = [], Counter()
    for year in years:
        for method, _ in method_labels:
            for seed in seeds:
                run = runs.get((year, method, seed))
                metrics_path = run / "artifacts/json/metrics_summary.json" if run else None
                metrics = json.loads(metrics_path.read_text()) if metrics_path and metrics_path.is_file() else None
                status = "Completed" if metrics is not None else "Missing"
                counts[status] += 1
                variants, spy_return = {}, None
                if metrics is not None:
                    benchmark = metrics.get("SP500", metrics.get("SP500Penguin", {}))
                    spy_return = benchmark.get("return_pct")
                    if not isinstance(spy_return, (int, float)) or not math.isfinite(spy_return):
                        raise ValueError(f"Invalid SPY return: {metrics_path}")
                    for original, values in metrics.items():
                        if original in {"SP500", "SP500Penguin"}:
                            continue
                        match = STRATEGY_NAME.fullmatch(original)
                        if not match:
                            raise ValueError(f"Unexpected strategy {original}: {metrics_path}")
                        base = match[1]
                        key = (base, 1 if original == base else 2)
                        if key in variants:
                            raise ValueError(f"Duplicate variant {key}: {metrics_path}")
                        variants[key] = original, values
                    if set(variants) != set(STRATEGIES):
                        raise ValueError(f"Incomplete strategy coverage: {metrics_path}")
                for base, variant in STRATEGIES:
                    original, values = variants.get((base, variant), ("", {}))
                    record = dict(year=year, method=method, seed=seed, strategy=base,
                                  variant=variant, original_strategy_name=original,
                                  spy_return_pct=spy_return, status=status,
                                  failure="" if metrics is not None else "Final test metrics not available.",
                                  source_file=str(metrics_path) if metrics_path else "")
                    for field in NUMERIC_FIELDS - {"spy_return_pct", "excess_return_pp"}:
                        value = values.get(field)
                        if metrics is not None and (not isinstance(value, (int, float)) or not math.isfinite(value)):
                            raise ValueError(f"Invalid {field}: {metrics_path}")
                        record[field] = value
                    buys = record["buy_trades"]
                    if buys is not None and (buys < 0 or int(buys) != buys):
                        raise ValueError(f"Invalid BUY count: {metrics_path}")
                    record["excess_return_pp"] = round(record["return_pct"] - spy_return, 2) if metrics is not None else None
                    records.append(record)
    return records, years, method_labels, seeds, dict(counts)


def generate(root, methods=None):
    root = Path(root).expanduser().resolve()
    records, years, method_labels, seeds, counts = collect(root, methods)
    output = root / "performance_tables"
    output.mkdir(exist_ok=True)
    with (output / "seed_results.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(records)
    for metric in METRICS:
        cells = cell_statistics(records, metric, years=years, methods=method_labels, seeds=seeds)
        name = "performance_summary" + ("_vs_spy" if metric == "excess_return_pp" else "")
        pdf = root / (name + ".pdf")
        write_pdf(pdf, cells, metric, collection=root.name)
        with (output / (name + ".csv")).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(cells[0]))
            writer.writeheader()
            writer.writerows({key: ",".join(map(str, value)) if isinstance(value, list) else value
                              for key, value in cell.items()} for cell in cells)
        metadata = {"collection": str(root), "metric": metric, "units": METRICS[metric][1],
                    "years": years, "methods": dict(method_labels), "seeds": seeds,
                    "run_counts": counts, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                    "average_buys": "mean executed test BUY orders across the same completed seeds as returns",
                    "standard_error": "sample SD (ddof=1) / sqrt(n); unavailable for fewer than two seeds",
                    "colormap": "viridis", "vmin": -100, "vmax": 50, "cells": cells}
        (output / (name + ".json")).write_text(json.dumps(metadata, indent=2, allow_nan=False) + "\n")
        print(f"Saved {pdf} ({len(STRATEGIES)} pages; runs: {counts})", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="+", type=Path, help="Collections containing Year*/RS_*/run folders.")
    parser.add_argument("--methods", nargs="+", choices=METHOD_LABELS,
                        help="Expected methods, including experiments that have not started yet.")
    args = parser.parse_args()
    for root in args.roots:
        generate(root, args.methods)


if __name__ == "__main__":
    main()
