import time
import signal
import sys
import random
from collections import defaultdict
from datetime import datetime, timedelta
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
    RandomPenguin,
    RandomPenguin2,
    TrendPenguin,
    CarefulTrendPenguin,
    CopilotPenguin,
    MovingAverageCrossoverPenguin,
    RSIMeanReversionPenguin,
    VolatilityBreakoutPenguin,
)


def synthetic_price_bar(symbol, price_history):
    """Generate synthetic price when Alpaca has no data."""
    if symbol not in price_history or not price_history[symbol]:
        return 100.0 + hash(symbol) % 50
    last = price_history[symbol][-1]
    change_pct = random.gauss(0, 0.3)
    return max(0.01, last * (1 + change_pct / 100))


def plot_capital_curves(curves, filename):
    """Plot and save capital curves."""
    plt.figure(figsize=(12, 6))
    for name, vals in curves.items():
        plt.plot(range(1, len(vals) + 1), vals, marker="o", label=name, linewidth=2)

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
            marker="s",
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
        RandomPenguin(),
        RandomPenguin2(),
        TrendPenguin(),
        CarefulTrendPenguin(),
        CopilotPenguin(),
        MovingAverageCrossoverPenguin(),
        RSIMeanReversionPenguin(),
        VolatilityBreakoutPenguin(),
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

    def handle_sigint(signum, frame):
        print("\n\n⛔ Interrupted by user (scoreboard not updated)")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    start_time = time.time()
    minute = 0

    while minute < RUN_MINUTES:
        if not client.market_is_open():
            clock = client.trading.get_clock()
            next_open = clock.next_open
            wake_up = next_open - timedelta(minutes=5)
            now = client.now_et()
            if wake_up > now:
                sleep_seconds = (wake_up - now).total_seconds()
                print(
                    f"Market is closed — sleeping {sleep_seconds:.0f}s until 5 min before open"
                )
                time.sleep(sleep_seconds)
            else:
                print("Market is closed — sleeping 30s")
                time.sleep(30)
            continue

        minute += 1
        print(
            f"\n=== Minute {minute}/{RUN_MINUTES} {datetime.now().strftime('%H:%M:%S')} ==="
        )

        # Poll prices for each symbol
        for s in SYMBOLS:
            try:
                price = client.get_mid_price(s)
            except Exception as e:
                print(
                    f"  ⚠️ API error for {s}: {type(e).__name__}. Using synthetic price."
                )
                price = None

            if price is None:
                if USE_SYNTHETIC_DATA:
                    price = synthetic_price_bar(s, price_history)
                    print(f"  {s}: ${price:.2f} (synthetic)")
                else:
                    print(f"  ⚠️ No quote for {s}, skipping")
                    continue
            else:
                print(f"  {s}: ${price:.2f}")
            price_history[s].append(price)

        # Let each penguin trade
        for penguin in penguins:
            portfolio = portfolios[penguin.name]
            for s in SYMBOLS:
                prices = price_history[s]
                if not prices:
                    continue
                try:
                    decision, qty = penguin.decide(s, prices, portfolio)
                except Exception as e:
                    print(f"    ❌ {penguin.name} error on {s}: {e}")
                    continue

                latest_price = prices[-1]
                if decision == "BUY":
                    success = portfolio.buy(s, latest_price, qty=qty)
                    if success:
                        print(
                            f"    ✓ {penguin.name} BUY {qty} {s} @ ${latest_price:.2f}"
                        )
                        trades_log[penguin.name].append(
                            f"BUY {qty} {s} @ ${latest_price:.2f}"
                        )
                elif decision == "SELL":
                    success = portfolio.sell(s, latest_price, qty=qty)
                    if success:
                        print(
                            f"    ✓ {penguin.name} SELL {qty} {s} @ ${latest_price:.2f}"
                        )
                        trades_log[penguin.name].append(
                            f"SELL {qty} {s} @ ${latest_price:.2f}"
                        )

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
        elapsed = time.time() - start_time
        next_bar_time = minute * BAR_TIMEFRAME_MINUTES * 60
        wait_time = next_bar_time - elapsed
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
        plt.plot(range(1, len(vals) + 1), vals, marker="o", label=name, linewidth=2)

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
            marker="s",
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
    plt.title(f"Penguin Capital Over {RUN_MINUTES} Minutes")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(CAPITAL_CURVES_FILE, dpi=100)
    print(f"\n📈 Saved capital curves to {CAPITAL_CURVES_FILE}")

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


if __name__ == "__main__":
    run()
