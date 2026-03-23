"""Centralized helpers for multiframe processing, export, and visualization."""

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from config import (
    SMA_WINDOWS,
    SMA_PRE_SMOOTH_WINDOW,
    SMA_EXTREMA_CLUSTER_THRESHOLD_PCT,
    SMA_EXTREMA_MIN_TOUCHES,
    SMA_EXTREMA_MERGE_BAR_GAP,
)
from indicators import DEFAULT_TIMEFRAMES, precompute_reaction_levels_for_full_history


def build_sr_strategy_sets(penguins: Dict[str, object]) -> Tuple[set, set]:
    """Return (all_sr_strategies, sr_strategies_that_require_precompute)."""
    sr_penguin_names = {
        name for name, penguin in penguins.items() if getattr(penguin, "USES_SR_LINES", False)
    }
    precompute_sr_penguin_names = {
        name
        for name, penguin in penguins.items()
        if getattr(penguin, "USES_SR_LINES", False)
        and getattr(penguin, "REQUIRES_SR_PRECOMPUTE", True)
    }
    return sr_penguin_names, precompute_sr_penguin_names


def precompute_multiframe_levels(
    data: Dict[str, Dict],
    symbols: List[str],
    sorted_timestamps: List[datetime],
) -> Dict[str, List[Dict[str, List[float]]]]:
    """Precompute reaction levels per symbol using available history."""
    precomputed_sr_data: Dict[str, List[Dict[str, List[float]]]] = {}
    for symbol in symbols:
        symbol_data = data[symbol]
        prices = [symbol_data[ts]["close"] for ts in sorted_timestamps if ts in symbol_data]
        if prices:
            precomputed_sr_data[symbol] = precompute_reaction_levels_for_full_history(
                prices=prices,
                timeframes=DEFAULT_TIMEFRAMES,
                cluster_tolerance_pct=0.006,
                max_levels_per_timeframe=3,
            )
    return precomputed_sr_data


def set_precomputed_levels_on_penguins(
    penguins: Dict[str, object],
    penguin_names: set,
    precomputed_sr_data: Dict[str, List[Dict[str, List[float]]]],
) -> None:
    """Push precomputed level payload into selected strategies."""
    for penguin_name in penguin_names:
        penguin = penguins[penguin_name]
        if hasattr(penguin, "set_precomputed_levels"):
            penguin.set_precomputed_levels(precomputed_sr_data)


def compute_sma_series(values: List[float], window: int) -> List[float]:
    """Compute SMA with None padding before the first full window."""
    out: List[float] = [None] * len(values)
    if window <= 0 or len(values) < window:
        return out

    running_sum = 0.0
    non_none_count = 0
    for idx, value in enumerate(values):
        if value is not None:
            running_sum += value
            non_none_count += 1
        if idx >= window:
            old_value = values[idx - window]
            if old_value is not None:
                running_sum -= old_value
                non_none_count -= 1
        if idx >= window - 1 and non_none_count == window:
            out[idx] = running_sum / window
    return out


def extract_sma_extrema(sma_values: List[float]):
    """Return local extrema as tuples: (index, 'peak'|'valley', value)."""
    extrema = []
    for idx in range(1, len(sma_values) - 1):
        prev_v = sma_values[idx - 1]
        curr_v = sma_values[idx]
        next_v = sma_values[idx + 1]

        if prev_v is None or curr_v is None or next_v is None:
            continue

        is_peak = (curr_v > prev_v and curr_v >= next_v) or (curr_v >= prev_v and curr_v > next_v)
        is_valley = (curr_v < prev_v and curr_v <= next_v) or (curr_v <= prev_v and curr_v < next_v)

        if is_peak:
            extrema.append((idx, "peak", curr_v))
        elif is_valley:
            extrema.append((idx, "valley", curr_v))

    return extrema


def export_sma_extrema_for_symbols(
    symbol_close_series: Dict[str, List[Tuple[datetime, float]]],
    sma_windows: List[int],
    output_dir: Path,
) -> List[Path]:
    """Export per-symbol CSV files containing only SMA extrema rows."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written_files: List[Path] = []

    windows = sorted({int(w) for w in sma_windows if int(w) > 0})
    for symbol, rows in symbol_close_series.items():
        if not rows:
            continue

        timestamps = [ts for ts, _ in rows]
        closes = [float(price) for _, price in rows]
        pre_smoothed = compute_sma_series(closes, SMA_PRE_SMOOTH_WINDOW)
        sma_columns = {w: compute_sma_series(pre_smoothed, w) for w in windows}

        out_file = output_dir / f"{symbol}_sma_extrema.csv"
        with open(out_file, "w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["timestamp", "sma_window", "extrema_type", "sma_value"])

            for w in windows:
                extrema_rows = extract_sma_extrema(sma_columns[w])
                for idx, extrema_type, sma_val in extrema_rows:
                    writer.writerow([
                        timestamps[idx].isoformat(),
                        w,
                        extrema_type,
                        f"{sma_val:.6f}",
                    ])

        written_files.append(out_file)

    return written_files


def _build_ticks_from_timestamps(bar_timestamps, num_bars):
    """Build deterministic x-axis ticks/labels from timestamps."""
    if not bar_timestamps:
        interval = max(1, num_bars // 10)
        x_ticks = list(range(1, num_bars + 1, interval))
        if num_bars > 0 and x_ticks[-1] != num_bars:
            x_ticks.append(num_bars)
        x_labels = [f"Bar {i}" for i in x_ticks]
        return x_ticks, x_labels

    total_bars = min(num_bars, len(bar_timestamps)) if num_bars else len(bar_timestamps)
    if total_bars <= 0:
        return [], []

    first_dt = bar_timestamps[0]
    last_dt = bar_timestamps[total_bars - 1]
    span_minutes = max(1, int((last_dt - first_dt).total_seconds() // 60))

    if span_minutes <= 120:
        label_fmt = "%H:%M"
    elif span_minutes <= 1440:
        label_fmt = "%b %d\n%H:%M"
    else:
        label_fmt = "%b %d"

    interval = max(1, total_bars // 10)
    tick_indices = list(range(0, total_bars, interval))
    if tick_indices[-1] != total_bars - 1:
        tick_indices.append(total_bars - 1)

    x_ticks = [idx + 1 for idx in tick_indices]
    x_labels = [bar_timestamps[idx].strftime(label_fmt) for idx in tick_indices]
    return x_ticks, x_labels


def _cluster_levels(levels, threshold_pct):
    """Cluster nearby price levels and return (center, count) clusters."""
    if not levels:
        return []

    sorted_levels = sorted(levels)
    clusters = [[sorted_levels[0]]]
    for level in sorted_levels[1:]:
        center = sum(clusters[-1]) / len(clusters[-1])
        if center > 0 and abs(level - center) / center <= threshold_pct:
            clusters[-1].append(level)
        else:
            clusters.append([level])

    out = []
    for cluster in clusters:
        center = sum(cluster) / len(cluster)
        out.append((center, len(cluster)))
    return out


def _build_non_overlapping_clusters(levels, threshold_pct, min_touches):
    """
    Build level clusters with strict one-time assignment.

    Once a value is used by one cluster, it is removed and cannot be reused
    for any later cluster.
    """
    ordered_levels = list(levels)
    if not ordered_levels:
        return []

    used = [False] * len(ordered_levels)
    clusters = []

    # Walk in chronological extraction order (first peak/valley first).
    for seed_idx, seed_val in enumerate(ordered_levels):
        if used[seed_idx]:
            continue
        if seed_val <= 0:
            continue

        members = {seed_idx}
        center = seed_val

        # Expand cluster iteratively around the running mean.
        changed = True
        while changed:
            changed = False
            for idx, value in enumerate(ordered_levels):
                if used[idx] or idx in members:
                    continue
                if center > 0 and abs(value - center) / center <= threshold_pct:
                    members.add(idx)
                    changed = True

            if changed:
                center = sum(ordered_levels[idx] for idx in members) / len(members)

        if len(members) >= min_touches:
            center = sum(ordered_levels[idx] for idx in members) / len(members)
            clusters.append((center, len(members)))

            # Consume all matched points so they cannot seed another line.
            for idx in members:
                used[idx] = True

    return clusters


def _merge_nearby_extrema_events(extrema, max_bar_gap):
    """Merge extrema close in time into one event so they count as one touch."""
    if not extrema:
        return []

    merged = []
    group = [extrema[0]]

    for idx, kind, value in extrema[1:]:
        prev_idx = group[-1][0]
        if idx - prev_idx <= max_bar_gap:
            group.append((idx, kind, value))
        else:
            rep_idx = int(round(sum(item[0] for item in group) / len(group)))
            rep_val = sum(item[2] for item in group) / len(group)
            rep_kind = group[-1][1]
            merged.append((rep_idx, rep_kind, rep_val))
            group = [(idx, kind, value)]

    rep_idx = int(round(sum(item[0] for item in group) / len(group)))
    rep_val = sum(item[2] for item in group) / len(group)
    rep_kind = group[-1][1]
    merged.append((rep_idx, rep_kind, rep_val))
    return merged


def _window_scaled_threshold_pct(window: int, all_windows: List[int]) -> float:
    """Scale threshold by SMA window: lower window -> smaller threshold."""
    if not all_windows:
        return SMA_EXTREMA_CLUSTER_THRESHOLD_PCT

    max_window = max(all_windows)
    if max_window <= 0:
        return SMA_EXTREMA_CLUSTER_THRESHOLD_PCT

    scaled = SMA_EXTREMA_CLUSTER_THRESHOLD_PCT * (window / max_window)
    # Keep a strict floor while avoiding near-zero thresholds.
    return max(scaled, SMA_EXTREMA_CLUSTER_THRESHOLD_PCT * 0.20)


def plot_multitimeframe_sr_history(sr_history_by_symbol, output_dir, bar_timestamps=None):
    """Plot per-symbol price + SMA/extrema levels for multiframe overview pages."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    created_files = []
    sma_windows = sorted({int(w) for w in SMA_WINDOWS if int(w) > 0})
    sma_colors = {
        50: "#ff7f0e",
        100: "#2ca02c",
        200: "#d62728",
        500: "#9467bd",
    }

    for symbol, snapshots in sorted(sr_history_by_symbol.items()):
        if not snapshots:
            continue

        n = len(snapshots)
        x = list(range(1, n + 1))
        prices = [float(row.get("price")) for row in snapshots if row.get("price") is not None]
        if len(prices) != n:
            continue

        symbol_timestamps = [row.get("timestamp") for row in snapshots if row.get("timestamp") is not None]
        if len(symbol_timestamps) != n:
            symbol_timestamps = bar_timestamps

        plt.figure(figsize=(15, 8))
        plt.plot(x, prices, color="black", linewidth=1.8, alpha=0.9, label="Price")

        for window in sma_windows:
            pre_smoothed = compute_sma_series(prices, SMA_PRE_SMOOTH_WINDOW)
            sma_values = compute_sma_series(pre_smoothed, window)
            if any(v is not None for v in sma_values):
                color = sma_colors.get(window)
                plt.plot(x, sma_values, linewidth=1.2, alpha=0.9, color=color, label=f"SMA {window}")

                extrema = extract_sma_extrema(sma_values)
                extrema_events = _merge_nearby_extrema_events(extrema, SMA_EXTREMA_MERGE_BAR_GAP)

                peak_x = [idx + 1 for idx, kind, _ in extrema_events if kind == "peak"]
                peak_y = [val for _, kind, val in extrema_events if kind == "peak"]
                valley_x = [idx + 1 for idx, kind, _ in extrema_events if kind == "valley"]
                valley_y = [val for _, kind, val in extrema_events if kind == "valley"]

                if peak_x:
                    plt.scatter(peak_x, peak_y, marker="^", s=14, color=color, alpha=0.75)
                if valley_x:
                    plt.scatter(valley_x, valley_y, marker="v", s=14, color=color, alpha=0.75)

                threshold_pct = _window_scaled_threshold_pct(window, sma_windows)

                # Cluster all extrema together so each high/low point belongs to exactly one line.
                # This avoids near-duplicate peak/valley lines at almost identical prices.
                extrema_clustered = _build_non_overlapping_clusters(
                    [val for _, _, val in extrema_events],
                    threshold_pct,
                    SMA_EXTREMA_MIN_TOUCHES,
                )

                for idx, (level, touches) in enumerate(extrema_clustered):
                    plt.axhline(
                        y=level,
                        color=color,
                        linestyle="--",
                        linewidth=min(2.2, 0.9 + 0.15 * touches),
                        alpha=0.30,
                        label=f"SMA {window} extrema lvl" if idx == 0 else None,
                    )

        x_ticks, x_labels = _build_ticks_from_timestamps(symbol_timestamps, n)
        if x_ticks and x_labels:
            plt.xticks(x_ticks, x_labels, rotation=45, ha="right", fontsize=9)
            plt.xlabel("Date / Time")
        else:
            plt.xlabel("Bar")

        plt.ylabel("Price ($)")
        plt.title(f"{symbol} - Price + SMA")
        plt.grid(True, alpha=0.25)
        plt.legend(loc="best", fontsize=8)
        plt.tight_layout()

        out_file = output_dir / f"{symbol}_multitimeframe_sr.png"
        plt.savefig(out_file, dpi=120)
        plt.close()
        created_files.append(str(out_file))

    return created_files


def create_multiframe_png_gallery_pdf(png_files, output_pdf):
    """Combine multiframe PNG plots into one multi-page PDF."""
    if not png_files:
        return None

    def _symbol_from_png_stem(stem: str) -> str:
        for suffix in ("_multitimeframe_sr", "_multiframe_sr", "_sr_lines", "_sr"):
            if stem.endswith(suffix):
                return stem[: -len(suffix)]
        return stem

    output_pdf = Path(output_pdf)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    sorted_pngs = sorted([Path(p) for p in png_files], key=lambda p: p.name.lower())

    with PdfPages(output_pdf) as pdf:
        for png_path in sorted_pngs:
            if not png_path.exists():
                continue

            img = plt.imread(png_path)
            fig, ax = plt.subplots(figsize=(14, 8))
            ax.imshow(img)
            ax.axis("off")
            symbol_label = _symbol_from_png_stem(png_path.stem)
            ax.set_title(f"Multiframe S/R: {symbol_label}", fontsize=12)
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)

    return str(output_pdf)
