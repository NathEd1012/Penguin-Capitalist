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
)
from data_client import AlpacaClient
from backtest.portfolio import Portfolio
from data.scoreboard import (
    load_scoreboard,
    save_scoreboard,
    register_penguin,
    record_win,
    record_run,
    print_scoreboard,
)

from penguins import (
    MomentumPenguin,
    MeanReversionPenguin,
    BreakoutPenguin,
    TrendPenguin,
)


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


def create_final_report_pdf(curves, portfolios, filename):
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

            summary = portfolio.get_symbol_summary()

            # Build table data
            table_data = [
                [
                    "Symbol",
                    "Buy Cnt",
                    "Sell Cnt",
                    "Total Qty Bought",
                    "Total Cost",
                    "Total Revenue",
                    "PnL",
                    "PnL %",
                ]
            ]

            total_pnl = 0
            for symbol in sorted(summary.keys()):
                s = summary[symbol]
                pnl = s["pnl"]
                pnl_pct = s["pnl_pct"]
                total_pnl += pnl

                table_data.append(
                    [
                        symbol,
                        str(s["buy_count"]),
                        str(s["sell_count"]),
                        str(s["total_qty_bought"]),
                        f"${s['total_cost']:,.2f}",
                        f"${s['total_revenue']:,.2f}",
                        f"${pnl:,.2f}",
                        f"{pnl_pct:+.2f}%",
                    ]
                )

            # Add total row
            table_data.append(["TOTAL", "", "", "", "", "", f"${total_pnl:,.2f}", ""])

            table = ax.table(
                cellText=table_data,
                cellLoc="center",
                loc="center",
                colWidths=[0.1, 0.1, 0.1, 0.15, 0.15, 0.15, 0.15, 0.1],
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

            plt.tight_layout()
            pdf.savefig(fig, bbox_inches="tight")
            plt.close()

    print(f"📄 Final report saved to {filename}")


def run():
    # Load scoreboard and register penguins
    scoreboard = load_scoreboard()

    print(f"🐧 Starting live simulation for {RUN_MINUTES} minutes")
    print(f"Symbols: {SYMBOLS}")
    print(f"Interval: {BAR_TIMEFRAME_MINUTES} minute(s) per bar\n")

    client = AlpacaClient(paper=True)

    penguins = [
        MomentumPenguin(),
        MeanReversionPenguin(),
        BreakoutPenguin(),
        TrendPenguin(),
    ]

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
    trades_log = {p.name: [] for p in penguins}
    actual_trading_minutes = 0  # Track minutes when market was actually open

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

                if trades_log[name]:
                    f.write(f"  Trades (up to interruption):\n")
                    for i, trade in enumerate(trades_log[name], 1):
                        f.write(f"    {i}. {trade}\n")
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

            # Liquidate all positions at market mid-prices
            print("💨 Liquidating all positions...")
            for penguin in penguins:
                portfolio = portfolios[penguin.name]
                for symbol in list(portfolio.positions.keys()):
                    pos = portfolio.positions[symbol]
                    if pos.qty > 0:
                        price = latest_prices.get(symbol, 100.0)
                        portfolio.sell(symbol, price, qty=pos.qty)
                        print(
                            f"  {penguin.name}: Sold {pos.qty} {symbol} @ ${price:.2f}"
                        )

            # Record final portfolio values
            for penguin in penguins:
                p = portfolios[penguin.name]
                v = p.value(latest_prices)
                curves[penguin.name].append(v)

            # Generate final PDF report
            pdf_filename = os.path.join("run_current", "report_interrupted.pdf")
            create_final_report_pdf(curves, portfolios, pdf_filename)

            # Archive to run_old with day/time structure
            now = datetime.now().replace(minute=0, second=0)
            date_str = now.strftime("%y%m%d")
            time_str = now.strftime("%H%M")
            old_run_dir = os.path.join("run_old", date_str, f"run_{time_str}")
            os.makedirs(old_run_dir, exist_ok=True)

            for filename in os.listdir("run_current"):
                src = os.path.join("run_current", filename)
                if os.path.isfile(src):
                    dst = os.path.join(old_run_dir, filename)
                    shutil.copy2(src, dst)
            print(f"💾 Archived interrupted run to {old_run_dir}")
            sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    minute = 0

    while minute < RUN_MINUTES:
        # Check if market is open
        try:
            market_open = client.market_is_open()
        except Exception as e:
            print(f"  ⚠️ Connection error checking market status: {type(e).__name__}. Retrying in 30s...")
            time.sleep(30)
            continue
        
        if not market_open:
            try:
                clock = client.trading.get_clock()
            except Exception as e:
                print(f"  ⚠️ Connection error getting clock: {type(e).__name__}. Retrying in 30s...")
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
                    print(f"{s}: ${bid:.2f}", end="  ")
                else:
                    print(f"  ⚠️ No quote for {s}, skipping")
                    continue
            else:
                mid = (bid + ask) / 2
                spread = ask - bid
                print(f"{s}: ${bid:.2f}", end="  ")

            bid_ask_prices[s] = (bid, ask)
            price_history[s].append(mid)  # Store mid for history/charting

        # Let each penguin trade
        for penguin in penguins:
            portfolio = portfolios[penguin.name]
            for s in SYMBOLS:
                if s not in bid_ask_prices:
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
                        print(f"    ✓ {penguin.name} BUY {qty} {s} @ ${ask:.2f} (ask)")
                        trades_log[penguin.name].append(f"BUY {qty} {s} @ ${ask:.2f}")
                elif decision == "SELL":
                    # Sell at bid price
                    success = portfolio.sell(s, bid, qty=qty)
                    if success:
                        print(f"    ✓ {penguin.name} SELL {qty} {s} @ ${bid:.2f} (bid)")
                        trades_log[penguin.name].append(f"SELL {qty} {s} @ ${bid:.2f}")

        # Record portfolio values
        latest_prices = {s: price_history[s][-1] for s in SYMBOLS if price_history[s]}
        for penguin in penguins:
            p = portfolios[penguin.name]
            v = p.value(latest_prices)
            curves[penguin.name].append(v)

        # Plot capital curves every 10 minutes
        if minute % 10 == 0:
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

    # Generate final PDF report with capital curves and trade summary
    pdf_filename = os.path.join("run_current", "report.pdf")
    create_final_report_pdf(curves, portfolios, pdf_filename)

    # Save to run_old only if meaningful run (>10 minutes of actual trading)
    if actual_trading_minutes >= 10:
        now = datetime.now().replace(minute=0, second=0)
        date_str = now.strftime("%y%m%d")
        time_str = now.strftime("%H%M")
        old_run_dir = os.path.join("run_old", date_str, f"run_{time_str}")
        os.makedirs(old_run_dir, exist_ok=True)

        # Copy files from run_current to timestamped folder in run_old
        for filename in os.listdir("run_current"):
            src = os.path.join("run_current", filename)
            if os.path.isfile(src):
                dst = os.path.join(old_run_dir, filename)
                shutil.copy2(src, dst)
        print(f"💾 Archived run to {old_run_dir}")
    else:
        print(
            f"⏭️  Only {actual_trading_minutes} minutes of actual trading - not archiving to run_old."
        )

    # Save trades log
    with open(TRADES_LOG_FILE, "w") as f:
        f.write(f"Penguin Trading Simulation Log\n")
        f.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Duration: {RUN_MINUTES} minutes\n")
        f.write(f"Symbols: {', '.join(SYMBOLS)}\n")
        f.write(f"Initial Capital: ${INITIAL_CAPITAL:,.2f}\n\n")
        f.write("=" * 80 + "\n\n")

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

            if trades_log[name]:
                f.write(f"  Trades:\n")
                for i, trade in enumerate(trades_log[name], 1):
                    f.write(f"    {i}. {trade}\n")
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
