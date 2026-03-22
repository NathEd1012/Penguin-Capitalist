"""Enhanced plotting and PDF report generation using matplotlib and PdfPages."""
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from datetime import datetime, timedelta
from pathlib import Path
import pytz
from config import INITIAL_CAPITAL


def _display_strategy_name(name: str) -> str:
    """Normalize strategy names for plot/report labels."""
    if name == "SMA20MultiTimeframePenguin":
        return "SMA20Penguin"
    return name


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
    """Build x-axis ticks/labels from actual bar timestamps (weekends naturally excluded). Only show underlined month boundaries."""
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

    x_ticks = []
    x_labels = []
    prev_month = None
    for idx in tick_indices:
        dt = bar_timestamps[idx]
        # Only keep labels with underline (month boundaries)
        if "%b %d" in label_fmt:
            if prev_month is not None and prev_month != dt.month:
                label = dt.strftime(label_fmt) + "\n" + "━" * 6
                x_ticks.append(idx + 1)
                x_labels.append(label)
            prev_month = dt.month

    return x_ticks, x_labels


def _build_timespan_text(start_date_str=None, stop_date_str=None, bar_timestamps=None, num_bars=None):
    """Build a human-readable timespan string for chart/report titles."""
    def _fmt_dt(dt: datetime) -> str:
        return dt.strftime("%Y-%m-%d %H:%M")

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


def plot_capital_curves(curves, filename, num_bars=None, binning="1m", start_date_str=None, stop_date_str=None, bar_timestamps=None):
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
    sp500_name = "SP500Penguin"
    sma20_name = "SMA20MultiTimeframePenguin" if "SMA20MultiTimeframePenguin" in curves else "SMA20Penguin"
    line_colors = {}

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

    for name, vals in curves.items():
        if name not in (sma20_name, sp500_name):
            display_name = _display_strategy_name(name)
            line = plt.plot(range(1, len(vals) + 1), vals, label=display_name, linewidth=2, alpha=0.7, zorder=2)
            line_colors[name] = line[0].get_color()
    
    # Plot SMA20 strategy last so it appears in foreground
    if sma20_name in curves:
        vals = curves[sma20_name]
        display_name = _display_strategy_name(sma20_name)
        line = plt.plot(range(1, len(vals) + 1), vals, label=display_name, linewidth=2, alpha=0.7, zorder=3)
        line_colors[sma20_name] = line[0].get_color()
    
    # Add text labels at the end of each curve on the right side
    for name, vals in curves.items():
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
    plt.title("Penguin Capital Curves")
    plt.legend(loc='best', fontsize=9)
    plt.grid(True, alpha=0.3)
    # Extend x-axis to accommodate right-side labels
    plt.xlim(left=0, right=len(next(iter(curves.values()), [])) * 1.15)
    plt.tight_layout()
    plt.savefig(filename, dpi=120, bbox_inches="tight")
    print(f"📈 Saved capital curves plot to {filename}")
    plt.close()


def plot_multitimeframe_sr_history(sr_history_by_symbol, output_dir, bar_timestamps=None):
    """
    Plot per-symbol price and multi-timeframe S/R lines for the full run.

    Args:
        sr_history_by_symbol: Dict[symbol] = [snapshot dict per bar]
        output_dir: Directory for generated PNG files
        bar_timestamps: Optional list of datetime timestamps for x-axis labels
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tf_colors = {
        "1y": "#1f77b4",
        "3m": "#ff7f0e",
        "1m": "#2ca02c",
        "1w": "#d62728",
        "1d": "#9467bd",
    }

    created_files = []

    for symbol, snapshots in sorted(sr_history_by_symbol.items()):
        if not snapshots:
            continue

        n = len(snapshots)
        x = list(range(1, n + 1))
        prices = [row.get("price") for row in snapshots]

        plt.figure(figsize=(15, 8))
        plt.plot(x, prices, color="black", linewidth=1.8, alpha=0.9, label="Price")

        for tf_name in ["1y", "3m", "1m", "1w", "1d"]:
            color = tf_colors[tf_name]

            # Range-extremes style keys.
            support_key = f"{tf_name}_support"
            resistance_key = f"{tf_name}_resistance"
            if support_key in snapshots[0] or resistance_key in snapshots[0]:
                support_series = [row.get(support_key) for row in snapshots]
                resistance_series = [row.get(resistance_key) for row in snapshots]

                plt.plot(
                    x,
                    support_series,
                    linestyle="--",
                    linewidth=1.4,
                    color=color,
                    alpha=0.8,
                    label=f"{tf_name} support",
                )
                plt.plot(
                    x,
                    resistance_series,
                    linestyle="-",
                    linewidth=1.4,
                    color=color,
                    alpha=0.8,
                    label=f"{tf_name} resistance",
                )

            # Reaction-line style keys (up to 5 lines per timeframe).
            for i in range(1, 6):
                line_key = f"{tf_name}_line_{i}"
                if line_key not in snapshots[0]:
                    continue

                line_series = [row.get(line_key) for row in snapshots]
                plt.plot(
                    x,
                    line_series,
                    linestyle=":",
                    linewidth=max(0.8, 1.6 - 0.2 * (i - 1)),
                    color=color,
                    alpha=max(0.35, 0.8 - 0.12 * (i - 1)),
                    label=f"{tf_name} line {i}",
                )

        x_ticks, x_labels = _build_ticks_from_timestamps(bar_timestamps, n)
        if x_ticks and x_labels:
            plt.xticks(x_ticks, x_labels, rotation=45, ha="right", fontsize=9)
            plt.xlabel("Date / Time")
        else:
            plt.xlabel("Bar")

        plt.ylabel("Price ($)")
        plt.title(f"{symbol} - Multitimeframe S/R Lines")
        plt.grid(True, alpha=0.25)
        plt.legend(loc="best", fontsize=8, ncol=2)
        plt.tight_layout()

        out_file = output_dir / f"{symbol}_multitimeframe_sr.png"
        plt.savefig(out_file, dpi=120)
        plt.close()
        created_files.append(str(out_file))

    return created_files


def create_png_gallery_pdf(png_files, output_pdf, page_title_prefix="Multitimeframe S/R"):
    """Combine many PNG files into a single multi-page PDF."""
    if not png_files:
        return None

    output_pdf = Path(output_pdf)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    # Keep ordering stable and predictable.
    sorted_pngs = sorted([Path(p) for p in png_files], key=lambda p: p.name.lower())

    with PdfPages(output_pdf) as pdf:
        for png_path in sorted_pngs:
            if not png_path.exists():
                continue

            img = plt.imread(png_path)

            fig, ax = plt.subplots(figsize=(14, 8))
            ax.imshow(img)
            ax.axis("off")
            ax.set_title(f"{page_title_prefix}: {png_path.stem}", fontsize=12)
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)

    return str(output_pdf)


def create_final_report_pdf(curves, portfolios, filename, latest_prices=None, num_bars=None, binning="1m", start_date_str=None, stop_date_str=None, bar_timestamps=None):
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
    """
    if latest_prices is None:
        latest_prices = {}
    
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

        sp500_name = "SP500Penguin"
        sma20_name = "SMA20MultiTimeframePenguin" if "SMA20MultiTimeframePenguin" in curves else "SMA20Penguin"
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
        for name, vals in curves.items():
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

        # Pages 2+: Trade Summary Table for each Penguin
        for penguin_name in sorted(portfolios.keys()):
            portfolio = portfolios[penguin_name]
            display_penguin_name = _display_strategy_name(penguin_name)
            
            fig = plt.figure(figsize=(12, 10))
            ax = fig.add_subplot(111)
            ax.axis("tight")
            ax.axis("off")

            summary = portfolio.get_symbol_summary(latest_prices)

            cash = portfolio.cash
            market_value = 0.0
            for symbol, pos_qty in portfolio.positions.items():
                if symbol in latest_prices and pos_qty > 0:
                    market_value += pos_qty * latest_prices[symbol]
            total_value = cash + market_value

            # Build table data
            table_data = [
                [
                    "Symbol",
                    "Buy/Sell Cnt",
                    "Shares",
                    "Total Cost",
                    "Total Revenue",
                    "Total PnL",
                    "PnL %",
                ]
            ]

            total_pnl = 0
            total_buy_count = 0
            total_sell_count = 0
            total_shares_bought = 0
            for symbol in sorted(summary.keys()):
                s = summary[symbol]
                pnl = s["total_pnl"]
                pnl_pct = s["pnl_pct"]
                buy_cnt = s["buy_count"]
                sell_cnt = s["sell_count"]
                shares_bought = s["total_qty_bought"]
                total_pnl += pnl
                total_buy_count += buy_cnt
                total_sell_count += sell_cnt
                total_shares_bought += shares_bought

                table_data.append(
                    [
                        symbol,
                        f"{buy_cnt}/{sell_cnt}",
                        str(shares_bought),
                        f"${s['total_cost']:,.2f}",
                        f"${s['total_revenue']:,.2f}",
                        f"${pnl:,.2f}",
                        f"{pnl_pct:+.2f}%",
                    ]
                )

            # Add total row
            table_data.append(
                [
                    "TOTAL",
                    "",
                    str(total_shares_bought),
                    "",
                    "",
                    f"${total_pnl:,.2f}",
                    "",
                ]
            )

            table = ax.table(
                cellText=table_data,
                cellLoc="center",
                loc="center",
                colWidths=[0.14, 0.14, 0.09, 0.18, 0.18, 0.15, 0.12],
            )
            table.auto_set_font_size(False)
            table.set_fontsize(9)
            table.scale(1, 2)

            # Style header row
            for i in range(len(table_data[0])):
                table[(0, i)].set_facecolor("#4472C4")
                table[(0, i)].set_text_props(weight="bold", color="white")

            # Style total row
            for i in range(len(table_data[0])):
                table[(len(table_data) - 1, i)].set_facecolor("#E7E6E6")
                table[(len(table_data) - 1, i)].set_text_props(weight="bold")

            title = f"Trade Summary: {display_penguin_name}"
            fig.suptitle(title, fontsize=14, weight="bold", y=0.98)

            # Portfolio totals at the top in fixed columns to avoid text overlap.
            summary_items = [
                f"Cash: ${cash:,.2f}",
                f"Market Value: ${market_value:,.2f}",
                f"Total Value: ${total_value:,.2f}",
                f"Buys: {total_buy_count}",
                f"Sells: {total_sell_count}",
            ]
            summary_x_positions = [0.08, 0.30, 0.52, 0.78, 0.92]
            for x_pos, item in zip(summary_x_positions, summary_items):
                fig.text(x_pos, 0.935, item, ha="center", va="center", fontsize=10, weight="semibold")

            plt.tight_layout(rect=[0, 0, 1, 0.88])
            pdf.savefig(fig, bbox_inches="tight")
            plt.close()

            # Add individual plot for this penguin on the next page
            if penguin_name in curves:
                fig, ax = plt.subplots(figsize=(12, 8))
                
                vals = curves[penguin_name]
                # Use the same color from the first plot
                color = line_colors.get(penguin_name, None)
                line = ax.plot(range(1, len(vals) + 1), vals, label=display_penguin_name, linewidth=2, alpha=0.8, color=color)
                
                # Add text label at the end of the curve
                if vals:
                    final_x = len(vals)
                    final_y = vals[-1]
                    actual_color = line[0].get_color()
                    ax.text(final_x + 50, final_y, f" {display_penguin_name}", fontsize=9, va="center", 
                           bbox=dict(boxstyle="round,pad=0.3", facecolor=actual_color, alpha=0.3, edgecolor="none"))
                
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
                ax.set_title(f"Capital Curve: {display_penguin_name}")
                ax.legend(fontsize=10, loc='best')
                ax.grid(True, alpha=0.3)
                
                # Extend x-axis to accommodate right-side label
                if vals:
                    ax.set_xlim(left=0, right=len(vals) * 1.15)
                
                plt.tight_layout()
                pdf.savefig(fig, bbox_inches="tight")
                plt.close()

    print(f"📄 Final report saved to {filename}")
