#!/usr/bin/env python3
"""Visualize multi-timeframe support/resistance levels from SupportResistancePenguin."""

import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytz
from matplotlib.backends.backend_pdf import PdfPages

# Ensure project root is on sys.path when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from market_data import get_bars, init_router
from config import ALL_SYMBOLS, BINNING, START_DATE, STOP_DATE


def _fetch_bars_with_retry(symbol: str, start: datetime, end: datetime, timeframe: str) -> tuple[pd.DataFrame, datetime, datetime]:
    """Fetch bars with automatic retry for Alpaca recent SIP restriction."""
    try:
        df = get_bars(symbol, start, end, timeframe)
        return df, start, end
    except RuntimeError as exc:
        if "recent SIP data" in str(exc):
            end_retry = datetime.now(pytz.UTC).replace(hour=23, minute=50, second=0, microsecond=0) - timedelta(days=1)
            start_retry = end_retry - (end - start)
            print(f"[{symbol}] Recent SIP restriction detected; retrying with yesterday as end date...")
            df = get_bars(symbol, start_retry, end_retry, timeframe)
            return df, start_retry, end_retry
        raise


def _compute_multitimeframe_levels(close_prices: list[float]) -> dict:
    """Compute S/R levels at multiple timeframes (matching SupportResistancePenguin logic)."""
    # Assumes ~390 bars per trading day (6.5 hours × 60 minutes)
    timeframe_bars = {
        "20-bar (trading)": 20,
        "1d": 390,
        "1w": 390 * 5,
        "1m": 390 * 21,
        "3m": 390 * 63,
        "1y": 390 * 252,
    }
    
    levels = {}
    for tf_name, num_bars in timeframe_bars.items():
        if num_bars > len(close_prices):
            # Not enough data for this timeframe
            continue
        
        recent_prices = close_prices[-num_bars:]
        support = min(recent_prices)
        resistance = max(recent_prices)
        
        levels[tf_name] = {
            "support": support,
            "resistance": resistance,
            "num_bars": num_bars,
        }
    
    return levels


def _plot_multitimeframe(df: pd.DataFrame, symbol: str, levels_dict: dict, output: Path | None):
    """Plot close price with multi-timeframe S/R levels stacked."""
    fig, ax = plt.subplots(figsize=(16, 8))
    
    ax.plot(df["timestamp"], df["close"], color="#1f77b4", linewidth=2, label="Close Price")
    ax.fill_between(df["timestamp"], df["low"], df["high"], color="#1f77b4", alpha=0.10, label="High-Low Range")
    
    # Color palette for different timeframes
    colors = {
        "20-bar (trading)": "#d62728",  # Red (thickest, most important)
        "1d": "#ff7f0e",                # Orange
        "1w": "#2ca02c",                # Green
        "1m": "#9467bd",                # Purple
        "3m": "#8c564b",                # Brown
        "1y": "#e377c2",                # Pink
    }
    
    linewidths = {
        "20-bar (trading)": 2.5,
        "1d": 2.0,
        "1w": 1.6,
        "1m": 1.3,
        "3m": 1.0,
        "1y": 0.8,
    }
    
    # Plot levels for each timeframe
    for tf_name in ["1y", "3m", "1m", "1w", "1d", "20-bar (trading)"]:  # Plot from longest to shortest
        if tf_name not in levels_dict:
            continue
        
        level_data = levels_dict[tf_name]
        support = level_data["support"]
        resistance = level_data["resistance"]
        num_bars = level_data["num_bars"]
        
        color = colors.get(tf_name, "#000000")
        lw = linewidths.get(tf_name, 1.0)
        
        # Support line
        ax.axhline(support, color=color, linestyle="--", linewidth=lw, alpha=0.7)
        ax.text(
            df["timestamp"].iloc[-1],
            support,
            f" S {tf_name}",
            color=color,
            fontsize=8,
            va="top",
            ha="left",
        )
        
        # Resistance line
        ax.axhline(resistance, color=color, linestyle="--", linewidth=lw, alpha=0.7)
        ax.text(
            df["timestamp"].iloc[-1],
            resistance,
            f" R {tf_name}",
            color=color,
            fontsize=8,
            va="bottom",
            ha="left",
        )
    
    ax.set_title(f"{symbol} Multi-Timeframe Support & Resistance Levels")
    ax.set_xlabel("Time")
    ax.set_ylabel("Price ($)")
    ax.grid(True, alpha=0.25)
    
    # Ensure y-axis is not inverted
    if ax.yaxis_inverted():
        ax.invert_yaxis()
    
    # Leave room for right-side labels
    ax.margins(x=0.12)
    
    fig.tight_layout()
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output, dpi=150)
        plt.close(fig)
        return None
    return fig


def main():
    parser = argparse.ArgumentParser(description="Visualize multi-timeframe S/R levels (as calculated by SupportResistancePenguin).")
    parser.add_argument("symbol", type=str, nargs="?", help="Ticker symbol, e.g. AAPL (omit when using --all-symbols)")
    parser.add_argument("--all-symbols", action="store_true", help="Generate a multi-page PDF for all configured symbols")
    parser.add_argument("--days", type=int, default=90, help="Lookback window in days (default: 90 for multi-timeframe context)")
    parser.add_argument("--timeframe", type=str, default=None, help="Bar timeframe: 1m, 5m, 15m, 1h, 1d (default: BINNING from config)")
    parser.add_argument(
        "--output",
        type=str,
        default="run_current/sr_multitimeframe_single_symbol.png",
        help="Output image path (single-symbol mode)",
    )
    parser.add_argument(
        "--pdf-output",
        type=str,
        default="run_current/S&R_MultiTimeframe.pdf",
        help="Output PDF path (all-symbols mode)",
    )
    args = parser.parse_args()

    if not args.all_symbols and not args.symbol:
        raise ValueError("Provide SYMBOL or use --all-symbols.")

    timeframe = args.timeframe or BINNING
    
    # For multi-timeframe analysis, use days parameter (default 90 days)
    end = datetime.now(pytz.UTC)
    start = end - timedelta(days=args.days)

    init_router(use_cache=True, cache_dir="data_cache")
    if args.all_symbols:
        output_pdf = Path(args.pdf_output)
        output_pdf.parent.mkdir(parents=True, exist_ok=True)
        symbols = list(ALL_SYMBOLS)
        successes = 0
        failures = 0

        with PdfPages(output_pdf) as pdf:
            for symbol in symbols:
                try:
                    df, _, _ = _fetch_bars_with_retry(symbol, start, end, timeframe)
                    if df.empty:
                        failures += 1
                        print(f"[{symbol}] No data returned; skipping")
                        continue

                    df = df.sort_values("timestamp").reset_index(drop=True)
                    levels_dict = _compute_multitimeframe_levels(df["close"].astype(float).tolist())
                    
                    if not levels_dict:
                        failures += 1
                        print(f"[{symbol}] Unable to compute levels; skipping")
                        continue

                    fig = _plot_multitimeframe(df, symbol, levels_dict, output=None)
                    pdf.savefig(fig, orientation='landscape')
                    plt.close(fig)
                    successes += 1
                    print(f"[{symbol}] Added to PDF")
                except Exception as exc:
                    failures += 1
                    print(f"[{symbol}] Failed: {exc}")

        print(f"Saved PDF: {output_pdf}")
        print(f"Timeframe used: {timeframe} (config BINNING={BINNING})")
        print(f"Date range: {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')} UTC ({args.days} days lookback)")
        print(f"Symbols added: {successes} / {len(symbols)} (failed: {failures})")
    else:
        symbol = args.symbol.upper()
        df, _, _ = _fetch_bars_with_retry(symbol, start, end, timeframe)

        if df.empty:
            raise RuntimeError(f"No data returned for {symbol}.")

        df = df.sort_values("timestamp").reset_index(drop=True)
        levels_dict = _compute_multitimeframe_levels(df["close"].astype(float).tolist())
        
        if not levels_dict:
            raise RuntimeError(f"Unable to compute levels for {symbol}.")

        output_path = Path(args.output)
        _plot_multitimeframe(df, symbol, levels_dict, output_path)

        print(f"Saved chart: {output_path}")
        print(f"Timeframe used: {timeframe} (config BINNING={BINNING})")
        print(f"Date range: {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')} UTC ({args.days} days lookback)")
        
        print("\nMulti-timeframe levels computed:")
        for tf_name in ["1y", "3m", "1m", "1w", "1d", "20-bar (trading)"]:
            if tf_name in levels_dict:
                level = levels_dict[tf_name]
                print(f"  {tf_name:20s}: Support=${level['support']:.2f}, Resistance=${level['resistance']:.2f} ({level['num_bars']} bars)")


if __name__ == "__main__":
    main()
