import time
import signal
import sys
import os
import json
import pytz
from collections import defaultdict
from datetime import datetime
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

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

# Import utility modules from scripts
from scripts import (
    synthetic_price_bar,
    plot_capital_curves,
    create_final_report_pdf,
    check_consistency,
    save_run_results_to_archive,
    compute_and_log_support_resistance_zones,
)


def run():
    # Track when the run started for archiving
    run_start_time = datetime.now()
    
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
    last_values = {p.name: INITIAL_CAPITAL for p in penguins}
    drop_alert_pct = 5.0

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

        # Compute and log Support & Resistance zones
        compute_and_log_support_resistance_zones(sr_penguin, SYMBOLS, scales)

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

            # Forced liquidation on interrupt: sell all remaining positions
            print("\n⚡ Performing forced liquidation of all positions...")
            for penguin in penguins:
                portfolio = portfolios[penguin.name]
                if not portfolio.positions:
                    print(f"  {penguin.name}: No open positions")
                    continue
                
                for symbol in list(portfolio.positions.keys()):
                    position = portfolio.positions[symbol]
                    qty = position.qty
                    if qty > 0 and symbol in latest_prices:
                        bid_price = latest_prices[symbol]
                        success = portfolio.sell(symbol, bid_price, qty=qty)
                        if success:
                            print(f"    ✓ {penguin.name} FORCED SELL {qty} {symbol} @ ${bid_price:.2f} [liquidation]")
                            trades_log[penguin.name].append(
                                (minute, f"FORCED SELL {qty} {symbol} @ ${bid_price:.2f} [liquidation]")
                            )

            # Update latest prices after liquidation
            latest_prices = {
                s: price_history[s][-1] for s in SYMBOLS if price_history[s]
            }

            # Ensure capital curve plot matches the report
            plot_capital_curves(curves, CAPITAL_CURVES_FILE)

            # Generate final PDF report
            pdf_filename = os.path.join("run_current", "report.pdf")
            create_final_report_pdf(curves, portfolios, pdf_filename, latest_prices)
            
            # Archive run results to both run_old and run_current
            save_run_results_to_archive(run_start_time)

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
                spread_pct = (spread / bid * 100) if bid > 0 else 0
                
                # Check for stale data: price differs >10% from last known price
                is_stale = False
                if price_history[s]:
                    last_price = price_history[s][-1]
                    price_change_pct = abs(mid - last_price) / last_price * 100
                    if price_change_pct > 10:
                        print(f"{s}: ${bid:.2f} ⚠️ STALE ({price_change_pct:.1f}% jump)", end="  ")
                        is_stale = True
                
                # Check for unrealistic spread (>5%)
                is_wide_spread = spread_pct > 5.0
                if is_wide_spread and not is_stale:
                    print(f"{s}: ${bid:.2f} ⚠️ WIDE SPREAD ({spread_pct:.1f}%)", end="  ")
                
                # If data is suspicious, treat as synthetic (no trading except final sell)
                if is_stale or is_wide_spread:
                    price_source[s] = "suspicious"
                else:
                    print(f"{s}: ${bid:.2f}", end="  ")
                    price_source[s] = "real"

            bid_ask_prices[s] = (bid, ask)
            price_history[s].append(mid)  # Store mid for history/charting

        # Let each penguin trade
        is_final_iteration = (minute == RUN_MINUTES)
        for penguin in penguins:
            portfolio = portfolios[penguin.name]
            for s in SYMBOLS:
                if s not in bid_ask_prices:
                    continue
                
                # Skip trading on synthetic/suspicious data (except allow SELL on final iteration)
                if price_source.get(s) in ["synthetic", "suspicious"] and not is_final_iteration:
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
                    # Do not allow BUY on synthetic/suspicious data at any time
                    if price_source.get(s) in ["synthetic", "suspicious"]:
                        print(
                            f"    ⚠️ {penguin.name} skipped BUY {qty} {s} - unreliable data ({price_source.get(s)})"
                        )
                        continue
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
                    # Do not allow SELL on synthetic/suspicious data, except on final iteration
                    if price_source.get(s) in ["synthetic", "suspicious"] and not is_final_iteration:
                        print(
                            f"    ⚠️ {penguin.name} skipped SELL {qty} {s} - unreliable data ({price_source.get(s)})"
                        )
                        continue
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

            previous_value = last_values.get(penguin.name, v)
            if previous_value > 0:
                drop_pct = (v - previous_value) / previous_value * 100
                if drop_pct <= -drop_alert_pct:
                    print(
                        f"  ⚠️ {penguin.name} value drop {drop_pct:.2f}% (minute {minute})"
                    )
                    print(f"    Cash: ${p.cash:,.2f}  Value: ${v:,.2f}")
                    if p.positions:
                        print("    Positions:")
                        for symbol, pos in p.positions.items():
                            last_price = latest_prices.get(symbol, pos.avg_price)
                            pnl = (last_price - pos.avg_price) * pos.qty
                            print(
                                f"      {symbol} qty={pos.qty} avg=${pos.avg_price:.2f} last=${last_price:.2f} pnl=${pnl:+.2f}"
                            )
                    else:
                        print("    Positions: none")

            last_values[penguin.name] = v

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
    
    # Save run results to both run_old and run_current
    save_run_results_to_archive(run_start_time)

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
