"""Rank tickers by cumulative executed BUY value in USD, one PDF page per strategy."""
import argparse
import csv
import math
import re
from collections import Counter
from decimal import Decimal
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.ticker import FuncFormatter, MaxNLocator

try:
    from .common import load_json, output_path, resolve_run_dir
except ImportError:
    from common import load_json, output_path, resolve_run_dir


NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
TRADE = re.compile(
    r"^\s*(?P<strategy>.+?):\s+(?P<action>BUY|SELL)\s+"
    rf"(?P<quantity>{NUMBER})\s+(?P<symbol>\S+)\s+@\s+\$"
    rf"(?P<price>{NUMBER})(?=\s|$)"
)


def read_buys(log_path, expected_counts=None):
    """Read only EXECUTION DETAILS; later recent-trade summaries repeat trades."""
    values = {name: Counter() for name in (expected_counts or {})}
    orders = {name: Counter() for name in (expected_counts or {})}
    in_details = False
    found_details = False
    with Path(log_path).open(encoding="utf-8", errors="replace") as handle:
        for line_number, line in enumerate(handle, 1):
            heading = line.strip()
            if heading == "EXECUTION DETAILS":
                in_details = found_details = True
                continue
            if heading.startswith(("LIQUIDATION TRADES", "STRATEGY SUMMARY")):
                break
            if not in_details:
                continue
            match = TRADE.match(line)
            if not match:
                if ": BUY " in line:
                    raise ValueError(f"Unrecognized BUY record at {log_path}:{line_number}")
                continue
            name, action, raw_quantity, symbol, raw_price = match.groups()
            values.setdefault(name, Counter())
            orders.setdefault(name, Counter())
            if action != "BUY":
                continue
            quantity = Decimal(raw_quantity)
            price = Decimal(raw_price)
            if not quantity.is_finite() or quantity <= 0:
                raise ValueError(f"Invalid BUY quantity at {log_path}:{line_number}")
            if not price.is_finite() or price <= 0:
                raise ValueError(f"Invalid BUY price at {log_path}:{line_number}")
            values[name][symbol] += quantity * price
            orders[name][symbol] += 1
    if not found_details and (not expected_counts or any(expected_counts.values())):
        raise ValueError(f"{log_path} has no complete EXECUTION DETAILS section; recent trades are insufficient.")
    if expected_counts is not None:
        for name in values.keys() | expected_counts.keys():
            actual = sum(orders.get(name, {}).values())
            expected = expected_counts.get(name)
            if expected is None or actual != expected:
                raise ValueError(f"{name}: parsed {actual} BUY orders, but metrics_summary.json records {expected}.")
    if not values:
        raise ValueError(f"No strategies found in {log_path}")
    return values, orders


def ranked_symbols(values):
    return sorted(values.items(), key=lambda item: (-item[1], item[0]))


def display_value(value):
    return f"${value:,.2f}"


def plot_strategy(name, values, orders, run_name):
    ranked = ranked_symbols(values)
    columns = max(1, math.ceil(len(ranked) / 50))
    figure, axes = plt.subplots(1, columns, figsize=(max(11, columns * 3.8), 12), squeeze=False, sharex=True)
    total = sum(values.values(), Decimal(0))
    figure.suptitle(f"{name} — total purchase value by ticker", fontsize=16, fontweight="bold", y=0.98)
    figure.text(0.5, 0.947,
                f"{run_name}\n{len(ranked)} tickers · {sum(orders.values()):,} BUY orders · {display_value(total)} total purchase value",
                ha="center", va="top", fontsize=9)
    maximum = float(ranked[0][1]) if ranked else 1.0
    for column, axis in enumerate(axes[0]):
        chunk = ranked[column * 50:(column + 1) * 50]
        if not chunk:
            axis.text(0.5, 0.5, "No executed BUY trades", transform=axis.transAxes, ha="center")
            axis.set_axis_off()
            continue
        bars = axis.barh(range(len(chunk)), [float(value) for _, value in chunk], color="#3678a8", height=0.72)
        axis.set_yticks(range(len(chunk)), [f"{column * 50 + i + 1}. {symbol}" for i, (symbol, _) in enumerate(chunk)], fontsize=7)
        axis.invert_yaxis()
        axis.bar_label(bars, labels=[display_value(value) for _, value in chunk], padding=3, fontsize=6)
        axis.set_xlim(0, maximum * 1.35)
        axis.set_xlabel("Total purchase value (USD)", fontsize=9)
        axis.xaxis.set_major_formatter(FuncFormatter(lambda value, position: f"${value:,.0f}"))
        axis.xaxis.set_major_locator(MaxNLocator(4))
        axis.tick_params(axis="x", labelsize=7)
        axis.set_title(f"Ranks {column * 50 + 1}–{column * 50 + len(chunk)}", loc="left", fontsize=9)
        axis.grid(axis="x", alpha=0.2)
        axis.set_axisbelow(True)
        axis.spines[["top", "right"]].set_visible(False)
    figure.text(0.5, 0.018,
                "Test-period BUY value = quantity × logged execution price, summed across repeat purchases; excludes commissions.\n"
                "All columns share the same USD scale. Execution prices are recorded to cents in the trade log.",
                ha="center", fontsize=8, color="#555555")
    figure.subplots_adjust(left=0.075, right=0.98, top=0.88, bottom=0.09, wspace=0.5)
    return figure


def generate(run_dir, destination=None):
    run_dir = resolve_run_dir(run_dir)
    artifacts = run_dir / "artifacts"
    metrics_path = artifacts / "json" / "metrics_summary.json"
    metrics = load_json(metrics_path) if metrics_path.is_file() else None
    expected = {name: int(values["buy_trades"]) for name, values in metrics.items()} if metrics is not None else None
    values, orders = read_buys(artifacts / "trades_log.txt", expected)
    # Validate the full log first, then omit the SPY reference from evaluation.
    for benchmark in ("SP500", "SP500Penguin"):
        values.pop(benchmark, None)
        orders.pop(benchmark, None)
    if not values:
        raise ValueError(f"No non-benchmark strategies found in {run_dir}")
    destination = output_path(run_dir, destination, "buy_histograms.pdf")
    with PdfPages(destination, metadata={"Title": "Cumulative purchase value by ticker (USD)"}) as pdf:
        for name in sorted(values):
            figure = plot_strategy(name, values[name], orders[name], run_dir.name)
            pdf.savefig(figure)
            plt.close(figure)
    csv_path = destination.with_suffix(".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["strategy", "rank", "symbol", "purchase_value_usd", "buy_orders"])
        for name in sorted(values):
            for rank, (symbol, value) in enumerate(ranked_symbols(values[name]), 1):
                writer.writerow([name, rank, symbol, format(value, "f"), orders[name][symbol]])
    print(f"Saved {destination} ({len(values)} strategy pages)")
    print(f"Saved {csv_path}")
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, help="Run directory or path below run_log.")
    parser.add_argument("--output", type=Path, help="Output PDF; default: artifacts/buy_histograms.pdf")
    args = parser.parse_args()
    generate(args.run_dir, args.output)


if __name__ == "__main__":
    main()
