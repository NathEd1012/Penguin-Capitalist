"""Shared, deterministic scoring for training and validation candidates."""

import math
import os

# Set in run_ALLRUNS.sh; 0 disables the activity penalty.
ACTIVITY_PENALTY_CAPITAL_MULTIPLIER = float(os.getenv("ACTIVITY_PENALTY_CAPITAL_MULTIPLIER", "1.5"))
if not math.isfinite(ACTIVITY_PENALTY_CAPITAL_MULTIPLIER) or ACTIVITY_PENALTY_CAPITAL_MULTIPLIER < 0:
    raise ValueError("ACTIVITY_PENALTY_CAPITAL_MULTIPLIER must be finite and nonnegative")


def training_profit_amount(candidate_metrics, benchmark_metrics, relative_to) -> float:
    """Return net profit, optionally relative to the benchmark."""
    profit = float(candidate_metrics.get("total_return", 0.0))
    if relative_to not in (0, "0", None, False):
        profit -= float(benchmark_metrics.get("total_return", 0.0))
    return profit


def activity_penalty(buy_trades: int, initial_capital: float, minimum_buys: int) -> float:
    """Penalize missing buys linearly using the configured capital multiplier."""
    if minimum_buys < 0:
        raise ValueError("minimum_buys must be nonnegative")
    if minimum_buys == 0:
        return 0.0
    shortfall = max(0, minimum_buys - max(0, buy_trades))
    return ACTIVITY_PENALTY_CAPITAL_MULTIPLIER * float(initial_capital) * shortfall / minimum_buys


def score_training_candidate(
    candidate_metrics,
    benchmark_metrics,
    relative_to,
    initial_capital: float,
    *,
    minimum_buys: int,
) -> tuple[float, int, int]:
    buy_trades = int(candidate_metrics.get("buy_trades", candidate_metrics.get("total_trades", 0)))
    profit = training_profit_amount(candidate_metrics, benchmark_metrics, relative_to)
    penalty = activity_penalty(buy_trades, initial_capital, minimum_buys)
    # Execution fees are already included in the portfolios' net profits.
    return (
        profit - penalty,
        -buy_trades,
        -int(candidate_metrics.get("total_trades", 0)),
    )
