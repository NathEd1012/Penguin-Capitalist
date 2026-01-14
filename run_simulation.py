import time
import signal
import sys

from config import SYMBOLS, SIMULATION_MINUTES
from data.alpaca_history import get_minute_bars

from penguins import (
    MomentumPenguin,
    MeanReversionPenguin,
    BreakoutPenguin,
)

from backtest.simulator import Simulator
from backtest.metrics import evaluate


def run():
    penguins = [
        MomentumPenguin(),
        MeanReversionPenguin(),
        BreakoutPenguin(),
    ]

    price_data = get_minute_bars(SYMBOLS, SIMULATION_MINUTES)

    for penguin in penguins:
        print(f"\n🐧 Starting {penguin.name}")
        sim = Simulator(penguin, SYMBOLS)

        try:
            for i in range(SIMULATION_MINUTES):
                step_prices = {
                    s: price_data[s][i] for s in SYMBOLS if i < len(price_data[s])
                }

                sim.step(step_prices)

                if i % 10 == 0:
                    value = sim.portfolio.value(step_prices)
                    print(
                        f"[{penguin.name}] "
                        f"minute={i:03d} "
                        f"value=${value:,.2f} "
                        f"cash=${sim.portfolio.cash:,.2f} "
                        f"positions={len(sim.portfolio.positions)}"
                    )

                time.sleep(0.01)

        except KeyboardInterrupt:
            print("\n⛔ Interrupted by user")

        finally:
            metrics = evaluate(sim.portfolio, sim.price_history)
            print(f"\n📊 Final results for {penguin.name}")
            for k, v in metrics.items():
                print(f"{k}: {v}")


if __name__ == "__main__":
    run()
