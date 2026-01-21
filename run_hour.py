import time
import signal
import sys
from collections import defaultdict
import random
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config import (
    SYMBOLS,
    BAR_TIMEFRAME_MINUTES,
    INITIAL_CAPITAL,
    TRANSACTION_COST,
    ENABLE_TRANSACTION_COSTS,
    ORDER_QTY,
    RUN_MINUTES,
    USE_SYNTHETIC_DATA,
    FAST_MODE,
    CAPITAL_CURVES_FILE,
    TRADES_LOG_FILE,
)
from data_client import AlpacaClient
from backtest.portfolio import Portfolio
from penguins import (
    MomentumPenguin,
    MeanReversionPenguin,
    BreakoutPenguin,
    CopilotPenguin,
)


def synthetic_price_bar(symbol, price_history):
    """Generate a synthetic price bar for testing when Alpaca returns no data."""
    if symbol not in price_history or not price_history[symbol]:
        return 100.0 + hash(symbol) % 50
    last = price_history[symbol][-1]
    change_pct = random.gauss(0, 0.3)
    return max(0.01, last * (1 + change_pct / 100))


def run():
    client = AlpacaClient(paper=True)

    penguins = [MomentumPenguin(), MeanReversionPenguin(), BreakoutPenguin(), CopilotPenguin()]
    portfolios = {
        p.name: Portfolio(cash=INITIAL_CAPITAL, fee_per_trade=TRANSACTION_COST, enable_fees=ENABLE_TRANSACTION_COSTS)
        for p in penguins
    }

    symbols = SYMBOLS
    interval = BAR_TIMEFRAME_MINUTES * 60
    minutes_to_run = RUN_MINUTES

    price_history = defaultdict(list)
    curves = {p.name: [] for p in penguins}
    trades_log = []  # List of (minute, penguin, symbol, action, price)

    def handle_sigint(signum, frame):
        print("\n⛔ Interrupted, exiting run")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    print(
        f"🐧 Starting: {minutes_to_run} min | fast_mode={FAST_MODE} | synthetic={USE_SYNTHETIC_DATA}"
    )
    print(
        f"   Symbols: {', '.join(symbols)} | Initial Capital: ${INITIAL_CAPITAL:,.2f}\n"
    )

    for minute in range(minutes_to_run):
        print(f"\n=== Minute {minute+1}/{minutes_to_run} ===")

        # poll prices for each symbol
        for s in symbols:
            price = client.get_mid_price(s)
            if price is None:
                if USE_SYNTHETIC_DATA:
                    price = synthetic_price_bar(s, price_history)
                else:
                    print(f"  ⚠️ No quote for {s}, skipping")
                    continue
            price_history[s].append(price)

        # let each penguin see the latest prices and decide for each symbol
        for penguin in penguins:
            portfolio = portfolios[penguin.name]
            for s in symbols:
                prices = price_history[s]
                if not prices:
                    continue
                try:
                    decision = penguin.decide(s, prices, portfolio)
                except Exception as e:
                    print(f"  ❌ Error in {penguin.name}.decide for {s}: {e}")
                    continue

                latest_price = prices[-1]
                if decision == "BUY":
                    success = portfolio.buy(s, latest_price, qty=ORDER_QTY)
                    if success:
                        trades_log.append(
                            (minute + 1, penguin.name, s, "BUY", latest_price)
                        )
                        print(
                            f"  ✓ [BUY]  {penguin.name:20s} {s:5s} @ ${latest_price:8.2f}"
                        )

                elif decision == "SELL":
                    success = portfolio.sell(s, latest_price, qty=ORDER_QTY)
                    if success:
                        trades_log.append(
                            (minute + 1, penguin.name, s, "SELL", latest_price)
                        )
                        print(
                            f"  ✓ [SELL] {penguin.name:20s} {s:5s} @ ${latest_price:8.2f}"
                        )

        # record total capital for each penguin
        latest_prices = {s: price_history[s][-1] for s in symbols if price_history[s]}
        for penguin in penguins:
            p = portfolios[penguin.name]
            v = p.value(latest_prices)
            curves[penguin.name].append(v)
            print(
                f"  {penguin.name:20s}: ${v:>10,.2f} | cash=${p.cash:>10,.2f} | trades={p.trades}"
            )

        if FAST_MODE:
            time.sleep(0.01)
        else:
            time.sleep(interval)

    # ===== END OF RUN: SUMMARY & FILES =====
    final_values = {name: vals[-1] if vals else 0.0 for name, vals in curves.items()}
    winner = max(final_values.items(), key=lambda kv: kv[1])

    print("\n" + "=" * 70)
    print("FINAL RESULTS".center(70))
    print("=" * 70)
    for name, val in sorted(final_values.items(), key=lambda kv: kv[1], reverse=True):
        profit = val - INITIAL_CAPITAL
        pct = (profit / INITIAL_CAPITAL * 100) if INITIAL_CAPITAL > 0 else 0
        print(f"  {name:25} ${val:>10,.2f}  ({profit:+.2f}, {pct:+.1f}%)")
    print(f"\n  🏆 Winner: {winner[0]} with ${winner[1]:,.2f}")
    print("=" * 70)

    # Save capital curves plot
    plt.figure(figsize=(12, 6))
    for name, vals in curves.items():
        plt.plot(range(1, len(vals) + 1), vals, marker="o", label=name, linewidth=2)
    plt.axhline(
        y=INITIAL_CAPITAL,
        color="gray",
        linestyle="--",
        alpha=0.5,
        label="Initial Capital",
    )
    plt.xlabel("Minute", fontsize=12)
    plt.ylabel("Total Capital ($)", fontsize=12)
    plt.title(
        f"Penguin Capital Over {minutes_to_run} Minutes", fontsize=14, fontweight="bold"
    )
    plt.legend(fontsize=10)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(CAPITAL_CURVES_FILE, dpi=100)
    print(f"\n📊 Saved: {CAPITAL_CURVES_FILE}")

    # Save trades log
    with open(TRADES_LOG_FILE, "w") as f:
        f.write(f"TRADES LOG - {minutes_to_run} minute run\n")
        f.write("=" * 80 + "\n\n")
        if trades_log:
            for minute, penguin, symbol, action, price in trades_log:
                f.write(
                    f"Minute {minute:2d} | {penguin:20s} | {action:4s} {symbol:5s} @ ${price:8.2f}\n"
                )
            f.write(f"\nTotal trades executed: {len(trades_log)}\n")
        else:
            f.write("No trades executed.\n")
        f.write("\n" + "=" * 80 + "\n")
        f.write("FINAL PORTFOLIO STATUS\n")
        f.write("=" * 80 + "\n\n")
        for name, portfolio in portfolios.items():
            f.write(f"{name}\n")
            f.write(f"  Final Value: ${final_values[name]:,.2f}\n")
            f.write(f"  Cash: ${portfolio.cash:,.2f}\n")
            f.write(f"  Positions: {len(portfolio.positions)}\n")
            f.write(f"  Total Trades: {portfolio.trades}\n")
            if portfolio.positions:
                f.write(f"  Holdings:\n")
                for symbol, pos in portfolio.positions.items():
                    f.write(f"    {symbol}: {pos.qty} @ avg ${pos.avg_price:.2f}\n")
            f.write("\n")
    print(f"📝 Saved: {TRADES_LOG_FILE}\n")


if __name__ == "__main__":
    run()
