#!/usr/bin/env python3
"""Plot one symbol over multiple backward spans and mark local extrema in a PDF.

Creates one PDF page per span, anchored at an end date:
- 1 day
- 1 week
- 1 month
- 3 months
- 1 year

Each span uses a configured stock-data timeframe, while local minima/maxima use
an adaptive bin size so extrema density stays readable.
"""

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytz
from matplotlib.backends.backend_pdf import PdfPages

# Ensure project root is on sys.path when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from market_data import get_bars, init_router

ALIGNMENT_THRESHOLD_PCT = 0.006
MAX_FITTED_LINES = 8
DEFAULT_ANCHOR_LEVELS = 5
ANCHOR_LEVEL_MARKER_SIZE = 40
ANCHOR_OUTSIDE_PADDING_RATIO = 0.20
END_DATE_LOOKBACK_DAYS = 14


@dataclass(frozen=True)
class SpanConfig:
    label: str
    delta: timedelta
    timeframe: str
    bucket_bars: int


SPAN_CONFIGS = [
    # bucket_bars controls extrema buckets per span.
    # 1 Day: 30 bars @1m = 30-minute buckets
    # 1 Week: 24 bars @5m = 2-hour buckets
    # 1 Month: 26 bars @15m = ~1 trading day buckets
    # 3 Months: 130 bars @15m = ~5 trading day buckets
    # 1 Year: 147 bars @1h = ~1 month buckets (about 21 trading days * ~7 hourly bars/day)
    SpanConfig("1 Day", timedelta(days=1), "1m", 30),
    SpanConfig("1 Week", timedelta(weeks=1), "5m", 24),
    SpanConfig("1 Month", timedelta(days=30), "15m", 26),
    SpanConfig("3 Months", timedelta(days=90), "15m", 130),
    SpanConfig("1 Year", timedelta(days=365), "1h", 147),
]


def _parse_end_datetime(end_date_arg: str | None) -> datetime:
    """Parse end date in UTC; default to yesterday 23:50 UTC to avoid SIP recency limits."""
    if not end_date_arg:
        return datetime.now(pytz.UTC).replace(hour=23, minute=50, second=0, microsecond=0) - timedelta(days=1)

    try:
        end_dt = pd.to_datetime(end_date_arg, utc=True)
    except Exception as exc:
        raise ValueError(f"Could not parse --end-date '{end_date_arg}': {exc}") from exc

    if isinstance(end_dt, pd.Timestamp):
        return end_dt.to_pydatetime()
    return end_dt


def _fetch_bars_with_retry(symbol: str, start: datetime, end: datetime, timeframe: str) -> pd.DataFrame:
    """Fetch bars and retry with a shifted end when recent SIP data is blocked."""
    try:
        return get_bars(symbol, start, end, timeframe)
    except RuntimeError as exc:
        if "recent SIP data" not in str(exc):
            raise

        end_retry = datetime.now(pytz.UTC).replace(hour=23, minute=50, second=0, microsecond=0) - timedelta(days=1)
        duration = end - start
        start_retry = end_retry - duration
        print(f"[{symbol} {timeframe}] Recent SIP restriction detected; retrying with end={end_retry.isoformat()}")
        return get_bars(symbol, start_retry, end_retry, timeframe)


def _resolve_end_datetime_with_data(
    symbol: str,
    requested_end_dt: datetime,
    probe_timeframe: str = "1m",
    max_lookback_days: int = END_DATE_LOOKBACK_DAYS,
) -> datetime:
    """Resolve to the most recent full UTC day that still has market data."""
    requested_day_start = requested_end_dt.replace(hour=0, minute=0, second=0, microsecond=0)

    for day_offset in range(max_lookback_days + 1):
        candidate_day_start = requested_day_start - timedelta(days=day_offset)
        candidate_day_end_exclusive = candidate_day_start + timedelta(days=1)
        probe_df = _fetch_bars_with_retry(symbol, candidate_day_start, candidate_day_end_exclusive, probe_timeframe)
        if not probe_df.empty:
            resolved_end = candidate_day_end_exclusive - timedelta(seconds=1)
            if day_offset > 0:
                print(
                    f"[{symbol}] No data at requested end date; shifted anchor back {day_offset} day(s) "
                    f"to {candidate_day_start.date().isoformat()} (full day)"
                )
            return resolved_end

    raise RuntimeError(
        f"No {probe_timeframe} data for {symbol} within {max_lookback_days} day(s) before "
        f"{requested_end_dt.isoformat()}"
    )


def _choose_bin_size(n_bars: int) -> int:
    """Choose an odd bin size that keeps extrema readable across different span lengths."""
    if n_bars <= 120:
        return 5
    if n_bars <= 500:
        return 9
    if n_bars <= 1500:
        return 15

    # For larger windows, target about 100 bins across the series.
    bin_size = max(17, int(round(n_bars / 80.0)))
    if bin_size % 2 == 0:
        bin_size += 1
    return bin_size


def _filter_extrema(
    candidates: list[int],
    values: np.ndarray,
    half_window: int,
    min_separation: int,
    prominence_threshold: float,
    is_minima: bool,
) -> list[int]:
    """Keep only well-separated extrema with meaningful local prominence."""
    if not candidates:
        return []

    scored: list[tuple[float, int]] = []
    n = len(values)
    for idx in candidates:
        left = max(0, idx - half_window)
        right = min(n - 1, idx + half_window)
        local_slice = values[left : right + 1]
        if np.isnan(local_slice).any():
            continue

        if is_minima:
            prominence = float(local_slice.max() - values[idx])
        else:
            prominence = float(values[idx] - local_slice.min())

        if prominence >= prominence_threshold:
            scored.append((prominence, idx))

    # Select strongest extrema first and enforce a minimum gap in bars.
    scored.sort(reverse=True)
    selected: list[int] = []
    for _, idx in scored:
        if all(abs(idx - kept) >= min_separation for kept in selected):
            selected.append(idx)

    selected.sort()
    return selected


def _find_extrema_by_bar_buckets(close: pd.Series, bucket_bars: int) -> tuple[list[int], list[int]]:
    """Find one min and one max per contiguous bucket of bars.

    If min/max lands on the bucket's leftmost or rightmost bar, do not mark it.
    """
    if close.empty or bucket_bars <= 1:
        return [], []

    mins: list[int] = []
    maxs: list[int] = []
    n = len(close)

    for start in range(0, n, bucket_bars):
        end = min(n, start + bucket_bars)
        chunk = close.iloc[start:end]
        if len(chunk) < 3:
            continue

        min_idx = int(chunk.idxmin())
        max_idx = int(chunk.idxmax())

        # Skip bucket-edge extrema as requested.
        if min_idx not in (start, end - 1):
            mins.append(min_idx)
        if max_idx not in (start, end - 1):
            maxs.append(max_idx)

    return sorted(set(mins)), sorted(set(maxs))


def _find_aligned_groups_from_anchor(
    close: pd.Series,
    candidate_indices: list[int],
    anchor_idx: int,
    anchor_y: float | None = None,
    threshold_pct_of_range: float = 0.015,
    min_points: int = 3,
) -> list[list[int]]:
    """Find groups of points approximately collinear with one anchor point.

    The anchor point is used only to generate candidate lines and is not included
    in returned groups.
    """
    if close.empty:
        return []

    n = len(close)
    if n < 4:
        return []

    if anchor_idx < 0 or anchor_idx >= n:
        return []

    if anchor_y is None:
        anchor_y = float(close.iloc[anchor_idx])

    pts = sorted(set(i for i in candidate_indices if 0 <= i < n and i != anchor_idx))
    if len(pts) < min_points:
        return []

    y_min = float(close.min())
    y_max = float(close.max())
    y_range = max(1e-9, y_max - y_min)
    threshold_abs = y_range * threshold_pct_of_range

    seen: set[tuple[int, ...]] = set()
    raw_groups: list[list[int]] = []

    for base_idx in pts:
        base_y = float(close.iloc[base_idx])
        dx = anchor_idx - base_idx
        if dx == 0:
            continue
        slope = (anchor_y - base_y) / dx

        aligned: list[int] = []
        for i in pts:
            pred = anchor_y + slope * (i - anchor_idx)
            if abs(float(close.iloc[i]) - pred) <= threshold_abs:
                aligned.append(i)

        if len(aligned) >= min_points:
            key = tuple(sorted(aligned))
            if key not in seen:
                seen.add(key)
                raw_groups.append(list(key))

    # Keep larger groups first and drop strict subsets to avoid duplicate lines.
    raw_groups.sort(key=len, reverse=True)
    kept: list[list[int]] = []
    kept_sets: list[set[int]] = []
    for grp in raw_groups:
        grp_set = set(grp)
        if any(grp_set.issubset(existing) for existing in kept_sets):
            continue
        kept.append(grp)
        kept_sets.append(grp_set)

    return kept


def _plot_fitted_alignment_lines(
    ax: plt.Axes,
    timestamps: pd.Series,
    close: pd.Series,
    groups: list[list[int]],
    anchor_indices: list[int],
    max_lines: int = MAX_FITTED_LINES,
) -> int:
    """Fit and plot a line for each aligned group (without latest point)."""
    if not groups:
        return 0

    plotted = 0
    colors = ["#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"]
    latest_idx = len(close) - 1

    groups_sorted = sorted(groups, key=len, reverse=True)
    for line_idx, grp in enumerate(groups_sorted[:max_lines], start=1):
        fit_grp = [i for i in grp if i not in set(anchor_indices)]
        if len(fit_grp) < 3:
            continue

        x = np.asarray(fit_grp, dtype=float)
        y = close.iloc[fit_grp].to_numpy(dtype=float)
        m, b = np.polyfit(x, y, 1)

        x0 = int(min(fit_grp))
        x1 = latest_idx
        y0 = m * x0 + b
        y1 = m * x1 + b

        color = colors[(line_idx - 1) % len(colors)]
        ax.plot(
            [timestamps.iloc[x0], timestamps.iloc[x1]],
            [y0, y1],
            color=color,
            linewidth=1.0,
            alpha=0.8,
            linestyle="-",
            zorder=2,
        )
        ax.scatter(
            timestamps.iloc[fit_grp],
            close.iloc[fit_grp],
            s=44,
            facecolors="none",
            edgecolors=color,
            linewidths=1.3,
            zorder=4,
        )
        plotted += 1

    return plotted


def _format_axis(ax: plt.Axes, timeframe: str):
    """Apply date formatting based on chart timeframe."""
    if timeframe in {"1m", "5m", "15m"}:
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=6, maxticks=12))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d\n%H:%M"))
    elif timeframe == "1h":
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=6, maxticks=10))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d\n%H:%M"))
    else:
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=6, maxticks=10))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))

    for tick in ax.get_xticklabels():
        tick.set_rotation(45)
        tick.set_ha("right")


def _build_anchor_levels(low_value: float, high_value: float, level_count: int) -> list[float]:
    """Build evenly spaced anchor levels including low and high values."""
    if level_count <= 1:
        return [high_value]

    if np.isclose(high_value, low_value):
        return [high_value]

    # Return descending levels: high -> low.
    return list(np.linspace(high_value, low_value, num=level_count, dtype=float))


def _plot_span_page(
    pdf: PdfPages,
    symbol: str,
    span_cfg: SpanConfig,
    end_dt: datetime,
    anchor_level_count: int,
):
    start_dt = end_dt - span_cfg.delta
    df = _fetch_bars_with_retry(symbol, start_dt, end_dt, span_cfg.timeframe)

    if df.empty:
        fig, ax = plt.subplots(figsize=(14, 8))
        ax.text(0.5, 0.5, f"No data for {symbol} ({span_cfg.label}, {span_cfg.timeframe})", ha="center", va="center", fontsize=14)
        ax.axis("off")
        pdf.savefig(fig)
        plt.close(fig)
        print(f"[{span_cfg.label}] No data")
        return

    df = df.sort_values("timestamp").reset_index(drop=True)
    close = df["close"].astype(float)
    timestamps = pd.to_datetime(df["timestamp"], utc=True)

    mins, maxs = _find_extrema_by_bar_buckets(close, bucket_bars=span_cfg.bucket_bars)
    extrema_mode = f"bucket ({span_cfg.bucket_bars} bars)"

    latest_idx = len(close) - 1
    candidate_points = sorted(set(i for i in (mins + maxs) if i < latest_idx))
    last_min_idx = max(mins) if mins else None
    last_max_idx = max(maxs) if maxs else None

    anchor_idx = latest_idx
    anchor_levels: list[float] = []
    anchor_low_used: float | None = None
    anchor_high_used: float | None = None
    if last_min_idx is not None and last_max_idx is not None:
        last_min_value = float(close.iloc[last_min_idx])
        last_max_value = float(close.iloc[last_max_idx])
        current_price = float(close.iloc[latest_idx])
        lo = min(last_min_value, last_max_value)
        hi = max(last_min_value, last_max_value)

        # If current price is outside the last min/max range, extend by a
        # padding ratio beyond current price instead of clamping at price.
        if current_price < lo:
            width_to_max = max(1e-9, hi - current_price)
            anchor_low_used = current_price - (ANCHOR_OUTSIDE_PADDING_RATIO * width_to_max)
            anchor_high_used = hi
        elif current_price > hi:
            width_to_min = max(1e-9, current_price - lo)
            anchor_low_used = lo
            anchor_high_used = current_price + (ANCHOR_OUTSIDE_PADDING_RATIO * width_to_min)
        else:
            anchor_low_used = lo
            anchor_high_used = hi

        anchor_levels = _build_anchor_levels(anchor_low_used, anchor_high_used, anchor_level_count)

    aligned_groups: list[list[int]] = []
    for anchor_y in anchor_levels:
        groups_for_anchor = _find_aligned_groups_from_anchor(
            close,
            candidate_points,
            anchor_idx=anchor_idx,
            anchor_y=anchor_y,
            threshold_pct_of_range=ALIGNMENT_THRESHOLD_PCT,
            min_points=3,
        )
        aligned_groups.extend(groups_for_anchor)

    # De-duplicate groups across all anchor levels.
    dedup: dict[tuple[int, ...], list[int]] = {}
    for grp in aligned_groups:
        dedup[tuple(sorted(set(grp)))] = sorted(set(grp))
    aligned_groups = list(dedup.values())

    global_low_idx = int(close.idxmin())
    global_high_idx = int(close.idxmax())
    global_low_visible = True
    global_high_visible = True

    fig, ax = plt.subplots(figsize=(14, 8))
    ax.plot(timestamps, close, color="#1f77b4", linewidth=1.3, alpha=0.85, label="Close")

    if mins:
        ax.scatter(
            timestamps.iloc[mins],
            close.iloc[mins],
            color="#2ca02c",
            s=30,
            alpha=0.9,
            edgecolors="black",
            linewidths=0.3,
            label=f"Local Minima ({len(mins)})",
            zorder=3,
        )
    if maxs:
        ax.scatter(
            timestamps.iloc[maxs],
            close.iloc[maxs],
            color="#d62728",
            s=30,
            alpha=0.9,
            edgecolors="black",
            linewidths=0.3,
            label=f"Local Maxima ({len(maxs)})",
            zorder=3,
        )

    if anchor_levels:
        anchor_timestamps = [timestamps.iloc[anchor_idx]] * len(anchor_levels)
        ax.scatter(
            anchor_timestamps,
            anchor_levels,
            marker="D",
            s=ANCHOR_LEVEL_MARKER_SIZE,
            facecolors="#ffbf00",
            edgecolors="black",
            linewidths=0.8,
            label=f"Current-Date Anchor Levels ({len(anchor_levels)})",
            zorder=5,
        )

    if global_low_visible:
        ax.scatter(
            timestamps.iloc[global_low_idx],
            close.iloc[global_low_idx],
            marker="*",
            s=200,
            color="#0b7d2b",
            edgecolors="black",
            linewidths=0.7,
            label="Global Low",
            zorder=4,
        )
    if global_high_visible:
        ax.scatter(
            timestamps.iloc[global_high_idx],
            close.iloc[global_high_idx],
            marker="*",
            s=200,
            color="#a51414",
            edgecolors="black",
            linewidths=0.7,
            label="Global High",
            zorder=4,
        )

    fitted_line_count = _plot_fitted_alignment_lines(
        ax,
        timestamps,
        close,
        aligned_groups,
        anchor_indices=[anchor_idx],
    )

    ax.set_title(
        f"{symbol} | {span_cfg.label} Backward from {end_dt.strftime('%Y-%m-%d')}"
        f" | TF={span_cfg.timeframe}, Extrema={extrema_mode}",
        fontsize=13,
        fontweight="bold",
    )
    ax.set_xlabel("Time (UTC)")
    ax.set_ylabel("Price ($)")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    _format_axis(ax, span_cfg.timeframe)

    stats = (
        (f"Last Min: {close.iloc[last_min_idx]:.2f}\n" if last_min_idx is not None else "Last Min: -\n")
        + (f"Last Max: {close.iloc[last_max_idx]:.2f}\n" if last_max_idx is not None else "Last Max: -\n")
        + (
            f"Bars: {len(df)}\n"
            f"Start: {timestamps.iloc[0].strftime('%Y-%m-%d %H:%M')}\n"
            f"End:   {timestamps.iloc[-1].strftime('%Y-%m-%d %H:%M')}\n"
            f"Minima: {len(mins)}\n"
            f"Maxima: {len(maxs)}\n"
            f"Aligned Lines: {fitted_line_count}\n"
            f"Anchor Levels: {len(anchor_levels)}\n"
            f"Low: {close.iloc[global_low_idx]:.2f}\n"
            f"High: {close.iloc[global_high_idx]:.2f}\n"
            f"Current: {close.iloc[latest_idx]:.2f}\n"
        )
        + (f"Anchor Low Used: {anchor_low_used:.2f}" if anchor_low_used is not None else "Anchor Low Used: -")
        + (f"\nAnchor High Used: {anchor_high_used:.2f}" if anchor_high_used is not None else "\nAnchor High Used: -")
    )
    ax.text(
        0.012,
        0.988,
        stats,
        transform=ax.transAxes,
        fontsize=9,
        va="top",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white", alpha=0.8),
    )

    fig.tight_layout()
    pdf.savefig(fig)
    plt.close(fig)

    print(
        f"[{span_cfg.label}] TF={span_cfg.timeframe}, bars={len(df)}, "
        f"mode={extrema_mode}, minima={len(mins)}, maxima={len(maxs)}, "
        f"aligned_lines={fitted_line_count}, "
        f"anchor_levels={len(anchor_levels)}, "
        f"low={close.iloc[global_low_idx]:.2f} ({'shown' if global_low_visible else 'hidden@corner'}), "
        f"high={close.iloc[global_high_idx]:.2f} ({'shown' if global_high_visible else 'hidden@corner'})"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Plot one stock over multiple backward spans and mark local minima/maxima in one PDF."
    )
    parser.add_argument("symbol", type=str, help="Ticker symbol, e.g. AAPL")
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="Anchor end date/time (UTC). Examples: '2026-03-24', '2026-03-24 23:50:00+00:00'.",
    )
    parser.add_argument(
        "--anchor-level-count",
        type=int,
        default=DEFAULT_ANCHOR_LEVELS,
        help="How many current-date anchor levels to use between last max and min (>=2 recommended).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output PDF path (default: run_current/<SYMBOL>_extrema_windows.pdf)",
    )
    args = parser.parse_args()

    symbol = args.symbol.strip().upper()
    end_dt = _parse_end_datetime(args.end_date)
    anchor_level_count = max(1, int(args.anchor_level_count))

    output_path = Path(args.output) if args.output else Path("run_current") / f"{symbol}_extrema_windows.pdf"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    init_router(use_cache=True, cache_dir="data_cache")

    resolved_end_dt = _resolve_end_datetime_with_data(symbol, end_dt)

    print(f"Generating extrema PDF for {symbol}")
    print(f"Requested end datetime (UTC): {end_dt.isoformat()}")
    print(f"Resolved end datetime (UTC):  {resolved_end_dt.isoformat()}")
    print(f"Current-date anchor levels: {anchor_level_count}")
    print(f"Output: {output_path}")

    with PdfPages(output_path) as pdf:
        for span_cfg in SPAN_CONFIGS:
            _plot_span_page(pdf, symbol, span_cfg, resolved_end_dt, anchor_level_count)

    print(f"Saved PDF: {output_path}")


if __name__ == "__main__":
    main()
