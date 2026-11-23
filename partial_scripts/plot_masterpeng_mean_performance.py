"""Plot MasterPeng seed means +/- standard errors in Viridis-colored 5 x 5 tables.

From the project root:
    python partial_scripts/plot_masterpeng_mean_performance.py
    python partial_scripts/plot_masterpeng_mean_performance.py --metric excess_return_pp

Each strategy/variant gets one PDF page. Colors use a fixed -100 to +50 scale;
out-of-range colors saturate, while printed values retain their actual values.
Error = sqrt(sample variance / n), with sample variance using n - 1.
"""

import argparse
import csv
import json
import math
from pathlib import Path

try:
    from .export_masterpeng_performance import DEFAULT_ROOT, METHODS, STRATEGIES, YEARS, strategy_title
    from .summarize_performance_tables import read_table, summarize
except ImportError:
    from export_masterpeng_performance import DEFAULT_ROOT, METHODS, STRATEGIES, YEARS, strategy_title
    from summarize_performance_tables import read_table, summarize


DEFAULT_INPUT = DEFAULT_ROOT / "performance_tables/masterpeng_performance.csv"
METHOD_LABELS = dict(METHODS + [("gpbpucb", "GP-BP-UCB")])
VMIN, VMAX = -100, 50
METRICS = {
    "return_pct": ("Test return", "%"),
    "excess_return_pp": ("Excess return vs SPY", "pp"),
}


def cell_statistics(rows, metric, *, years=None, methods=None, seeds=None):
    """Reuse the exported table's seed validation and exclude missing results."""
    if metric not in METRICS:
        raise ValueError(f"Unknown metric: {metric}")
    selected = []
    for row in rows:
        if row.get("strategy") in {"SP500", "SP500Penguin"}:
            continue
        if metric not in row:
            raise ValueError(f"Input has no {metric} column.")
        selected.append({**row, "excess_return_pp": row[metric]})
    cells = []
    for stat in summarize(selected, years=years, methods=methods, seeds=seeds):
        variance = stat["sample_sd_pp"] ** 2 if stat["sample_sd_pp"] is not None else None
        cells.append({
            "strategy": stat["strategy"], "variant": stat["variant"],
            "year": stat["year"], "method": stat["method"], "metric": metric,
            "n": stat["n"], "expected_n": stat["expected_n"],
            "mean": stat["mean_pp"], "sample_variance": variance,
            "standard_error": math.sqrt(variance / stat["n"]) if variance is not None else None,
            "mean_buy_trades": stat["mean_buy_trades"], "buy_count_n": stat["buy_count_n"],
            "included_seeds": stat["included_seeds"], "missing_seeds": stat["missing_seeds"],
        })
    return cells


def cell_text(cell, unit):
    if cell["mean"] is None:
        text = "No results"
    else:
        error = "N/A" if cell["standard_error"] is None else f"{cell['standard_error']:.2f}"
        text = f"{cell['mean']:+.2f} ± {error} {unit}"
    buys = "N/A" if cell["mean_buy_trades"] is None else f"{cell['mean_buy_trades']:,.1f}"
    return text + f"\nAvg buys: {buys}\nn = {cell['n']}/{cell['expected_n']}"


def write_pdf(path, cells, metric, collection=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.cm import ScalarMappable
    from matplotlib.colors import Normalize
    from matplotlib.ticker import FuncFormatter

    label, unit = METRICS[metric]
    years = sorted({cell["year"] for cell in cells})
    present_methods = {cell["method"] for cell in cells}
    methods = [(method, label) for method, label in METHOD_LABELS.items() if method in present_methods]
    if len(methods) != len(present_methods):
        raise ValueError(f"Unknown search methods: {present_methods - METHOD_LABELS.keys()}")
    cmap = plt.get_cmap("viridis")
    norm = Normalize(vmin=VMIN, vmax=VMAX, clip=True)
    lookup = {(c["strategy"], c["variant"], c["year"], c["method"]): c for c in cells}
    with PdfPages(path) as pdf:
        for page, (base, variant) in enumerate(STRATEGIES, 1):
            figure, axis = plt.subplots(figsize=(14, 9))
            figure.patch.set_facecolor("white")
            axis.axis("off")
            figure.text(0.055, 0.945, strategy_title(base, variant),
                        fontsize=23, weight="bold", color="#17354a")
            figure.text(0.055, 0.905, f"{label}: mean ± standard error ({unit}) | start year × search method",
                        fontsize=12, color="#43596a")
            if collection:
                figure.text(0.055, 0.875, collection, fontsize=10, color="#43596a")
            contents = []
            for year in years:
                row = [str(year)]
                for method, _ in methods:
                    cell = lookup[(base, variant, year, method)]
                    row.append(cell_text(cell, unit))
                contents.append(row)
            year_width = 0.07 if len(methods) >= 4 else 0.16
            table = axis.table(cellText=contents, colLabels=["Year"] + [name for _, name in methods],
                               cellLoc="center", colWidths=[year_width] + [(1 - year_width) / len(methods)] * len(methods),
                               bbox=[0, 0, 1, 1])
            table.auto_set_font_size(False)
            table.set_fontsize(12)
            for (row, column), box in table.get_celld().items():
                box.set_edgecolor("#d4dee5")
                box.set_linewidth(0.8)
                if row == 0 or column == 0:
                    box.set_facecolor("#17354a")
                    box.set_text_props(color="white", weight="bold")
                else:
                    cell = lookup[(base, variant, years[row - 1], methods[column - 1][0])]
                    color = cmap(norm(cell["mean"])) if cell["mean"] is not None else (0.88, 0.89, 0.91, 1)
                    box.set_facecolor(color)
                    brightness = sum(weight * channel for weight, channel in zip((0.2126, 0.7152, 0.0722), color[:3]))
                    box.set_text_props(color="black" if brightness > 0.5 else "white")
                    box.get_text().set_linespacing(1.3)
            axis.set_position([0.055, 0.265, 0.89, 0.585])
            color_axis = figure.add_axes([0.22, 0.18, 0.56, 0.025])
            bar = figure.colorbar(ScalarMappable(norm=norm, cmap=cmap), cax=color_axis,
                                 orientation="horizontal", extend="both", ticks=[-100, -75, -50, -25, 0, 25, 50])
            bar.ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:+g}{unit}"))
            bar.set_label(f"Cell color = mean {label.lower()} ({unit}); fixed scale −100 to +50")
            figure.text(0.055, 0.09, "Error = SEM = √(s² / n); s² = Σ(x − mean)² / (n − 1). Missing seeds are excluded.",
                        fontsize=10, color="#43596a")
            figure.text(0.055, 0.06, "Avg buys = executed test BUY orders averaged across the included seeds. One seed has no estimable SEM; colors saturate outside the scale.",
                        fontsize=9, color="#43596a")
            figure.text(0.945, 0.03, f"{page} / {len(STRATEGIES)}", ha="right", fontsize=9, color="#43596a")
            pdf.savefig(figure)
            if page == 1:
                figure.savefig(path.with_name(path.stem + "_preview.png"), dpi=140)
            plt.close(figure)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="MasterPeng seed-level CSV or XLSX export.")
    parser.add_argument("--metric", choices=METRICS, default="return_pct")
    parser.add_argument("--output", type=Path, help="Output PDF; default: mean_viridis subfolder beside the input.")
    args = parser.parse_args()
    source = args.input.expanduser().resolve()
    cells = cell_statistics(read_table(source), args.metric)
    path = args.output.expanduser().resolve() if args.output else source.parent / "mean_viridis" / f"masterpeng_mean_{args.metric}.pdf"
    if path.suffix.lower() != ".pdf":
        parser.error("--output must be a PDF path.")
    path.parent.mkdir(parents=True, exist_ok=True)
    write_pdf(path, cells, args.metric)
    with path.with_suffix(".csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(cells[0]))
        writer.writeheader()
        writer.writerows({key: ",".join(map(str, value)) if isinstance(value, list) else value
                          for key, value in cell.items()} for cell in cells)
    path.with_suffix(".json").write_text(json.dumps({
        "input": str(source), "metric": args.metric, "units": METRICS[args.metric][1],
        "error": "sqrt(sample variance / n), sample variance uses n - 1",
        "average_buys": "mean executed test BUY orders across the same included seeds as returns",
        "colormap": "viridis", "vmin": VMIN, "vmax": VMAX, "cells": cells,
    }, indent=2, allow_nan=False) + "\n")
    print(f"Saved {path} ({len(STRATEGIES)} pages, {len(cells)} cells), CSV and JSON statistics.")


if __name__ == "__main__":
    main()
