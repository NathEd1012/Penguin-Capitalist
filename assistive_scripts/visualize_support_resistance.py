#!/usr/bin/env python3
"""Visualize support/resistance levels for a single symbol."""

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


def _find_local_extrema(prices: list[float]) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    """Return local minima/maxima as (index, price) tuples."""
    support_levels: list[tuple[int, float]] = []
    resistance_levels: list[tuple[int, float]] = []

    if len(prices) < 3:
        return support_levels, resistance_levels

    for i in range(1, len(prices) - 1):
        if prices[i] < prices[i - 1] and prices[i] < prices[i + 1]:
            support_levels.append((i, prices[i]))
        elif prices[i] > prices[i - 1] and prices[i] > prices[i + 1]:
            resistance_levels.append((i, prices[i]))

    return support_levels, resistance_levels


def _cluster_levels(levels: list[tuple[int, float]], tolerance: float = 0.02) -> list[dict]:
    """Cluster nearby levels and return sorted stats with price/touches."""
    if not levels:
        return []

    levels_sorted = sorted(levels, key=lambda x: x[1])
    clusters = []
    current_cluster = [levels_sorted[0]]

    for level in levels_sorted[1:]:
        base_price = current_cluster[0][1]
        pct_diff = abs(level[1] - base_price) / base_price
        if pct_diff <= tolerance:
            current_cluster.append(level)
        else:
            clusters.append(current_cluster)
            current_cluster = [level]

    clusters.append(current_cluster)

    stats = []
    for cluster in clusters:
        stats.append({
            "price": float(np.mean([p for _, p in cluster])),
            "touches": len(cluster),
            "points": cluster,
        })

    stats.sort(key=lambda x: (-x["touches"], x["price"]))
    return stats


def _compute_sr_levels(close_prices: list[float], tolerance: float, top_n: int):
    supports, resistances = _find_local_extrema(close_prices)
    support_points = supports
    resistance_points = resistances
    support_stats = _cluster_levels(supports, tolerance=tolerance)[:top_n]
    resistance_stats = _cluster_levels(resistances, tolerance=tolerance)[:top_n]
    return support_stats, resistance_stats, support_points, resistance_points


def _compute_penguin_levels(close_prices: list[float], window: int = 20) -> tuple[list[float], list[float]]:
    """Compute rolling support/resistance exactly as SupportResistancePenguin uses them."""
    supports = [float("nan")] * len(close_prices)
    resistances = [float("nan")] * len(close_prices)

    for i in range(window - 1, len(close_prices)):
        recent = close_prices[i - window + 1 : i + 1]
        supports[i] = min(recent)
        resistances[i] = max(recent)

    return supports, resistances


def _plot_sr(
    df: pd.DataFrame,
    symbol: str,
    support_stats: list[dict],
    resistance_stats: list[dict],
    support_points: list[tuple[int, float]],
    resistance_points: list[tuple[int, float]],
    penguin_support_series: list[float] | None,
    penguin_resistance_series: list[float] | None,
    levels_source: str,
    output: Path | None,
):
    """Plot close price with support and resistance horizontal lines."""
    fig, ax = plt.subplots(figsize=(14, 7))

    ax.plot(df["timestamp"], df["close"], color="#1f77b4", linewidth=1.8, label=f"{symbol} Close")
    ax.fill_between(df["timestamp"], df["low"], df["high"], color="#1f77b4", alpha=0.12, label="High-Low Range")

    # Plot all local extrema points so touch counts are visually verifiable.
    if support_points:
        s_x = [df["timestamp"].iloc[i] for i, _ in support_points]
        s_y = [p for _, p in support_points]
        ax.scatter(s_x, s_y, s=14, color="#2ca02c", alpha=0.30, label="Local Minima")

    if resistance_points:
        r_x = [df["timestamp"].iloc[i] for i, _ in resistance_points]
        r_y = [p for _, p in resistance_points]
        ax.scatter(r_x, r_y, s=14, color="#d62728", alpha=0.30, label="Local Maxima")

    if levels_source == "penguin" and penguin_support_series and penguin_resistance_series:
        ax.plot(
            df["timestamp"],
            penguin_support_series,
            color="#2ca02c",
            linestyle="--",
            linewidth=1.6,
            alpha=0.95,
            label="S&R Penguin Support (rolling 20 low)",
        )
        ax.plot(
            df["timestamp"],
            penguin_resistance_series,
            color="#d62728",
            linestyle="--",
            linewidth=1.6,
            alpha=0.95,
            label="S&R Penguin Resistance (rolling 20 high)",
        )

        latest_support = next((v for v in reversed(penguin_support_series) if pd.notna(v)), None)
        latest_resistance = next((v for v in reversed(penguin_resistance_series) if pd.notna(v)), None)
        if latest_support is not None:
            ax.text(df["timestamp"].iloc[-1], latest_support, f" S {latest_support:.2f}", color="#2ca02c", fontsize=9, va="center", ha="left")
        if latest_resistance is not None:
            ax.text(df["timestamp"].iloc[-1], latest_resistance, f" R {latest_resistance:.2f}", color="#d62728", fontsize=9, va="center", ha="left")
    else:
        for idx, s in enumerate(support_stats, 1):
            ax.axhline(s["price"], color="#2ca02c", linestyle="--", alpha=0.8, linewidth=1.2)
            # Highlight points that belong to this support cluster.
            cs_x = [df["timestamp"].iloc[i] for i, _ in s.get("points", [])]
            cs_y = [p for _, p in s.get("points", [])]
            if cs_x:
                ax.scatter(cs_x, cs_y, s=34, facecolors="none", edgecolors="#2ca02c", linewidths=1.2, alpha=0.9)
            ax.text(
                df["timestamp"].iloc[-1],
                s["price"],
                f" S{idx} {s['price']:.2f} ({s['touches']})",
                color="#2ca02c",
                fontsize=9,
                va="center",
                ha="left",
            )

        for idx, r in enumerate(resistance_stats, 1):
            ax.axhline(r["price"], color="#d62728", linestyle="--", alpha=0.8, linewidth=1.2)
            # Highlight points that belong to this resistance cluster.
            cr_x = [df["timestamp"].iloc[i] for i, _ in r.get("points", [])]
            cr_y = [p for _, p in r.get("points", [])]
            if cr_x:
                ax.scatter(cr_x, cr_y, s=34, facecolors="none", edgecolors="#d62728", linewidths=1.2, alpha=0.9)
            ax.text(
                df["timestamp"].iloc[-1],
                r["price"],
                f" R{idx} {r['price']:.2f} ({r['touches']})",
                color="#d62728",
                fontsize=9,
                va="center",
                ha="left",
            )

    ax.set_title(f"{symbol} Support & Resistance")
    ax.set_xlabel("Time")
    ax.set_ylabel("Price ($)")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")

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


def _build_levels(df: pd.DataFrame, levels_source: str, tolerance: float, top_n: int):
    """Build either cluster-based levels or SupportResistancePenguin rolling levels."""
    support_stats, resistance_stats, support_points, resistance_points = _compute_sr_levels(
        close_prices=df["close"].astype(float).tolist(),
        tolerance=tolerance,
        top_n=top_n,
    )
    penguin_support_series = None
    penguin_resistance_series = None
    if levels_source == "penguin":
        penguin_support_series, penguin_resistance_series = _compute_penguin_levels(
            close_prices=df["close"].astype(float).tolist(),
            window=20,
        )
    return (
        support_stats,
        resistance_stats,
        support_points,
        resistance_points,
        penguin_support_series,
        penguin_resistance_series,
    )


def main():
    parser = argparse.ArgumentParser(description="Visualize support and resistance levels for one stock symbol.")
    parser.add_argument("symbol", type=str, nargs="?", help="Ticker symbol, e.g. AAPL (omit when using --all-symbols)")
    parser.add_argument("--all-symbols", action="store_true", help="Generate a multi-page PDF for all configured symbols")
    parser.add_argument("--days", type=int, default=None, help="Lookback window in days (overrides config dates if provided)")
    parser.add_argument("--timeframe", type=str, default=None, help="Bar timeframe: 1m, 5m, 15m, 1h, 1d (default: BINNING from config)")
    parser.add_argument(
        "--levels-source",
        type=str,
        default="cluster",
        choices=["cluster", "penguin"],
        help="Level source: 'cluster' (static extrema clusters) or 'penguin' (rolling 20-bar levels used by SupportResistancePenguin)",
    )
    parser.add_argument("--tolerance", type=float, default=0.02, help="Clustering tolerance as decimal (default: 0.02)")
    parser.add_argument("--top", type=int, default=5, help="Top support/resistance lines to draw (default: 5)")
    parser.add_argument(
        "--output",
        type=str,
        default="run_current/support_resistance_single_symbol.png",
        help="Output image path (single-symbol mode)",
    )
    parser.add_argument(
        "--pdf-output",
        type=str,
        default="run_current/S&R_Lines.pdf",
        help="Output PDF path (all-symbols mode)",
    )
    args = parser.parse_args()

    if not args.all_symbols and not args.symbol:
        raise ValueError("Provide SYMBOL or use --all-symbols.")

    timeframe = args.timeframe or BINNING
    
    # Use config dates by default, or calculate from --days if provided
    if args.days is not None:
        end = datetime.now(pytz.UTC)
        start = end - timedelta(days=args.days)
    else:
        # Parse config dates (assume UTC if no timezone info)
        start = datetime.fromisoformat(START_DATE.replace("TODAY", datetime.now(pytz.UTC).strftime("%Y-%m-%d")))
        if start.tzinfo is None:
            start = pytz.UTC.localize(start)
        stop = datetime.fromisoformat(STOP_DATE.replace("TODAY", datetime.now(pytz.UTC).strftime("%Y-%m-%d")))
        if stop.tzinfo is None:
            stop = pytz.UTC.localize(stop)
        
        # Use exact config dates
        start = start
        end = stop

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
                    (
                        support_stats,
                        resistance_stats,
                        support_points,
                        resistance_points,
                        penguin_support_series,
                        penguin_resistance_series,
                    ) = _build_levels(df, args.levels_source, args.tolerance, args.top)

                    fig = _plot_sr(
                        df,
                        symbol,
                        support_stats,
                        resistance_stats,
                        support_points,
                        resistance_points,
                        penguin_support_series,
                        penguin_resistance_series,
                        args.levels_source,
                        output=None,
                    )
                    pdf.savefig(fig, orientation='landscape')
                    plt.close(fig)
                    successes += 1
                    print(f"[{symbol}] Added to PDF")
                except Exception as exc:
                    failures += 1
                    print(f"[{symbol}] Failed: {exc}")

        print(f"Saved PDF: {output_pdf}")
        print(f"Timeframe used: {timeframe} (config BINNING={BINNING})")
        print(f"Date range: {start.strftime('%Y-%m-%d %H:%M')} to {end.strftime('%Y-%m-%d %H:%M')} UTC")
        if args.days is None:
            print(f"Using config dates: START_DATE={START_DATE}, STOP_DATE={STOP_DATE}")
        print(f"Symbols added: {successes} / {len(symbols)} (failed: {failures})")
    else:
        symbol = args.symbol.upper()
        df, _, _ = _fetch_bars_with_retry(symbol, start, end, timeframe)

        if df.empty:
            raise RuntimeError(f"No data returned for {symbol}.")

        df = df.sort_values("timestamp").reset_index(drop=True)
        (
            support_stats,
            resistance_stats,
            support_points,
            resistance_points,
            penguin_support_series,
            penguin_resistance_series,
        ) = _build_levels(df, args.levels_source, args.tolerance, args.top)

        output_path = Path(args.output)
        _plot_sr(
            df,
            symbol,
            support_stats,
            resistance_stats,
            support_points,
            resistance_points,
            penguin_support_series,
            penguin_resistance_series,
            args.levels_source,
            output_path,
        )

        print(f"Saved chart: {output_path}")
        print(f"Timeframe used: {timeframe} (config BINNING={BINNING})")
        print(f"Date range: {start.strftime('%Y-%m-%d %H:%M')} to {end.strftime('%Y-%m-%d %H:%M')} UTC")
        if args.days is None:
            print(f"Using config dates: START_DATE={START_DATE}, STOP_DATE={STOP_DATE}")
        if args.levels_source == "penguin" and penguin_support_series and penguin_resistance_series:
            latest_support = next((v for v in reversed(penguin_support_series) if pd.notna(v)), None)
            latest_resistance = next((v for v in reversed(penguin_resistance_series) if pd.notna(v)), None)
            print("SupportResistancePenguin levels (rolling 20 bars):")
            if latest_support is not None:
                print(f"  Support: ${latest_support:.2f}")
            if latest_resistance is not None:
                print(f"  Resistance: ${latest_resistance:.2f}")
        else:
            print("Support levels:")
            for idx, s in enumerate(support_stats, 1):
                print(f"  S{idx}: ${s['price']:.2f} (touches={s['touches']})")

            print("Resistance levels:")
            for idx, r in enumerate(resistance_stats, 1):
                print(f"  R{idx}: ${r['price']:.2f} (touches={r['touches']})")


if __name__ == "__main__":
    main()
