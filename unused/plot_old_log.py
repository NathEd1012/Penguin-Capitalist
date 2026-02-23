#!/usr/bin/env python3
"""
plot_old_log.py - Replot capital curves from saved data or plot summary from log.
Usage: python plot_old_log.py <data_XXXXXX.json or trades_XXXXXX.txt>
"""

import sys
import json
import os
import matplotlib
import re

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from config import INITIAL_CAPITAL


def plot_capital_curves(curves, filename):
    """Plot and save capital curves."""
    plt.figure(figsize=(12, 6))
    for name, vals in curves.items():
        plt.plot(range(1, len(vals) + 1), vals, marker=None, label=name, linewidth=1)

    # Calculate and plot overall average capital
    if curves:
        curve_values = list(curves.values())
        num_penguins = len(curve_values)
        overall_avg = [
            sum(vals[i] for vals in curve_values) / num_penguins
            for i in range(len(curve_values[0]))
        ]
        plt.plot(
            range(1, len(overall_avg) + 1),
            overall_avg,
            marker="",
            label="Overall Average Capital",
            linewidth=3,
            color="black",
            linestyle="--",
        )

    plt.axhline(
        y=INITIAL_CAPITAL,
        color="gray",
        linestyle="--",
        alpha=0.5,
        label="Initial Capital",
    )
    plt.xlabel("Minute")
    plt.ylabel("Total Capital ($)")
    plt.title(f"Penguin Capital Over {len(list(curves.values())[0])} Minutes")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(filename, dpi=100)
    plt.close()  # Close to free memory
    print(f"📈 Saved replot to {filename}")


def plot_from_log(log_file, output_file):
    """Plot capital progression from log file trades."""
    with open(log_file, "r") as f:
        content = f.read()

    # Extract penguin sections
    sections = re.split(r"\n(?=[A-Z][a-z]+Penguin)", content)[
        1:
    ]  # Split on penguin names

    curves = {}

    for section in sections:
        lines = section.strip().split("\n")
        name = lines[0]
        portfolio = {"cash": INITIAL_CAPITAL, "positions": {}}
        values = [INITIAL_CAPITAL]

        # Find trades
        trades_start = False
        for line in lines:
            if "Trades:" in line:
                trades_start = True
                continue
            if trades_start and line.strip().startswith(("BUY", "SELL")):
                # Parse trade: "1. BUY 1 MSFT @ $457.42"
                match = re.search(
                    r"\s*\d+\.\s*(BUY|SELL)\s+(\d+)\s+(\w+)\s+@\s+\$([0-9.]+)", line
                )
                if match:
                    action, qty_str, symbol, price_str = match.groups()
                    qty = int(qty_str)
                    price = float(price_str)

                    if action == "BUY":
                        cost = price * qty + 1.0  # assuming fee
                        if portfolio["cash"] >= cost:
                            portfolio["cash"] -= cost
                            portfolio["positions"][symbol] = (
                                portfolio["positions"].get(symbol, 0) + qty
                            )
                    elif action == "SELL":
                        if portfolio["positions"].get(symbol, 0) >= qty:
                            portfolio["cash"] += price * qty - 1.0
                            portfolio["positions"][symbol] -= qty
                            if portfolio["positions"][symbol] == 0:
                                del portfolio["positions"][symbol]

                    # Calculate current value (assuming current prices are the trade prices, simplistic)
                    value = portfolio["cash"]
                    for sym, q in portfolio["positions"].items():
                        value += (
                            q * price
                        )  # Use last price, not accurate but approximate
                    values.append(value)

        if len(values) > 1:
            curves[name] = values

    if not curves:
        print("No trades found in log.")
        return

    # Plot
    plt.figure(figsize=(12, 6))
    for name, vals in curves.items():
        plt.plot(range(len(vals)), vals, marker=None, label=name, linewidth=1)

    plt.axhline(
        y=INITIAL_CAPITAL,
        color="red",
        linestyle="--",
        label=f"Initial Capital (${INITIAL_CAPITAL})",
    )
    plt.xlabel("Trade Number")
    plt.ylabel("Portfolio Value ($)")
    plt.title(f"Portfolio Value Progression from {os.path.basename(log_file)}")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_file, dpi=100)
    plt.close()
    print(f"📊 Saved progression plot to {output_file}")


def main():
    if len(sys.argv) != 2:
        print("Usage: python plot_old_log.py <data_XXXXXX.json or trades_XXXXXX.txt>")
        sys.exit(1)

    input_file = sys.argv[1]

    if input_file.endswith(".json"):
        # Original functionality for JSON
        try:
            with open(input_file, "r") as f:
                curves = json.load(f)
        except FileNotFoundError:
            print(f"Error: File {input_file} not found.")
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON in {input_file}.")
            sys.exit(1)

        output_file = input_file.replace("data_", "replot_capital_").replace(
            ".json", ".png"
        )
        output_file = os.path.join(
            os.path.dirname(input_file), "..", "plots", os.path.basename(output_file)
        )
        plot_capital_curves(curves, output_file)

    elif input_file.endswith(".txt"):
        # New functionality for TXT logs
        output_file = input_file.replace("trades_", "summary_").replace(".txt", ".png")
        output_file = os.path.join(
            os.path.dirname(input_file), "..", "plots", os.path.basename(output_file)
        )
        plot_from_log(input_file, output_file)

    else:
        print("Error: File must be .json or .txt")
        sys.exit(1)


if __name__ == "__main__":
    main()
