import time
import signal
import sys
import random
import os
import shutil
from collections import defaultdict
from datetime import datetime
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.table import Table
import json
import pytz

from config import (
    SYMBOLS,
    RUN_MINUTES,
    BAR_TIMEFRAME_MINUTES,
    INITIAL_CAPITAL,
    TRANSACTION_COST,
    ENABLE_TRANSACTION_COSTS,
    USE_SYNTHETIC_DATA,
    CAPITAL_CURVES_FILE,
    TRADES_LOG_FILE,
    CURVES_DATA_FILE,
    PLOTS_DIR,
    ACTIVE_PENGUINS,
)
from data_client import AlpacaClient
from data import get_minute_bars, get_timeframe_bars
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from backtest.portfolio import Portfolio
from data.scoreboard import (
    load_scoreboard,
    save_scoreboard,
    register_penguin,
    record_win,
    record_run,
    print_scoreboard,
)

from penguins import SupportResistancePenguin
from penguins.sma20_multitimeframe_penguin import SMA20MultiTimeframePenguin


def synthetic_price_bar(symbol, price_history):
    """Generate synthetic price when Alpaca has no data."""
    if symbol not in price_history or not price_history[symbol]:
        return 100.0 + hash(symbol) % 50
    last = price_history[symbol][-1]
    # Ensure last price is valid
    if last <= 0:
        return 100.0 + hash(symbol) % 50
    change_pct = random.gauss(0, 0.3)
    new_price = last * (1 + change_pct / 100)
    # Ensure minimum price of $0.01
    return max(0.01, new_price)


def plot_capital_curves(curves, filename):
    """Plot and save capital curves."""
    plt.figure(figsize=(12, 6))
    for name, vals in curves.items():
        plt.plot(range(1, len(vals) + 1), vals, label=name, linewidth=3)

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
            marker=None,
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
    print(f"📈 Updated capital curves to {filename}")


def create_final_report_pdf(curves, portfolios, filename, latest_prices=None):
    """Create PDF with capital curves and per-symbol trade summary."""
    with PdfPages(filename) as pdf:
        # Page 1: Capital Curves
        fig, ax = plt.subplots(figsize=(12, 8))

        for name, vals in curves.items():
            ax.plot(range(1, len(vals) + 1), vals, label=name, linewidth=2)

        # Calculate and plot overall average capital
        if curves:
            curve_values = list(curves.values())
            num_penguins = len(curve_values)
            overall_avg = [
                sum(vals[i] for vals in curve_values) / num_penguins
                for i in range(len(curve_values[0]))
            ]
            ax.plot(
                range(1, len(overall_avg) + 1),
                overall_avg,
                marker=None,
                label="Overall Average Capital",
                linewidth=2.5,
                color="black",
                linestyle="--",
            )

        ax.axhline(
            y=INITIAL_CAPITAL,
            color="gray",
            linestyle="--",
            alpha=0.5,
            label="Initial Capital",
        )
        ax.set_xlabel("Minute")
        ax.set_ylabel("Total Capital ($)")
        ax.set_title(f"Penguin Capital Curves")
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        pdf.savefig(fig, bbox_inches="tight")
        plt.close()

        # Page 2+: Trade Summary Table for each Penguin
        for penguin_name, portfolio in sorted(portfolios.items()):
            fig = plt.figure(figsize=(12, 10))
            ax = fig.add_subplot(111)
            ax.axis("tight")
            ax.axis("off")

            summary = portfolio.get_symbol_summary(latest_prices or {})

            cash = portfolio.cash
            market_value = 0.0
            if latest_prices:
                for symbol, pos in portfolio.positions.items():
                    if symbol in latest_prices:
                        market_value += pos.qty * latest_prices[symbol]
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

    print(f"📄 Final report saved to {filename}")


def check_consistency(portfolio, latest_prices, curve_values, max_jump_pct=0.15):
    """Validate positions vs trade history and detect suspicious curve jumps."""
    warnings = []

    # 1) Positions vs trade history
    expected_qty = {}
    for t in portfolio.trade_history:
        expected_qty[t.symbol] = expected_qty.get(t.symbol, 0) + (
            t.qty if t.side == "BUY" else -t.qty
        )

    for symbol, pos in portfolio.positions.items():
        expected = expected_qty.get(symbol, 0)
        if expected != pos.qty:
            warnings.append(
                f"Position mismatch for {symbol}: positions={pos.qty}, trades={expected}"
            )

    for symbol, qty in expected_qty.items():
        if qty != 0 and symbol not in portfolio.positions:
            warnings.append(
                f"Missing position for {symbol}: trades imply qty={qty}, positions=0"
            )

    # 2) Curve vs portfolio value
    if curve_values:
        computed_value = portfolio.value(latest_prices)
        curve_value = curve_values[-1]
        if abs(computed_value - curve_value) > 0.01:
            warnings.append(
                f"Curve mismatch: curve=${curve_value:,.2f}, portfolio=${computed_value:,.2f}"
            )

        # 3) Large jumps in curve
        for i in range(1, len(curve_values)):
            prev = curve_values[i - 1]
            curr = curve_values[i]
            if prev <= 0:
                continue
            pct = (curr - prev) / prev
            if abs(pct) >= max_jump_pct:
                warnings.append(
                    f"Large jump at minute {i + 1}: {pct:+.2%} (from ${prev:,.2f} to ${curr:,.2f})"
                )

    return warnings


def run():
    # Load scoreboard and register penguins
    scoreboard = load_scoreboard()

    print(f"🐧 Starting live simulation for {RUN_MINUTES} minutes")
    print(f"Symbols: {SYMBOLS}")
    print(f"Interval: {BAR_TIMEFRAME_MINUTES} minute(s) per bar\n")

    client = AlpacaClient(paper=True)

    penguins = [penguin_class() for penguin_class in ACTIVE_PENGUINS]

    for penguin in penguins:
        if isinstance(penguin, SMA20MultiTimeframePenguin):
            penguin.initialize_sma_levels(SYMBOLS, client)

    # Register all penguins in scoreboard
    for penguin in penguins:
        scoreboard = register_penguin(scoreboard, penguin.name)

    portfolios = {
        p.name: Portfolio(
            cash=INITIAL_CAPITAL,
            fee_per_trade=TRANSACTION_COST,
            enable_fees=ENABLE_TRANSACTION_COSTS,
        )
        for p in penguins
    }
    price_history = defaultdict(list)
    curves = {p.name: [] for p in penguins}
    trades_log = {p.name: [] for p in penguins}  # List of (minute, trade_str) tuples
    actual_trading_minutes = 0  # Track minutes when market was actually open

    sr_penguins = [p for p in penguins if isinstance(p, SupportResistancePenguin)]
    if sr_penguins:
        sr_penguin = sr_penguins[0]
        warmup_bars = max(
            60,
            sr_penguin.left + sr_penguin.right + sr_penguin.atr_n,
        )
        print("Evaluating historical data for S&R lines...")

        try:
            warmup_history = get_minute_bars(SYMBOLS, minutes=warmup_bars)
        except Exception as e:
            warmup_history = {}
            print(f"Warning: failed to load minute bars: {e}")

        for symbol in SYMBOLS:
            prices = warmup_history.get(symbol, [])
            if prices:
                price_history[symbol].extend(prices)

        scales = [
            ("Intraday", TimeFrame(5, TimeFrameUnit.Minute), 3),
            ("Short Swing", TimeFrame(15, TimeFrameUnit.Minute), 10),
            ("Swing", TimeFrame.Hour, 60),
            ("Macro", TimeFrame.Day, 180),
        ]

        def _zones_overlap_strict(cluster, zone):
            """Check if zone overlaps with any zone in cluster (no tolerance)."""
            for existing in cluster["zones"]:
                overlaps = not (
                    existing["high"] < zone["low"]
                    or zone["high"] < existing["low"]
                )
                if overlaps:
                    return True
            return False

        zones_log_path = os.path.join("run_current", "support_resistance_zones.txt")
        with open(zones_log_path, "w") as f:
            f.write("=" * 80 + "\n")
            f.write("SUPPORT & RESISTANCE ZONES LOG\n")
            f.write("=" * 80 + "\n\n")
            f.write("Parameters:\n")
            f.write(
                f"  - Pivot detection window: {sr_penguin.left} bars left, {sr_penguin.right} bars right\n"
            )
            f.write(f"  - ATR period: {sr_penguin.atr_n} bars\n")
            f.write(
                f"  - Minimum bars needed: {sr_penguin.left + sr_penguin.right + sr_penguin.atr_n} bars\n"
            )
            f.write(f"  - Zone width multiplier: {sr_penguin.zone_k}\n")
            f.write("  - Minimum touches: 2\n")
            f.write("  - Reaction requirement: move >= 1 ATR within 3 bars\n")
            f.write("  - Merge tolerance: 0.3% of current price\n")
            f.write("  - Scales: 5Min/3D, 15Min/10D, 60Min/60D, 1D/6M\n\n")

            for symbol in SYMBOLS:
                f.write("=" * 80 + "\n")
                f.write(f"SYMBOL: {symbol} (MULTI-SCALE)\n")
                f.write("=" * 80 + "\n\n")

                per_scale_zones = []
                latest_price = None

                for scale_name, timeframe, lookback_days in scales:
                    try:
                        scale_history = get_timeframe_bars(
                            [symbol],
                            timeframe=timeframe,
                            lookback_days=lookback_days,
                        ).get(symbol, [])
                    except Exception as e:
                        scale_history = []
                        print(
                            f"Warning: failed to load {scale_name} bars for {symbol}: {e}"
                        )

                    if not scale_history:
                        continue

                    if latest_price is None:
                        latest_price = scale_history[-1]

                    zones = sr_penguin.compute_scale_zones(
                        scale_history,
                        min_touches=2,
                        reaction_lookahead=3,
                        reaction_atr_mult=1.0,
                    )
                    for zone in zones:
                        # Cap touches and reactions to 10 per scale
                        capped_touches = min(zone["touches"], 10)
                        capped_reactions = min(zone.get("reactions", 0), 10)
                        per_scale_zones.append(
                            {
                                "center": zone["center"],
                                "low": zone["low"],
                                "high": zone["high"],
                                "touches": capped_touches,
                                "reactions": capped_reactions,
                                "score": zone.get("score", 0),
                                "scale": scale_name,
                            }
                        )

                if not per_scale_zones:
                    f.write("No zones detected.\n\n")
                    continue

                current_price = latest_price if latest_price is not None else 0.0
                tolerance = current_price * 0.003
                max_zone_width = current_price * 0.005  # Max 0.5% of price

                clusters = []
                for zone in sorted(per_scale_zones, key=lambda z: z["center"]):
                    merged = False
                    for cluster in clusters:
                        if _zones_overlap_strict(cluster, zone):
                            cluster["zones"].append(zone)
                            merged = True
                            break
                    if not merged:
                        clusters.append({"zones": [zone]})

                merged_zones = []
                for cluster in clusters:
                    zones = cluster["zones"]
                    strongest = max(zones, key=lambda z: z["score"])
                    
                    # Calculate merged bounds
                    merged_low = min(z["low"] for z in zones)
                    merged_high = max(z["high"] for z in zones)
                    merged_center = (merged_low + merged_high) / 2
                    
                    # Cap width to 0.5% of price
                    if merged_high - merged_low > max_zone_width:
                        merged_low = merged_center - max_zone_width / 2
                        merged_high = merged_center + max_zone_width / 2
                    
                    merged_zone = {
                        "center": merged_center,
                        "low": merged_low,
                        "high": merged_high,
                        "touches": sum(z["touches"] for z in zones),
                        "reactions": sum(z["reactions"] for z in zones),
                        "score": strongest["score"],
                        "scales": sorted({z["scale"] for z in zones}),
                    }
                    merged_zones.append(merged_zone)

                merged_zones.sort(key=lambda z: z["score"], reverse=True)

                f.write(f"Current price: ${current_price:.2f}\n\n")
                f.write(f"ZONES ({len(merged_zones)}):\n")
                for idx, zone in enumerate(merged_zones, 1):
                    if zone["center"] < current_price - tolerance:
                        label = "SUPPORT"
                    elif zone["center"] > current_price + tolerance:
                        label = "RESISTANCE"
                    else:
                        label = "PIVOT/RANGE"

                    f.write(f"  Zone #{idx} [{label}]:\n")
                    f.write(
                        f"    Center: ${zone['center']:.2f}\n"
                        f"    Range: ${zone['low']:.2f} - ${zone['high']:.2f}\n"
                        f"    Touches: {zone['touches']}\n"
                        f"    Reactions: {zone['reactions']}\n"
                        f"    Strength Score: {zone['score']:.2f}\n"
                        f"    Scales: {', '.join(zone['scales'])}\n"
                    )

                f.write("\n")

    def handle_sigint(signum, frame):
        print("\n\n⛔ Interrupted by user...")
        # Only save if we had meaningful trading time (>10 minutes)
        if actual_trading_minutes < 10:
            print(
                f"⏭️  Only {actual_trading_minutes} minutes of actual trading - not saving run."
            )
            sys.exit(0)

        print("💾 Saving current state...")
        # Save current curves and trades
        with open(CURVES_DATA_FILE, "w") as f:
            json.dump(curves, f, indent=2)
        with open(TRADES_LOG_FILE, "w") as f:
            f.write(f"Penguin Trading Simulation Log (Interrupted)\n")
            f.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Duration: {minute} minutes (interrupted)\n")
            f.write(f"Symbols: {', '.join(SYMBOLS)}\n")
            f.write(f"Initial Capital: ${INITIAL_CAPITAL:,.2f}\n\n")
            f.write("=" * 80 + "\n\n")

            latest_prices = {
                s: price_history[s][-1] for s in SYMBOLS if price_history[s]
            }
            consistency_warnings = {
                name: check_consistency(
                    portfolios[name],
                    latest_prices,
                    curves.get(name, []),
                )
                for name in portfolios
            }
            for name in sorted(portfolios.keys()):
                p = portfolios[name]
                v = p.value(latest_prices)
                pnl = v - INITIAL_CAPITAL
                pnl_pct = (pnl / INITIAL_CAPITAL * 100) if INITIAL_CAPITAL else 0

                f.write(f"{name}\n")
                f.write(f"  Current Value:   ${v:,.2f}\n")
                f.write(f"  PnL:             ${pnl:+,.2f}  ({pnl_pct:+.2f}%)\n")
                f.write(f"  Total Trades:    {p.trades}\n")
                f.write(f"  Current Positions: {len(p.positions)}\n")
                f.write(f"  Current Cash:    ${p.cash:,.2f}\n\n")

                warnings = consistency_warnings.get(name, [])
                if warnings:
                    f.write("  Consistency Warnings:\n")
                    for w in warnings:
                        f.write(f"    - {w}\n")
                    f.write("\n")

                if trades_log[name]:
                    f.write(f"  Trades (up to interruption):\n")
                    current_minute = None
                    for minute_num, trade_str in trades_log[name]:
                        time_bucket = (minute_num // 10) * 10
                        if time_bucket != current_minute:
                            current_minute = time_bucket
                            f.write(f"\n    Minute {time_bucket}-{time_bucket + 9}:\n")
                        f.write(f"      {trade_str}\n")
                else:
                    f.write(f"  Trades: None\n")
                f.write("\n")

        print(f"📝 Saved interrupted log to {TRADES_LOG_FILE}")
        print(f"📊 Saved interrupted curves to {CURVES_DATA_FILE}")
        # Only generate full report if run was at least 10 minutes of actual trading
        if actual_trading_minutes >= 10:
            print(
                f"\n✓ Run had {actual_trading_minutes} minutes of trading - generating full final report..."
            )

            # Get latest prices
            latest_prices = {
                s: price_history[s][-1] for s in SYMBOLS if price_history[s]
            }

            # Keep portfolios intact to avoid double-counting trades on interruption
            # Use latest prices for market value instead of force-liquidating

            # Ensure capital curve plot matches the report
            plot_capital_curves(curves, CAPITAL_CURVES_FILE)

            # Generate final PDF report
            pdf_filename = os.path.join("run_current", "report.pdf")
            create_final_report_pdf(curves, portfolios, pdf_filename, latest_prices)

            sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    minute = 0

    while minute < RUN_MINUTES:
        # Check if market is open
        try:
            market_open = client.market_is_open()
        except Exception as e:
            print(
                f"  ⚠️ Connection error checking market status: {type(e).__name__}. Retrying in 30s..."
            )
            time.sleep(30)
            continue

        if not market_open:
            try:
                clock = client.trading.get_clock()
            except Exception as e:
                print(
                    f"  ⚠️ Connection error getting clock: {type(e).__name__}. Retrying in 30s..."
                )
                time.sleep(30)
                continue

            next_open = clock.next_open
            now = datetime.now(pytz.timezone("US/Eastern"))
            time_to_open = (next_open - now).total_seconds()

            if time_to_open > 30 * 60:
                sleep_time = 30 * 60
                print(
                    f"  📴 Market closed - next open in {time_to_open/3600:.1f}h, sleeping 30 min..."
                )
            elif time_to_open > 5 * 60:
                sleep_time = 5 * 60
                print(
                    f"  📴 Market closed - next open in {time_to_open/60:.1f} min, sleeping 5 min..."
                )
            else:
                sleep_time = 30
                print(
                    f"  📴 Market closed - next open in {time_to_open:.0f} sec, sleeping 30 sec..."
                )

            time.sleep(sleep_time)
            continue  # Skip to next minute after waking

        minute += 1
        actual_trading_minutes += 1  # Increment only when market is open
        loop_start = time.time()
        print(
            f"\n=== Minute {minute}/{RUN_MINUTES} {datetime.now().strftime('%H:%M:%S')} ==="
        )

        # Poll prices for each symbol
        bid_ask_prices = {}
        price_source = {}  # Track if price is real or synthetic
        for s in SYMBOLS:
            try:
                bid, ask = client.get_bid_ask(s)
            except Exception as e:
                print(
                    f"  ⚠️ API error for {s}: {type(e).__name__}. Using synthetic price."
                )
                bid, ask = None, None

            if bid is None or ask is None:
                if USE_SYNTHETIC_DATA:
                    mid = synthetic_price_bar(s, price_history)
                    spread = mid * 0.001  # 0.1% spread for synthetic
                    bid, ask = mid - spread / 2, mid + spread / 2
                    print(f"{s}: ${bid:.2f} (synthetic)", end="  ")
                    price_source[s] = "synthetic"
                else:
                    print(f"  ⚠️ No quote for {s}, skipping")
                    continue
            else:
                mid = (bid + ask) / 2
                spread = ask - bid
                print(f"{s}: ${bid:.2f} (real)", end="  ")
                price_source[s] = "real"

            bid_ask_prices[s] = (bid, ask)
            price_history[s].append(mid)  # Store mid for history/charting

        # Let each penguin trade
        for penguin in penguins:
            portfolio = portfolios[penguin.name]
            for s in SYMBOLS:
                if s not in bid_ask_prices:
                    continue
                
                # Skip trading on synthetic data
                if price_source.get(s) == "synthetic":
                    continue

                mid_prices = price_history[s]
                if not mid_prices:
                    continue

                bid, ask = bid_ask_prices[s]

                try:
                    decision, qty = penguin.decide(s, mid_prices, bid, ask, portfolio)
                except Exception as e:
                    print(f"    ❌ {penguin.name} error on {s}: {e}")
                    continue

                if decision == "BUY":
                    # Validate price is not $0 before buying
                    if ask <= 0:
                        print(
                            f"    ⚠️ {penguin.name} skipped BUY {qty} {s} - invalid price ${ask:.2f}"
                        )
                        continue
                    # Buy at ask price
                    success = portfolio.buy(s, ask, qty=qty)
                    if success:
                        source_marker = (
                            " [synthetic]" if price_source.get(s) == "synthetic" else ""
                        )
                        print(
                            f"    ✓ {penguin.name} BUY {qty} {s} @ ${ask:.2f} (ask){source_marker}"
                        )
                        trades_log[penguin.name].append(
                            (minute, f"BUY {qty} {s} @ ${ask:.2f}{source_marker}")
                        )
                elif decision == "SELL":
                    # Validate price is not $0 before selling
                    if bid <= 0:
                        print(
                            f"    ⚠️ {penguin.name} skipped SELL {qty} {s} - invalid price ${bid:.2f}"
                        )
                        continue
                    # Sell at bid price
                    success = portfolio.sell(s, bid, qty=qty)
                    if success:
                        source_marker = (
                            " [synthetic]" if price_source.get(s) == "synthetic" else ""
                        )
                        print(
                            f"    ✓ {penguin.name} SELL {qty} {s} @ ${bid:.2f} (bid){source_marker}"
                        )
                        trades_log[penguin.name].append(
                            (minute, f"SELL {qty} {s} @ ${bid:.2f}{source_marker}")
                        )

        # Record portfolio values
        latest_prices = {s: price_history[s][-1] for s in SYMBOLS if price_history[s]}
        for penguin in penguins:
            p = portfolios[penguin.name]
            v = p.value(latest_prices)
            curves[penguin.name].append(v)

        # Plot capital curves every 10 trading minutes
        if actual_trading_minutes % 10 == 0:
            plot_capital_curves(curves, CAPITAL_CURVES_FILE)
            print(f"  {penguin.name}:")
            print(f"    Cash (pocket): ${p.cash:,.2f}")
            print(f"    Total value (cash + stocks): ${v:,.2f}")
            print(f"    Trades: {p.trades}")

        # Wait for next bar
        elapsed = time.time() - loop_start
        wait_time = BAR_TIMEFRAME_MINUTES * 60 - elapsed
        if wait_time > 0:
            print(f"  Waiting {wait_time:.1f}s for next minute...")
            time.sleep(wait_time)

    # End of run: determine winner and save results
    print("\n" + "=" * 60)
    final_values = {name: vals[-1] if vals else 0.0 for name, vals in curves.items()}

    # Filter out penguins with 0 trades for winner selection
    eligible_winners = {
        name: val for name, val in final_values.items() if portfolios[name].trades > 0
    }

    if eligible_winners:
        winner = max(eligible_winners.items(), key=lambda kv: kv[1])
        winner_name, winner_value = winner
    else:
        # If no penguin traded, pick the one with highest value anyway
        winner = max(final_values.items(), key=lambda kv: kv[1])
        winner_name, winner_value = winner
        print("⚠️ No penguin made any trades - winner selected by capital value only")

    print("\n📊 FINAL RESULTS")
    print("=" * 60)
    for name in sorted(final_values.keys()):
        val = final_values[name]
        port = portfolios[name]
        pnl = val - INITIAL_CAPITAL
        pnl_pct = (pnl / INITIAL_CAPITAL * 100) if INITIAL_CAPITAL else 0
        print(
            f"{name:25} ${val:10,.2f}  (PnL: ${pnl:+8,.2f}  {pnl_pct:+6.2f}%)  trades={port.trades}"
        )

    print(f"\n🏆 Winner: {winner_name} with ${winner_value:,.2f}")

    # Record win in scoreboard (completed run, not interrupted)
    for penguin in penguins:
        scoreboard = record_run(scoreboard, penguin.name)
    scoreboard = record_win(scoreboard, winner_name)
    save_scoreboard(scoreboard)
    print_scoreboard(scoreboard)

    # Save capital curves plot
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
            linewidth=2,
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
    plt.title(f"Penguin Capital Over {RUN_MINUTES} Minutes")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(CAPITAL_CURVES_FILE, dpi=100)
    print(f"\n📈 Saved capital curves to {CAPITAL_CURVES_FILE}")

    now = datetime.now()
    rounded_minute = (now.minute // 10) * 10
    date_stamp = now.strftime("%y%m%d")
    time_stamp = f"{now.hour:02d}{rounded_minute:02d}"
    final_plot_name = f"capital_curve_{date_stamp}_{time_stamp}.png"
    final_plot_path = os.path.join(PLOTS_DIR, final_plot_name)
    shutil.copy2(CAPITAL_CURVES_FILE, final_plot_path)
    print(f"📈 Saved final capital curves to {final_plot_path}")

    # Generate final PDF report with capital curves and trade summary
    latest_prices = {s: price_history[s][-1] for s in SYMBOLS if price_history[s]}
    pdf_filename = os.path.join("run_current", "report.pdf")
    create_final_report_pdf(curves, portfolios, pdf_filename, latest_prices)

    # Keep all outputs in run_current only

    # Save trades log
    with open(TRADES_LOG_FILE, "w") as f:
        f.write(f"Penguin Trading Simulation Log\n")
        f.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Duration: {RUN_MINUTES} minutes\n")
        f.write(f"Symbols: {', '.join(SYMBOLS)}\n")
        f.write(f"Initial Capital: ${INITIAL_CAPITAL:,.2f}\n\n")
        f.write("=" * 80 + "\n\n")

        consistency_warnings = {
            name: check_consistency(
                portfolios[name],
                latest_prices,
                curves.get(name, []),
            )
            for name in portfolios
        }

        for name in sorted(portfolios.keys()):
            port = portfolios[name]
            val = final_values[name]
            pnl = val - INITIAL_CAPITAL
            pnl_pct = (pnl / INITIAL_CAPITAL * 100) if INITIAL_CAPITAL else 0

            f.write(f"{name}\n")
            f.write(f"  Final Value:   ${val:,.2f}\n")
            f.write(f"  PnL:           ${pnl:+,.2f}  ({pnl_pct:+.2f}%)\n")
            f.write(f"  Total Trades:  {port.trades}\n")
            f.write(f"  Final Positions: {len(port.positions)}\n")
            f.write(f"  Final Cash:    ${port.cash:,.2f}\n\n")

            warnings = consistency_warnings.get(name, [])
            if warnings:
                f.write("  Consistency Warnings:\n")
                for w in warnings:
                    f.write(f"    - {w}\n")
                f.write("\n")

            if trades_log[name]:
                f.write(f"  Trades:\n")
                current_minute = None
                for minute_num, trade_str in trades_log[name]:
                    time_bucket = (minute_num // 10) * 10
                    if time_bucket != current_minute:
                        current_minute = time_bucket
                        f.write(f"\n    Minute {time_bucket}-{time_bucket + 9}:\n")
                    f.write(f"      {trade_str}\n")
            else:
                f.write(f"  Trades: None\n")
            f.write("\n")

    print(f"📝 Saved trades log to {TRADES_LOG_FILE}")

    # Save curves data
    with open(CURVES_DATA_FILE, "w") as f:
        json.dump(curves, f, indent=2)
    print(f"📊 Saved curves data to {CURVES_DATA_FILE}")


if __name__ == "__main__":
    run()
