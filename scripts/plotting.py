"""Enhanced plotting and PDF report generation using matplotlib and PdfPages."""
import os
import math
from pathlib import Path

mpl_config_dir = Path(os.environ.get("MPLCONFIGDIR", "/private/tmp/penguin_mplconfig"))
xdg_cache_dir = Path(os.environ.get("XDG_CACHE_HOME", "/private/tmp/penguin_xdg_cache"))
try:
    mpl_config_dir.mkdir(parents=True, exist_ok=True)
    xdg_cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_config_dir))
    os.environ.setdefault("XDG_CACHE_HOME", str(xdg_cache_dir))
    os.environ.setdefault("MPLBACKEND", "Agg")
except Exception:
    pass

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.colors import Normalize
from datetime import datetime, timedelta
import pytz
import csv
from config import INITIAL_CAPITAL


def _display_strategy_name(name: str) -> str:
    """Use a stable plot label for known benchmark names and the penguin name otherwise."""
    if name.startswith("SP500"):
        return "SP500"
    return name


def _is_sp500_benchmark(name: str) -> bool:
    return name.startswith("SP500")


def _strategy_group_key(name: str) -> tuple[int, str]:
    """Sort trainable/manual strategies into adjacent pairs."""
    order_map = {
        "SP500": 0,
        "OG_TP1": 10,
        "OG_TP1_Manual": 11,
        "OG_TP2": 12,
        "OG_TP2_Manual": 13,
        "OG_TP3": 14,
        "OG_TP3_Manual": 15,
        "OG_TP4": 16,
        "OG_TP4_Manual": 17,
        "Adv_SELL_TP1": 20,
        "Adv_SELL_TP1_Manual": 21,
        "Adv_SELL_TP2": 22,
        "Adv_SELL_TP2_Manual": 23,
        "Adv_SELL_TP3": 24,
        "Adv_SELL_TP3_Manual": 25,
        "Adv_SELL_TP4": 26,
        "Adv_SELL_TP4_Manual": 27,
        "SP500x2": 40,
        "SMA20Penguin": 50,
    }
    return order_map.get(name, 100), name


def _strategy_base_key(name: str) -> str:
    """Return the shared base key for a trainable/manual pair."""
    if name.endswith("_Manual"):
        return name[:-7]
    return name


def _strategy_line_style(name: str) -> str:
    return "--" if name.endswith("_Manual") else "-"


def _build_report_page_groups(strategy_names: list[str]) -> list[list[str]]:
    """Group paired trainable/manual strategies onto the same report page."""
    ordered_names = sorted(strategy_names, key=_strategy_group_key)
    available_names = set(strategy_names)
    consumed_names: set[str] = set()
    page_groups: list[list[str]] = []

    paired_bases = {
        "OG_TP1",
        "OG_TP2",
        "OG_TP3",
        "OG_TP4",
        "Adv_SELL_TP1",
        "Adv_SELL_TP2",
        "Adv_SELL_TP3",
        "Adv_SELL_TP4",
    }

    for name in ordered_names:
        if name in consumed_names:
            continue

        base_name = _strategy_base_key(name)
        manual_name = f"{base_name}_Manual"
        if base_name in paired_bases and name == base_name and manual_name in available_names:
            page_groups.append([name, manual_name])
            consumed_names.add(name)
            consumed_names.add(manual_name)
            continue

        page_groups.append([name])
        consumed_names.add(name)

    return page_groups


def _strategy_parameter_text(strategy_name: str) -> str | None:
    """Return a short parameter summary for RSI strategies."""
    rsi_parameter_map = {
        "RSIMeanReversionPenguin": "RSI period=14 | oversold=30 | overbought=70 | cooldown=none",
        "RSIMeanReversionPenguinStrict1": "RSI period=14 | oversold=29 | overbought=71 | cooldown=0",
        "RSIMeanReversionPenguinStrict2": "RSI period=14 | oversold=26 | overbought=71 | cooldown=0",
        "RSIMeanReversionReducedPenguin": "RSI period=14 | adaptive boundaries | target=1-10 trades/day",
        "RSIMeanReversionMomentumPenguin": "RSI period=14 | 3-stage momentum | RISING(35/80) FALLING(25/65) HOLDING(30/70)",
    }
    return rsi_parameter_map.get(strategy_name)


def _save_strategy_summary_to_artifacts(
    internal_name: str,
    display_name: str,
    summary: dict,
    cash: float,
    market_value: float,
    total_value: float,
    total_buy_count: int,
    total_sell_count: int,
    total_pnl: float,
    artifacts_dir,
):
    """Save strategy summary data to a CSV file in artifacts/csv directory."""
    artifacts_path = Path(artifacts_dir)
    artifacts_path.mkdir(parents=True, exist_ok=True)
    
    # Save as CSV for easy import into spreadsheets
    csv_dir = artifacts_path / "csv"
    csv_dir.mkdir(parents=True, exist_ok=True)
    csv_file = csv_dir / f"{internal_name}_summary.csv"

    total_qty_bought = sum(s["total_qty_bought"] for s in summary.values())
    total_qty_sold = sum(s["total_qty_sold"] for s in summary.values())
    realized_pnl = sum(s["realized_pnl"] for s in summary.values())
    unrealized_pnl = sum(s["unrealized_pnl"] for s in summary.values())
    open_positions = sum(1 for s in summary.values() if s["position_qty"] > 0)
    
    with open(csv_file, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Header with strategy info
        writer.writerow([f"Strategy Summary: {display_name}"])
        writer.writerow([])
        
        # Portfolio totals
        writer.writerow(["Portfolio Totals"])
        writer.writerow(["Cash", f"${cash:,.2f}"])
        writer.writerow(["Total Value", f"${total_value:,.2f}"])
        writer.writerow(["Total Buy Count", total_buy_count])
        writer.writerow(["Total Sell Count", total_sell_count])
        writer.writerow(["Total Shares Bought", total_qty_bought])
        writer.writerow(["Total Shares Sold", total_qty_sold])
        writer.writerow(["Realized PnL", f"${realized_pnl:,.2f}"])
        writer.writerow(["Total PnL", f"${total_pnl:,.2f}"])
        writer.writerow(["Open Positions", open_positions])
        writer.writerow([])
        
        # Per-symbol summary
        writer.writerow([
            "Symbol",
            "Buy Count",
            "Sell Count",
            "Shares Bought",
            "Shares Sold",
            "Position Qty",
            "Total Cost",
            "Total Revenue",
            "Realized PnL",
            "Total PnL",
            "PnL %",
        ])
        for symbol in sorted(summary.keys()):
            s = summary[symbol]
            writer.writerow([
                symbol,
                s["buy_count"],
                s["sell_count"],
                s["total_qty_bought"],
                s["total_qty_sold"],
                s["position_qty"],
                f"${s['total_cost']:,.2f}",
                f"${s['total_revenue']:,.2f}",
                f"${s['realized_pnl']:,.2f}",
                f"${s['total_pnl']:,.2f}",
                f"{s['pnl_pct']:+.2f}%",
            ])


def _aggregate_strategy_summary(summary: dict) -> dict:
    """Aggregate per-symbol summary data into strategy-level totals."""
    totals = {
        "buy_count": 0,
        "sell_count": 0,
        "total_qty_bought": 0,
        "total_qty_sold": 0,
        "total_cost": 0.0,
        "total_revenue": 0.0,
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "total_pnl": 0.0,
        "open_positions": 0,
    }

    for symbol_summary in summary.values():
        totals["buy_count"] += symbol_summary["buy_count"]
        totals["sell_count"] += symbol_summary["sell_count"]
        totals["total_qty_bought"] += symbol_summary["total_qty_bought"]
        totals["total_qty_sold"] += symbol_summary["total_qty_sold"]
        totals["total_cost"] += symbol_summary["total_cost"]
        totals["total_revenue"] += symbol_summary["total_revenue"]
        totals["realized_pnl"] += symbol_summary["realized_pnl"]
        totals["unrealized_pnl"] += symbol_summary["unrealized_pnl"]
        totals["total_pnl"] += symbol_summary["total_pnl"]
        if symbol_summary["position_qty"] > 0:
            totals["open_positions"] += 1

    totals["total_trades"] = totals["buy_count"] + totals["sell_count"]
    return totals


def _format_param_summary(params: dict[str, int | float], limit: int = 6) -> str:
    if not params:
        return "<no parameters>"

    display_name_map = {
        "adx_period": "adx_period",
        "adx_threshold": "adx_thr",
        "bb_period": "bb_period",
        "bb_stddev": "bb_std",
        "buy_rsi": "buy_rsi",
        "cooldown_bars": "cooldown",
        "max_cash_fraction": "max_cash_fpt",
        "rsi_period": "rsi_period",
        "sell_rsi": "sell_rsi",
        "stop_loss_pct": "stop_loss",
        "take_profit_pct": "take_profit",
    }

    def format_value(value: int | float) -> str:
        if isinstance(value, bool):
            return str(value)
        if isinstance(value, int):
            return str(value)
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return str(value)

    ordered_items = sorted(params.items())
    if len(ordered_items) <= limit:
        return ", ".join(
            f"{display_name_map.get(key, key)}={format_value(value)}" for key, value in ordered_items
        )

    head = ", ".join(
        f"{display_name_map.get(key, key)}={format_value(value)}" for key, value in ordered_items[:limit]
    )
    return f"{head}, ... (+{len(ordered_items) - limit} more)"


def _parameter_normalization_scales(parameter_sets: list[dict[str, int | float]]) -> dict[str, float]:
    scales: dict[str, float] = {}
    values_by_key: dict[str, list[float]] = {}

    for params in parameter_sets:
        if not isinstance(params, dict):
            continue
        for key, value in params.items():
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                continue
            values_by_key.setdefault(key, []).append(numeric_value)

    for key, values in values_by_key.items():
        if not values:
            continue
        min_value = min(values)
        max_value = max(values)
        span = max_value - min_value
        scales[key] = span if span > 0 else 1.0

    return scales


def _parameter_l2_distance(
    current_params: dict[str, int | float],
    optimal_params: dict[str, int | float],
    normalization_scales: dict[str, float] | None = None,
) -> float:
    if not current_params or not optimal_params:
        return float("nan")

    squared_distance = 0.0
    for key in sorted(set(current_params) | set(optimal_params)):
        current_value = current_params.get(key)
        optimal_value = optimal_params.get(key)
        if current_value is None or optimal_value is None:
            continue
        try:
            scale = float((normalization_scales or {}).get(key, 1.0))
            if not math.isfinite(scale) or scale <= 0:
                scale = 1.0
            delta = (float(current_value) - float(optimal_value)) / scale
        except (TypeError, ValueError):
            continue
        squared_distance += delta * delta
    return math.sqrt(squared_distance)


def create_training_pareto_pdf(
    training_history: dict[str, list[dict]],
    parameter_history: list[dict],
    trained_parameters: dict[str, dict],
    output_pdf,
    title: str = "Pareto Front",
    relative_to: int | str = 0,
    transaction_cost: float = 0.0,
):
    """Create a multi-page PDF with one buy-vs-profit scatter plot per strategy."""
    output_path = Path(output_pdf)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    use_relative_benchmark = relative_to not in (0, "0", None, False)
    profit_axis_label = (
        f"Profit amount relative to {relative_to} ($)" if use_relative_benchmark else "Profit amount relative to 0 ($)"
    )
    best_profit_label = f"profit relative to {relative_to}" if use_relative_benchmark else "profit relative to 0"
    plot_title_suffix = f" relative to {relative_to}" if use_relative_benchmark else " relative to 0"

    parameter_history_by_strategy: dict[str, dict[int, dict[str, int | float]]] = {}
    for entry in parameter_history:
        strategy_name = entry.get("strategy")
        trial_number = entry.get("trial")
        params = entry.get("params")
        if not isinstance(strategy_name, str) or not isinstance(trial_number, int) or not isinstance(params, dict):
            continue
        strategy_map = parameter_history_by_strategy.setdefault(strategy_name, {})
        strategy_map[trial_number] = params

    with PdfPages(output_path) as pdf:
        for strategy_name in sorted(training_history):
            trial_history = training_history.get(strategy_name, [])
            completed_trials = [trial for trial in trial_history if trial.get("status") == "completed"]
            optimal_params = dict((trained_parameters.get(strategy_name) or {}).get("best_params") or {})
            trial_parameter_map = parameter_history_by_strategy.get(strategy_name, {})
            normalization_scales = _parameter_normalization_scales([optimal_params, *trial_parameter_map.values()])

            fig, ax = plt.subplots(figsize=(10, 7))
            fig.suptitle(f"{title}: {strategy_name}", fontsize=16, fontweight="bold", x=0.5, y=0.975, ha="center")
            fig.subplots_adjust(top=0.82)

            if completed_trials:
                x_values = [int(trial.get("buy_trades", trial.get("total_trades", 0))) for trial in completed_trials]
                y_values = [float(trial.get("relative_profit_amount", trial.get("profit_amount", 0.0))) for trial in completed_trials]
                trial_numbers = [int(trial.get("trial", 0)) for trial in completed_trials]
                distance_values = [
                    _parameter_l2_distance(
                        trial_parameter_map.get(trial_number, {}),
                        optimal_params,
                        normalization_scales,
                    )
                    for trial_number in trial_numbers
                ]
                finite_distance_values = [value for value in distance_values if math.isfinite(value)]
                if finite_distance_values:
                    min_distance = min(finite_distance_values)
                    max_distance = max(finite_distance_values)
                    if max_distance == min_distance:
                        max_distance = min_distance + 1e-9
                    color_norm = Normalize(vmin=min_distance, vmax=max_distance)
                else:
                    color_norm = None

                scatter = ax.scatter(
                    x_values,
                    y_values,
                    c=distance_values,
                    cmap="viridis_r",
                    norm=color_norm,
                    s=55,
                    alpha=0.85,
                    edgecolors="black",
                    linewidths=0.5,
                    zorder=4,
                )

                for x_value, y_value, trial_number in zip(x_values, y_values, trial_numbers):
                    ax.annotate(
                        str(trial_number),
                        (x_value, y_value),
                        textcoords="offset points",
                        xytext=(5, 4),
                        fontsize=8,
                        zorder=1,
                    )

                cbar = fig.colorbar(scatter, ax=ax)
                cbar.set_label("Normalized L2 distance to optimal parameters")

                best_trial = max(
                    completed_trials,
                    key=lambda trial: float((trial.get("score") or [float("-inf")])[0]),
                )
                best_trial_number = int(best_trial.get("trial", 0))
                best_x = int(best_trial.get("buy_trades", best_trial.get("total_trades", 0)))
                best_y = float(best_trial.get("relative_profit_amount", best_trial.get("profit_amount", 0.0)))
                best_params = dict(trial_parameter_map.get(best_trial_number, {}))

                ax.scatter(
                    [best_x],
                    [best_y],
                    s=120,
                    color="red",
                    edgecolors="black",
                    linewidths=1.0,
                    zorder=6,
                    label="Best / chosen",
                )

                best_box_text = (
                    f"Best / chosen\n"
                    f"trial {best_trial_number:03d}; net=${float(best_trial.get('score', [0.0])[0]):,.2f}; {best_profit_label}=${best_y:,.2f}\n"
                    f"\n"
                    f"params={_format_param_summary(best_params)}"
                )
                fig.text(
                    0.5,
                    0.935,
                    best_box_text,
                    ha="center",
                    va="top",
                    fontsize=7,
                    bbox={"boxstyle": "round,pad=0.22", "fc": "white", "ec": "black", "alpha": 0.96},
                )
            else:
                ax.text(0.5, 0.5, "No completed trials available", ha="center", va="center", transform=ax.transAxes)

            ax.set_xlabel("Number of buys")
            ax.set_ylabel(profit_axis_label)
            ax.grid(True, alpha=0.25)

            # Net score is zero when relative profit equals transaction_cost * number_of_buys.
            if completed_trials:
                max_trades = max(x_values) if x_values else 0
            else:
                max_trades = 0
            x_line_max = max(max_trades, 1)
            ax.plot(
                [0, x_line_max],
                [0, float(transaction_cost) * x_line_max],
                color="gray",
                linestyle="--",
                linewidth=0.8,
                alpha=0.9,
                label="net score = 0",
                zorder=1,
            )

            ax.axvline(0.0, color="gray", linestyle=":", linewidth=1, alpha=0.4)
            ax.set_title(f"{strategy_name} buy-count vs profit{plot_title_suffix}")
            if completed_trials:
                ax.legend(loc="best", fontsize=9)

            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)

    print(f"Training Pareto PDF saved to {output_path}")



def _parse_datetime_string(dt_str: str) -> datetime:
    """Parse datetime from config format string."""
    for fmt in ["%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S"]:
        try:
            dt = datetime.strptime(dt_str.strip(), fmt)
            if dt.tzinfo is None:
                dt = pytz.UTC.localize(dt)
            return dt
        except ValueError:
            continue
    raise ValueError(f"Cannot parse datetime: {dt_str}")


def _build_ticks_from_timestamps(bar_timestamps, num_bars):
    """
    Build x-axis ticks/labels from actual bar timestamps.
    - For spans <= 60 days: Show ticks every 7 days, format "DD Mon"
    - For spans 60-365 days: Show ticks every month, format "Mon" or "Mon YYYY" for January
    - For spans > 365 days: Show ticks every 3 months, format "Mon" or "Mon YYYY" for January
    """
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
    
    # Calculate span in days
    span_days = (last_dt - first_dt).days
    
    # Determine tick placement strategy
    tick_dates = []
    
    if span_days <= 60:
        # Small span: show ticks every 7 days
        current_date = first_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        while current_date <= last_dt:
            tick_dates.append(current_date)
            current_date = current_date + timedelta(days=7)
    elif span_days <= 365:
        # Medium span (up to 1 year): show only the 1st of each month
        current_date = first_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        while current_date <= last_dt:
            tick_dates.append(current_date)
            # Move to the 1st of next month
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)
    else:
        # Large span: show only every 3 months (quarterly)
        current_date = first_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        while current_date <= last_dt:
            tick_dates.append(current_date)
            # Move to the same day 3 months later
            new_month = current_date.month + 3
            new_year = current_date.year
            if new_month > 12:
                new_month -= 12
                new_year += 1
            current_date = current_date.replace(year=new_year, month=new_month)
    
    # Find the bar indices closest to each tick date
    tick_indices = []
    for tick_date in tick_dates:
        closest_idx = 0
        min_diff = abs((bar_timestamps[0] - tick_date).total_seconds())
        for i in range(total_bars):
            diff = abs((bar_timestamps[i] - tick_date).total_seconds())
            if diff < min_diff:
                min_diff = diff
                closest_idx = i
        if closest_idx not in tick_indices:
            tick_indices.append(closest_idx)
    
    # Sort indices
    tick_indices.sort()
    
    # Build labels with appropriate format
    # Only show year for January, otherwise just month
    x_ticks = [idx + 1 for idx in tick_indices]
    x_labels = []
    for idx in tick_indices:
        dt = bar_timestamps[idx]
        if span_days <= 60:
            # Short span: always show day and month
            x_labels.append(dt.strftime('%d %b'))
        else:
            # Medium/long span: show year only for January
            if dt.month == 1:
                x_labels.append(dt.strftime('%b %Y'))
            else:
                x_labels.append(dt.strftime('%b'))
    
    return x_ticks, x_labels


def _build_timespan_text(start_date_str=None, stop_date_str=None, bar_timestamps=None, num_bars=None):
    """Build a human-readable timespan string for chart/report titles."""
    def _fmt_dt(dt: datetime) -> str:
        return dt.strftime("%y-%m-%d")

    if bar_timestamps:
        total_bars = min(num_bars, len(bar_timestamps)) if num_bars else len(bar_timestamps)
        if total_bars > 0:
            start_dt = bar_timestamps[0]
            stop_dt = bar_timestamps[total_bars - 1]
            return f"{_fmt_dt(start_dt)} to {_fmt_dt(stop_dt)}"

    if start_date_str and stop_date_str:
        try:
            start_dt = _parse_datetime_string(start_date_str)
            stop_dt = _parse_datetime_string(stop_date_str)
            return f"{_fmt_dt(start_dt)} to {_fmt_dt(stop_dt)}"
        except Exception:
            # Keep title useful even if parsing fails.
            return f"{start_date_str.strip()} to {stop_date_str.strip()}"

    return ""


def plot_capital_curves(curves, filename, num_bars=None, binning="1m", start_date_str=None, stop_date_str=None, bar_timestamps=None, symbol_list_name=None):
    """
    Plot and save capital curves with smart x-axis showing actual dates/times.
    
    Args:
        curves: Dict[strategy_name] = list of capital values
        filename: Path to save PNG
        num_bars: Number of bars (for x-axis scaling calculation)
        binning: "1m", "5m", "15m", "1h", "1d" (for x-axis scaling calculation)
        start_date_str: Start date string (e.g., "2026-02-20 14:30:00")
        stop_date_str: Stop date string (e.g., "2026-02-21 23:50:00")
    """
    # Match PDF page-1 styling so PNG and report look consistent.
    plt.figure(figsize=(12, 8))
    
    # Determine x-axis based on actual dates and number of bars
    if num_bars is None:
        num_bars = len(list(curves.values())[0]) if curves else 0
    
    binning_map = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "1d": 1440}
    minutes_per_bar = binning_map.get(binning, 1)
    total_minutes = num_bars * minutes_per_bar
    
    # Parse actual start/stop dates if provided
    x_ticks = []
    x_labels = []
    x_label_text = "Time"
    
    if bar_timestamps:
        x_ticks, x_labels = _build_ticks_from_timestamps(bar_timestamps, num_bars)
        x_label_text = "Date / Time"
    elif start_date_str and stop_date_str:
        try:
            start_dt = _parse_datetime_string(start_date_str)
            stop_dt = _parse_datetime_string(stop_date_str)
            
            # Generate ticks based on duration
            if total_minutes <= 120:  # <= 2 hours: every 15 minutes
                interval_minutes = 15
                time_fmt = "%H:%M"
                date_fmt = None
            elif total_minutes <= 480:  # 2-8 hours: every 1 hour
                interval_minutes = 60
                time_fmt = "%H:%M"
                date_fmt = None
            elif total_minutes <= 1440:  # <= 1 day: every 3 hours
                interval_minutes = 180
                time_fmt = "%H:%M"
                date_fmt = "%b %d"
            elif total_minutes <= 7200:  # <= 5 days: daily
                interval_minutes = 1440
                time_fmt = None
                date_fmt = "%b %d"
            else:  # > 5 days: every few days, show month changes
                interval_minutes = 1440 * max(1, (total_minutes // 1440) // 10)
                time_fmt = None
                date_fmt = "%b %d"
            
            # Generate tick positions - only keep underlined month boundaries
            current_dt = start_dt
            bar_idx = 0
            prev_month = None
            
            while bar_idx <= num_bars:
                bar_position = bar_idx + 1
                
                # Format label
                label = ""
                if date_fmt:
                    date_str = current_dt.strftime(date_fmt)
                    current_month = current_dt.month
                    
                    # Only keep month boundaries with underline
                    if prev_month is not None and prev_month != current_month:
                        label = date_str + "\n" + "━" * len(date_fmt)
                        x_ticks.append(bar_position)
                        x_labels.append(label)
                    prev_month = current_month
                
                # Move to next interval
                current_dt += timedelta(minutes=interval_minutes)
                bar_idx += interval_minutes // minutes_per_bar
            
            # Always add the end date if it's a month boundary
            if not x_ticks or x_ticks[-1] != num_bars + 1:
                end_dt = stop_dt
                if prev_month is not None and prev_month != end_dt.month:
                    date_str = end_dt.strftime(date_fmt) if date_fmt else ""
                    label = date_str + "\n" + "━" * len(date_fmt) if date_fmt else ""
                    if label:
                        x_ticks.append(num_bars + 1)
                        x_labels.append(label)

            x_label_text = "Date / Time"
        
        except Exception as e:
            # Fallback to simple scaling if date parsing fails
            interval = max(1, num_bars // 10)
            x_ticks = list(range(0, num_bars + 1, interval))
            x_labels = [f"Bar {i}" for i in x_ticks]
    else:
        # Fallback: generic scaling
        interval = max(1, num_bars // 10)
        x_ticks = list(range(0, num_bars + 1, interval))
        x_labels = [f"Bar {i}" for i in x_ticks]
    
    # Plot curves with transparency (SMA20 strategy plotted last for foreground)
    sp500_name = next((name for name in curves if _is_sp500_benchmark(name)), None)
    sma20_name = "SMA20Penguin"
    line_colors = {}
    pair_colors = {}
    color_cycle = plt.rcParams.get("axes.prop_cycle", None)
    color_list = color_cycle.by_key().get("color", []) if color_cycle is not None else []
    color_index = 0

    def _color_for_group(group_key: str) -> str:
        nonlocal color_index
        if group_key not in pair_colors:
            if color_list:
                pair_colors[group_key] = color_list[color_index % len(color_list)]
                color_index += 1
            else:
                pair_colors[group_key] = "C0"
        return pair_colors[group_key]

    # Draw SP500 first so it stays in the background.
    if sp500_name in curves:
        vals = curves[sp500_name]
        display_name = _display_strategy_name(sp500_name)
        line = plt.plot(
            range(1, len(vals) + 1),
            vals,
            label=display_name,
            linewidth=2,
            color="black",
            alpha=1.0,
            zorder=1,
        )
        line_colors[sp500_name] = line[0].get_color()

    for name in sorted(curves.keys(), key=_strategy_group_key):
        vals = curves[name]
        if name not in (sma20_name, sp500_name):
            display_name = _display_strategy_name(name)
            group_key = _strategy_base_key(name)
            color = "darkgrey" if _is_sp500_benchmark(name) else _color_for_group(group_key)
            line = plt.plot(
                range(1, len(vals) + 1),
                vals,
                label=display_name,
                linewidth=2,
                alpha=0.9 if name.endswith("_Manual") else 0.8,
                zorder=2,
                color=color,
                linestyle=_strategy_line_style(name),
            )
            line_colors[name] = line[0].get_color()
    
    # Plot SMA20 strategy last so it appears in foreground
    if sma20_name in curves:
        vals = curves[sma20_name]
        display_name = _display_strategy_name(sma20_name)
        line = plt.plot(range(1, len(vals) + 1), vals, label=display_name, linewidth=2, alpha=0.7, zorder=3)
        line_colors[sma20_name] = line[0].get_color()
    
    # Add text labels at the end of each curve on the right side
    for name in sorted(curves.keys(), key=_strategy_group_key):
        vals = curves[name]
        if vals:
            final_x = len(vals)
            final_y = vals[-1]
            color = line_colors.get(name, "black")
            display_name = _display_strategy_name(name)
            plt.text(final_x + 50, final_y, f" {display_name}", fontsize=8, va="center", 
                    bbox=dict(boxstyle="round,pad=0.3", facecolor=color, alpha=0.3, edgecolor="none"))

    plt.axhline(
        y=INITIAL_CAPITAL,
        color="gray",
        linestyle="--",
        alpha=0.7,
        label="Initial Capital",
    )
    
    plt.xticks(x_ticks, x_labels, rotation=45, ha='right', fontsize=9)
    plt.xlabel(x_label_text)
    plt.ylabel("Total Capital ($)")
    title = "Penguin Capital Curves"
    if symbol_list_name:
        title = f"{title} ({symbol_list_name})"
    plt.title(title)
    plt.legend(loc='best', fontsize=9)
    plt.grid(True, alpha=0.3)
    # Extend x-axis to accommodate right-side labels
    plt.xlim(left=0, right=len(next(iter(curves.values()), [])) * 1.15)
    plt.tight_layout()
    plt.savefig(filename, dpi=120, bbox_inches="tight")
    print(f"📈 Saved capital curves plot to {filename}")
    plt.close()


def create_final_report_pdf(curves, portfolios, filename, latest_prices=None, num_bars=None, binning="1m", start_date_str=None, stop_date_str=None, bar_timestamps=None, artifacts_dir=None, symbol_list_name=None):
    """
    Create comprehensive PDF report with capital curves and per-symbol trade summaries.
    
    Args:
        curves: Dict[penguin_name] = [list of capital values]
        portfolios: Dict[penguin_name] = Portfolio object
        filename: Output PDF filename
        latest_prices: Dict of current market prices
        num_bars: Number of bars (for x-axis scaling)
        binning: Timeframe string ("1m", "5m", "15m", "1h", "1d")
        start_date_str: Start date string for x-axis
        stop_date_str: Stop date string for x-axis
        artifacts_dir: Directory to save summary data files (optional)
    """
    if latest_prices is None:
        latest_prices = {}

    # Determine final liquidation timestamp (last bar) to exclude forced closes
    final_liquidation_timestamp = None
    if bar_timestamps and len(bar_timestamps) > 0:
        final_liquidation_timestamp = bar_timestamps[-1]
    
    # Calculate x-axis scaling if num_bars not provided
    if num_bars is None:
        num_bars = len(list(curves.values())[0]) if curves else 0
    
    binning_map = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "1d": 1440}
    minutes_per_bar = binning_map.get(binning, 1)
    total_minutes = num_bars * minutes_per_bar
    
    # Generate x-axis labels using actual dates/times
    x_ticks = []
    x_labels = []
    x_label_text = "Time"
    
    if bar_timestamps:
        x_ticks, x_labels = _build_ticks_from_timestamps(bar_timestamps, num_bars)
        x_label_text = "Date / Time"
    elif start_date_str and stop_date_str:
        try:
            start_dt = _parse_datetime_string(start_date_str)
            stop_dt = _parse_datetime_string(stop_date_str)
            
            # Generate ticks based on duration
            if total_minutes <= 120:  # <= 2 hours: every 15 minutes
                interval_minutes = 15
                time_fmt = "%H:%M"
                date_fmt = None
            elif total_minutes <= 480:  # 2-8 hours: every 1 hour
                interval_minutes = 60
                time_fmt = "%H:%M"
                date_fmt = None
            elif total_minutes <= 1440:  # <= 1 day: every 3 hours
                interval_minutes = 180
                time_fmt = "%H:%M"
                date_fmt = "%b %d"
            elif total_minutes <= 7200:  # <= 5 days: daily
                interval_minutes = 1440
                time_fmt = None
                date_fmt = "%b %d"
            else:  # > 5 days: every few days, show month changes
                interval_minutes = 1440 * max(1, (total_minutes // 1440) // 10)
                time_fmt = None
                date_fmt = "%b %d"
            
            # Generate tick positions - only keep underlined month boundaries
            current_dt = start_dt
            bar_idx = 0
            prev_month = None
            
            while bar_idx <= num_bars:
                bar_position = bar_idx + 1
                
                # Format label
                label = ""
                if date_fmt:
                    date_str = current_dt.strftime(date_fmt)
                    current_month = current_dt.month
                    
                    # Only keep month boundaries with underline
                    if prev_month is not None and prev_month != current_month:
                        label = date_str + "\n" + "━" * len(date_fmt)
                        x_ticks.append(bar_position)
                        x_labels.append(label)
                    prev_month = current_month
                
                # Move to next interval
                current_dt += timedelta(minutes=interval_minutes)
                bar_idx += interval_minutes // minutes_per_bar
            
            # Always add the end date if it's a month boundary
            if not x_ticks or x_ticks[-1] != num_bars + 1:
                end_dt = stop_dt
                if prev_month is not None and prev_month != end_dt.month:
                    date_str = end_dt.strftime(date_fmt) if date_fmt else ""
                    label = date_str + "\n" + "━" * len(date_fmt) if date_fmt else ""
                    if label:
                        x_ticks.append(num_bars + 1)
                        x_labels.append(label)
                
            x_label_text = "Date / Time"
        
        except Exception as e:
            # Fallback to simple scaling if date parsing fails
            interval = max(1, num_bars // 10)
            x_ticks = list(range(0, num_bars + 1, interval))
            x_labels = [f"Bar {i}" for i in x_ticks]
    else:
        # Fallback: generic scaling
        interval = max(1, num_bars // 10)
        x_ticks = list(range(0, num_bars + 1, interval))
        x_labels = [f"Bar {i}" for i in x_ticks]
    
    timespan_text = _build_timespan_text(start_date_str, stop_date_str, bar_timestamps, num_bars)

    with PdfPages(filename) as pdf:
        # Page 1: Capital Curves
        fig, ax = plt.subplots(figsize=(12, 8))

        sp500_name = next((name for name in curves if _is_sp500_benchmark(name)), None)
        sma20_name = "SMA20Penguin"
        line_colors = {}

        # Draw SP500 first so it stays in the background.
        if sp500_name in curves:
            vals = curves[sp500_name]
            display_name = _display_strategy_name(sp500_name)
            line = ax.plot(
                range(1, len(vals) + 1),
                vals,
                label=display_name,
                linewidth=2,
                color="black",
                alpha=1.0,
                zorder=1,
            )
            line_colors[sp500_name] = line[0].get_color()

        for name, vals in curves.items():
            if name not in (sma20_name, sp500_name):
                display_name = _display_strategy_name(name)
                line = ax.plot(range(1, len(vals) + 1), vals, label=display_name, linewidth=2, alpha=0.7, zorder=2)
                line_colors[name] = line[0].get_color()
        
        # Plot SMA20 strategy last so it appears in foreground
        if sma20_name in curves:
            vals = curves[sma20_name]
            display_name = _display_strategy_name(sma20_name)
            line = ax.plot(range(1, len(vals) + 1), vals, label=display_name, linewidth=2, alpha=0.7, zorder=3)
            line_colors[sma20_name] = line[0].get_color()
        
        # Add text labels at the end of each curve on the right side
        for name in sorted(curves.keys(), key=_strategy_group_key):
            vals = curves[name]
            if vals:
                final_x = len(vals)
                final_y = vals[-1]
                color = line_colors.get(name, "black")
                display_name = _display_strategy_name(name)
                ax.text(final_x + 50, final_y, f" {display_name}", fontsize=8, va="center", 
                       bbox=dict(boxstyle="round,pad=0.3", facecolor=color, alpha=0.3, edgecolor="none"))

        ax.axhline(
            y=INITIAL_CAPITAL,
            color="gray",
            linestyle="--",
            alpha=0.7,
            label="Initial Capital",
        )
        ax.set_xticks(x_ticks)
        ax.set_xticklabels(x_labels, rotation=45, ha='right', fontsize=9)
        ax.set_xlabel(x_label_text)
        ax.set_ylabel("Total Capital ($)")
        page1_title = "Penguin Capital Curves"
        if symbol_list_name:
            page1_title = f"{page1_title} ({symbol_list_name})"
        if timespan_text:
            page1_title = f"{page1_title} ({timespan_text})"
        ax.set_title(page1_title)
        ax.legend(fontsize=9, loc='best')
        ax.grid(True, alpha=0.3)
        # Extend x-axis to accommodate right-side labels
        if curves:
            max_len = max(len(vals) for vals in curves.values())
            ax.set_xlim(left=0, right=max_len * 1.15)

        plt.tight_layout()
        pdf.savefig(fig, bbox_inches="tight")
        plt.close()

        # Pages 2+: One page per strategy or paired trainable/manual group.
        for page_names in _build_report_page_groups(list(portfolios.keys())):
            page_items = []
            for penguin_name in page_names:
                if penguin_name not in curves or penguin_name not in portfolios:
                    continue

                portfolio = portfolios[penguin_name]
                display_penguin_name = _display_strategy_name(penguin_name)
                parameter_text = _strategy_parameter_text(penguin_name)
                summary = portfolio.get_symbol_summary(latest_prices)

                cash = portfolio.cash
                market_value = 0.0
                for symbol, pos_qty in portfolio.positions.items():
                    if symbol in latest_prices and pos_qty > 0:
                        market_value += pos_qty * latest_prices[symbol]
                total_value = cash + market_value

                totals = _aggregate_strategy_summary(summary)

                preliq_sell_count = 0
                preliq_qty_sold = 0
                for t in portfolio.trades:
                    if t.action == "SELL":
                        if final_liquidation_timestamp and t.timestamp == final_liquidation_timestamp:
                            continue
                        preliq_sell_count += 1
                        preliq_qty_sold += t.quantity

                totals["sell_count"] = preliq_sell_count
                totals["total_qty_sold"] = preliq_qty_sold

                page_items.append(
                    {
                        "name": penguin_name,
                        "display_name": display_penguin_name,
                        "parameter_text": parameter_text,
                        "summary": summary,
                        "cash": cash,
                        "market_value": market_value,
                        "total_value": total_value,
                        "total_pnl": totals["total_pnl"],
                        "buy_count": totals["buy_count"],
                        "sell_count": totals["sell_count"],
                    }
                )

                if artifacts_dir:
                    _save_strategy_summary_to_artifacts(
                        penguin_name,
                        display_penguin_name,
                        summary,
                        cash,
                        market_value,
                        total_value,
                        totals["buy_count"],
                        totals["sell_count"],
                        totals["total_pnl"],
                        artifacts_dir,
                    )

            if not page_items:
                continue

            def _build_summary_lines(item: dict[str, object]) -> list[str]:
                lines = [
                    f"{item['display_name']}",
                    f"Cash: ${item['cash']:,.2f}  |  Total Value: ${item['total_value']:,.2f}",
                    f"Buys: {item['buy_count']}  |  Sells: {item['sell_count']}",
                    f"Total PnL: ${item['total_pnl']:,.2f}",
                ]
                if item["parameter_text"]:
                    lines.append(item["parameter_text"])
                return lines

            summary_text_blocks = [_build_summary_lines(item) for item in page_items]
            summary_height_units = max(1.8, 0.28 * max(len(lines) for lines in summary_text_blocks))
            fig = plt.figure(figsize=(12, 8))
            grid = fig.add_gridspec(2, 1, height_ratios=[summary_height_units, 6.0], hspace=0.18)
            summary_grid = grid[0].subgridspec(1, len(page_items), wspace=0.25)
            summary_axes = [fig.add_subplot(summary_grid[0, idx]) for idx in range(len(page_items))]
            ax = fig.add_subplot(grid[1])

            for summary_ax, item, lines in zip(summary_axes, page_items, summary_text_blocks):
                summary_ax.axis("off")
                summary_ax.text(
                    0.5,
                    0.5,
                    "\n".join(lines),
                    ha="center",
                    va="center",
                    fontsize=9,
                    wrap=True,
                    family="monospace",
                    bbox=dict(boxstyle="round,pad=0.5", facecolor="lightyellow", alpha=0.3, edgecolor="gray"),
                )

            page_title_names = ", ".join(item["display_name"] for item in page_items)

            for item in page_items:
                penguin_name = item["name"]
                vals = curves[penguin_name]
                color = line_colors.get(penguin_name, None)
                line = ax.plot(
                    range(1, len(vals) + 1),
                    vals,
                    label=item["display_name"],
                    linewidth=2,
                    alpha=0.8,
                    color=color,
                    linestyle=_strategy_line_style(penguin_name),
                )

                if vals:
                    final_x = len(vals)
                    final_y = vals[-1]
                    actual_color = line[0].get_color()
                    ax.text(
                        final_x + 50,
                        final_y,
                        f" {item['display_name']}",
                        fontsize=9,
                        va="center",
                        bbox=dict(boxstyle="round,pad=0.3", facecolor=actual_color, alpha=0.3, edgecolor="none"),
                    )

            ax.axhline(
                y=INITIAL_CAPITAL,
                color="gray",
                linestyle="--",
                alpha=0.7,
                label="Initial Capital",
            )
            ax.set_xticks(x_ticks)
            ax.set_xticklabels(x_labels, rotation=45, ha='right', fontsize=9)
            ax.set_xlabel(x_label_text)
            ax.set_ylabel("Total Capital ($)")
            individual_title = f"Capital Curve: {page_title_names}"
            if symbol_list_name:
                individual_title = f"{individual_title} ({symbol_list_name})"
            ax.set_title(individual_title)
            ax.legend(fontsize=10, loc='best')
            ax.grid(True, alpha=0.3)

            max_len = max(len(curves[item["name"]]) for item in page_items)
            ax.set_xlim(left=0, right=max_len * 1.15)

            pdf.savefig(fig, bbox_inches="tight")
            plt.close()

    print(f"📄 Final report saved to {filename}")
