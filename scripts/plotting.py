"""Enhanced plotting and PDF report generation using matplotlib and PdfPages."""
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from datetime import datetime, timedelta
import pytz
from config import INITIAL_CAPITAL


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
    """Build x-axis ticks/labels from actual bar timestamps (weekends naturally excluded)."""
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
        label = dt.strftime(label_fmt)
        if "%b %d" in label_fmt:
            if prev_month is not None and prev_month != dt.month:
                label = label + "\n" + "━" * 6
            prev_month = dt.month
        x_ticks.append(idx + 1)
        x_labels.append(label)

    return x_ticks, x_labels


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
    plt.figure(figsize=(14, 6))
    
    # Determine x-axis based on actual dates and number of bars
    if num_bars is None:
        num_bars = len(list(curves.values())[0]) if curves else 0
    
    binning_map = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "1d": 1440}
    minutes_per_bar = binning_map.get(binning, 1)
    total_minutes = num_bars * minutes_per_bar
    
    # Parse actual start/stop dates if provided
    x_ticks = []
    x_labels = []
    
    if bar_timestamps:
        x_ticks, x_labels = _build_ticks_from_timestamps(bar_timestamps, num_bars)
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
            
            # Generate tick positions
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
                    
                    # Highlight month changes
                    if prev_month is not None and prev_month != current_month:
                        label = date_str + "\n" + "━" * len(date_fmt)
                    else:
                        label = date_str
                    prev_month = current_month
                
                if time_fmt:
                    time_str = current_dt.strftime(time_fmt)
                    label = time_str if not label else label + "\n" + time_str
                
                x_ticks.append(bar_position)
                x_labels.append(label)
                
                # Move to next interval
                current_dt += timedelta(minutes=interval_minutes)
                bar_idx += interval_minutes // minutes_per_bar
            
            # Always add the end date
            if not x_ticks or x_ticks[-1] != num_bars + 1:
                end_dt = stop_dt
                date_str = end_dt.strftime(date_fmt) if date_fmt else ""
                time_str = end_dt.strftime(time_fmt) if time_fmt else ""
                label = date_str
                if time_str:
                    label = (date_str + "\n" + time_str) if date_str else time_str
                x_ticks.append(num_bars + 1)
                x_labels.append(label)
        
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
    
    # Plot curves with transparency (SMA20 last for foreground)
    line_colors = {}
    for name, vals in curves.items():
        if name != "SMA20MultiTimeframePenguin":
            line = plt.plot(range(1, len(vals) + 1), vals, label=name, linewidth=2.5, alpha=0.7)
            line_colors[name] = line[0].get_color()
    
    # Plot SMA20 last so it appears in foreground
    if "SMA20MultiTimeframePenguin" in curves:
        vals = curves["SMA20MultiTimeframePenguin"]
        line = plt.plot(range(1, len(vals) + 1), vals, label="SMA20MultiTimeframePenguin", linewidth=2.5, alpha=0.7)
        line_colors["SMA20MultiTimeframePenguin"] = line[0].get_color()
    
    # Add text labels at the end of each curve on the right side
    for name, vals in curves.items():
        if vals:
            final_x = len(vals)
            final_y = vals[-1]
            color = line_colors.get(name, "black")
            plt.text(final_x + 50, final_y, f" {name}", fontsize=8, va="center", 
                    bbox=dict(boxstyle="round,pad=0.3", facecolor=color, alpha=0.3, edgecolor="none"))

    plt.axhline(
        y=INITIAL_CAPITAL,
        color="gray",
        linestyle="--",
        alpha=0.7,
        label="Initial Capital",
    )
    
    plt.xticks(x_ticks, x_labels, rotation=45, ha='right', fontsize=9)
    plt.xlabel("Date / Time")
    plt.ylabel("Total Capital ($)")
    plt.title("Penguin Capital Curves")
    plt.legend(loc='best', fontsize=9)
    plt.grid(True, alpha=0.3)
    # Extend x-axis to accommodate right-side labels
    plt.xlim(left=0, right=len(next(iter(curves.values()), [])) * 1.15)
    plt.tight_layout()
    plt.savefig(filename, dpi=100)
    print(f"📈 Saved capital curves plot to {filename}")
    plt.close()


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
            
            # Generate tick positions
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
                    
                    # Highlight month changes
                    if prev_month is not None and prev_month != current_month:
                        label = date_str + "\n" + "━" * len(date_fmt)
                    else:
                        label = date_str
                    prev_month = current_month
                
                if time_fmt:
                    time_str = current_dt.strftime(time_fmt)
                    label = time_str if not label else label + "\n" + time_str
                
                x_ticks.append(bar_position)
                x_labels.append(label)
                
                # Move to next interval
                current_dt += timedelta(minutes=interval_minutes)
                bar_idx += interval_minutes // minutes_per_bar
            
            # Always add the end date
            if not x_ticks or x_ticks[-1] != num_bars + 1:
                end_dt = stop_dt
                date_str = end_dt.strftime(date_fmt) if date_fmt else ""
                time_str = end_dt.strftime(time_fmt) if time_fmt else ""
                label = date_str
                if time_str:
                    label = (date_str + "\n" + time_str) if date_str else time_str
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
    
    with PdfPages(filename) as pdf:
        # Page 1: Capital Curves
        fig, ax = plt.subplots(figsize=(12, 8))

        line_colors = {}
        for name, vals in curves.items():
            if name != "SMA20MultiTimeframePenguin":
                line = ax.plot(range(1, len(vals) + 1), vals, label=name, linewidth=2, alpha=0.7)
                line_colors[name] = line[0].get_color()
        
        # Plot SMA20 last so it appears in foreground
        if "SMA20MultiTimeframePenguin" in curves:
            vals = curves["SMA20MultiTimeframePenguin"]
            line = ax.plot(range(1, len(vals) + 1), vals, label="SMA20MultiTimeframePenguin", linewidth=2, alpha=0.7)
            line_colors["SMA20MultiTimeframePenguin"] = line[0].get_color()
        
        # Add text labels at the end of each curve on the right side
        for name, vals in curves.items():
            if vals:
                final_x = len(vals)
                final_y = vals[-1]
                color = line_colors.get(name, "black")
                ax.text(final_x + 50, final_y, f" {name}", fontsize=8, va="center", 
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
        ax.set_title("Penguin Capital Curves")
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
                    "Buy Cnt",
                    "Sell Cnt",
                    "Pos Qty",
                    "Market Value",
                    "Total Cost",
                    "Total Revenue",
                    "Total PnL",
                    "PnL %",
                ]
            ]

            total_pnl = 0
            for symbol in sorted(summary.keys()):
                s = summary[symbol]
                pnl = s["total_pnl"]
                pnl_pct = s["pnl_pct"]
                total_pnl += pnl

                table_data.append(
                    [
                        symbol,
                        str(s["buy_count"]),
                        str(s["sell_count"]),
                        str(s["position_qty"]),
                        f"${s['market_value']:,.2f}",
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
                    "",
                    "",
                    f"${market_value:,.2f}",
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
                colWidths=[0.09, 0.08, 0.08, 0.08, 0.13, 0.13, 0.13, 0.12, 0.09],
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

            title = f"Trade Summary: {penguin_name}"
            fig.suptitle(title, fontsize=14, weight="bold", y=0.98)

            # Portfolio totals at the top
            summary_text = (
                f"Cash: ${cash:,.2f}    "
                f"Market Value: ${market_value:,.2f}    "
                f"Total Value: ${total_value:,.2f}"
            )
            fig.text(0.5, 0.93, summary_text, ha="center", fontsize=11)

            plt.tight_layout()
            pdf.savefig(fig, bbox_inches="tight")
            plt.close()

            # Add individual plot for this penguin on the next page
            if penguin_name in curves:
                fig, ax = plt.subplots(figsize=(12, 8))
                
                vals = curves[penguin_name]
                # Use the same color from the first plot
                color = line_colors.get(penguin_name, None)
                line = ax.plot(range(1, len(vals) + 1), vals, label=penguin_name, linewidth=2, alpha=0.8, color=color)
                
                # Add text label at the end of the curve
                if vals:
                    final_x = len(vals)
                    final_y = vals[-1]
                    actual_color = line[0].get_color()
                    ax.text(final_x + 50, final_y, f" {penguin_name}", fontsize=9, va="center", 
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
                ax.set_title(f"Capital Curve: {penguin_name}")
                ax.legend(fontsize=10, loc='best')
                ax.grid(True, alpha=0.3)
                
                # Extend x-axis to accommodate right-side label
                if vals:
                    ax.set_xlim(left=0, right=len(vals) * 1.15)
                
                plt.tight_layout()
                pdf.savefig(fig, bbox_inches="tight")
                plt.close()

    print(f"📄 Final report saved to {filename}")
