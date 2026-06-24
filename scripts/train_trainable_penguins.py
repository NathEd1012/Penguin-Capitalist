"""Train the trainable penguin strategies on a compact stock subset.

The search objective is lexicographic:
1. Maximize final portfolio value.
2. Minimize the number of trades when final value is tied.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.backtest import BINNING, START_DATE, STOP_DATE
from config.portfolio import INITIAL_CAPITAL
from config.training import (
    TRAINING_PENGUINS,
    TRAINING_SYMBOLS,
    TRAINING_TRANSACTION_COST,
)
from run_simulation import parse_datetime_string, run_backtest


ParameterDict = dict[str, int | float]


def _sample_trainable_penguin1(rng: random.Random) -> ParameterDict:
    buy_rsi = rng.uniform(18.0, 42.0)
    sell_rsi = rng.uniform(max(buy_rsi + 8.0, 55.0), 88.0)
    return {
        "rsi_period": rng.randint(7, 28),
        "buy_rsi": round(buy_rsi, 2),
        "sell_rsi": round(sell_rsi, 2),
        "max_cash_fraction_per_trade": round(rng.uniform(0.02, 0.20), 4),
        "stop_loss_pct": round(rng.uniform(0.01, 0.10), 4),
        "take_profit_pct": round(rng.uniform(0.02, 0.20), 4),
        "cooldown_bars": rng.randint(0, 30),
    }


def _sample_trainable_penguin2(rng: random.Random) -> ParameterDict:
    return {
        "bb_period": rng.randint(10, 40),
        "bb_stddev": round(rng.uniform(1.0, 3.5), 2),
        "adx_period": rng.randint(7, 28),
        "adx_threshold": round(rng.uniform(10.0, 40.0), 2),
        "max_cash_fraction_per_trade": round(rng.uniform(0.02, 0.20), 4),
        "stop_loss_pct": round(rng.uniform(0.01, 0.10), 4),
        "take_profit_pct": round(rng.uniform(0.02, 0.20), 4),
        "cooldown_bars": rng.randint(0, 30),
    }


def _strategy_sampler(strategy_class) -> Callable[[random.Random], ParameterDict]:
    strategy_name = strategy_class.__name__
    if strategy_name.endswith("TrainablePenguin1") or strategy_name.endswith("TrainablePenguin1_Manual"):
        return _sample_trainable_penguin1
    if strategy_name.endswith("TrainablePenguin2") or strategy_name.endswith("TrainablePenguin2_Manual"):
        return _sample_trainable_penguin2
    raise ValueError(f"No parameter sampler is defined for {strategy_name}")


def _evaluate_strategy(
    strategy_instance,
    symbols: list[str],
    start_dt: datetime,
    end_dt: datetime,
    binning: str,
) -> dict[str, Any]:
    results, _, _, _, _, _ = run_backtest(
        symbols=symbols,
        start_datetime=start_dt,
        end_datetime=end_dt,
        binning=binning,
        initial_capital=INITIAL_CAPITAL,
        transaction_cost=TRAINING_TRANSACTION_COST,
        penguin_classes=[strategy_instance],
    )
    _, metrics = next(iter(results.values()))
    return metrics


def _score_metrics(metrics: dict[str, Any]) -> tuple[float, int]:
    return float(metrics.get("final_value", 0.0)), -int(metrics.get("total_trades", 0))


def train_strategy(
    strategy_class,
    symbols: list[str],
    start_dt: datetime,
    end_dt: datetime,
    binning: str,
    trials: int,
    seed: int,
) -> dict[str, Any]:
    rng = random.Random(seed)
    sampler = _strategy_sampler(strategy_class)

    baseline_instance = strategy_class()
    baseline_metrics = _evaluate_strategy(baseline_instance, symbols, start_dt, end_dt, binning)
    best_params = asdict(getattr(baseline_instance, "params", {})) if hasattr(baseline_instance, "params") else {}
    best_metrics = baseline_metrics
    best_score = _score_metrics(baseline_metrics)
    trial_history: list[dict[str, Any]] = []

    for trial_number in range(1, trials + 1):
        params = sampler(rng)
        candidate = strategy_class(**params)
        metrics = _evaluate_strategy(candidate, symbols, start_dt, end_dt, binning)
        score = _score_metrics(metrics)

        trial_entry = {
            "trial": trial_number,
            "params": params,
            "metrics": metrics,
            "score": list(score),
        }
        trial_history.append(trial_entry)

        if score > best_score:
            best_score = score
            best_params = params
            best_metrics = metrics

        print(
            f"  Trial {trial_number:03d}: final=${metrics.get('final_value', 0.0):,.2f}, "
            f"trades={metrics.get('total_trades', 0)}, score={score}"
        )

    return {
        "strategy": strategy_class.__name__,
        "baseline_metrics": baseline_metrics,
        "best_params": best_params,
        "best_metrics": best_metrics,
        "best_score": list(best_score),
        "trials": trial_history,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=12, help="Random parameter samples per strategy.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducible sampling.")
    parser.add_argument(
        "--symbols",
        nargs="*",
        default=TRAINING_SYMBOLS,
        help="Stock subset to train on. Defaults to a compact liquid basket.",
    )
    parser.add_argument("--start-date", default=START_DATE, help="Backtest start date.")
    parser.add_argument("--stop-date", default=STOP_DATE, help="Backtest stop date.")
    parser.add_argument("--binning", default=BINNING, help="Bar size to use during training.")
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "training_results" / "json"),
        help="Directory for the JSON training report.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    start_dt = parse_datetime_string(args.start_date)
    end_dt = parse_datetime_string(args.stop_date)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "symbols": list(args.symbols),
        "start_date": args.start_date,
        "stop_date": args.stop_date,
        "binning": args.binning,
        "transaction_cost": TRAINING_TRANSACTION_COST,
        "trials": args.trials,
        "seed": args.seed,
        "manual_baselines": [],
        "trained_strategies": [],
    }

    print("Training manual baselines")
    for manual_class in TRAINING_MANUAL_PENGUINS:
        metrics = _evaluate_strategy(manual_class(), list(args.symbols), start_dt, end_dt, args.binning)
        report["manual_baselines"].append(
            {
                "strategy": manual_class.__name__,
                "metrics": metrics,
                "score": list(_score_metrics(metrics)),
            }
        )
        print(
            f"  {manual_class.__name__}: final=${metrics.get('final_value', 0.0):,.2f}, "
            f"trades={metrics.get('total_trades', 0)}"
        )

    print("\nTraining automated strategies")
    for strategy_class in TRAINING_PENGUINS:
        print(f"\nOptimizing {strategy_class.__name__}")
        result = train_strategy(
            strategy_class=strategy_class,
            symbols=list(args.symbols),
            start_dt=start_dt,
            end_dt=end_dt,
            binning=args.binning,
            trials=args.trials,
            seed=args.seed,
        )
        report["trained_strategies"].append(result)
        print(
            f"Best {strategy_class.__name__}: final=${result['best_metrics'].get('final_value', 0.0):,.2f}, "
            f"trades={result['best_metrics'].get('total_trades', 0)}"
        )

    report_path = output_dir / f"trainable_penguins_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, default=str)

    print(f"\nSaved training report to {report_path}")


if __name__ == "__main__":
    main()