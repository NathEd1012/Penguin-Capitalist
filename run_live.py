import time
import signal
import sys
from collections import defaultdict
import argparse

from config import SYMBOLS, BAR_TIMEFRAME_MINUTES
from data_client import AlpacaClient
from backtest.portfolio import Portfolio
from penguins import (
    MomentumPenguin,
    MeanReversionPenguin,
    BreakoutPenguin,
)


def run(args):
    client = AlpacaClient(paper=args.paper)

    penguins = [MomentumPenguin(), MeanReversionPenguin(), BreakoutPenguin()]
    portfolios = {p.name: Portfolio() for p in penguins}

    symbols = args.symbols or SYMBOLS
    interval = args.interval or (BAR_TIMEFRAME_MINUTES * 60)

    price_history = defaultdict(list)

    def handle_sigint(signum, frame):
        print("\n⛔ Interrupted, exiting live runner")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    if not args.execute:
        print(
            "⚠️ Running in dry-run mode (no orders will be submitted). Use --execute to place orders."
        )

    while True:
        if not client.market_is_open():
            print("Market is closed — sleeping 30s")
            time.sleep(30)
            continue

        for s in symbols:
            price = client.get_mid_price(s)
            if price is None:
                print(f"No quote for {s}, skipping")
                continue

            price_history[s].append(price)

            for penguin in penguins:
                portfolio = portfolios[penguin.name]
                try:
                    decision = penguin.decide(s, price_history[s], portfolio)
                except Exception as e:
                    print(f"Error in strategy {penguin.name} for {s}: {e}")
                    continue

                if decision == "BUY":
                    print(f"[{penguin.name}] BUY {s} @ {price:.2f}")
                    if args.execute:
                        try:
                            order = client.buy_market(s, qty=args.qty)
                            print(f"Order submitted: {order}")
                            portfolio.buy(s, price, qty=args.qty)
                        except Exception as e:
                            print(f"Order error: {e}")

                elif decision == "SELL":
                    print(f"[{penguin.name}] SELL {s} @ {price:.2f}")
                    if args.execute:
                        try:
                            order = client.sell_market(s, qty=args.qty)
                            print(f"Order submitted: {order}")
                            portfolio.sell(s, price, qty=args.qty)
                        except Exception as e:
                            print(f"Order error: {e}")

        if args.once:
            print("One-shot run complete (dry-run). Exiting.")
            break

        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(
        description="Run live trading loop (paper by default)"
    )
    parser.add_argument(
        "--symbols", nargs="+", help="Symbols to trade (overrides config)"
    )
    parser.add_argument("--interval", type=int, help="Polling interval in seconds")
    parser.add_argument("--qty", type=int, default=1, help="Quantity per order")
    parser.add_argument(
        "--paper",
        action="store_true",
        default=True,
        help="Use Alpaca paper account (default)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually submit orders (disabled by default)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single iteration and exit (useful for testing)",
    )

    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
