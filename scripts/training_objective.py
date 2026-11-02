"""Shared, deterministic scoring for training and validation candidates."""

ACTIVITY_PENALTY_CAPITAL_MULTIPLIER = 1.5


def training_profit_amount(candidate_metrics, benchmark_metrics, relative_to) -> float:
    """Return profit before activity and transaction-cost penalties."""
    profit = float(candidate_metrics.get("total_return", 0.0))
    if relative_to not in (0, "0", None, False):
        profit -= float(benchmark_metrics.get("total_return", 0.0))
    return profit


def activity_penalty(buy_trades: int, initial_capital: float, minimum_buys: int) -> float:
    """Penalize missing buys linearly, up to 1.5 times starting capital."""
    if minimum_buys < 1:
        raise ValueError("minimum_buys must be positive")
    shortfall = max(0, minimum_buys - max(0, buy_trades))
    return ACTIVITY_PENALTY_CAPITAL_MULTIPLIER * float(initial_capital) * shortfall / minimum_buys


def score_training_candidate(
    candidate_metrics,
    benchmark_metrics,
    transaction_cost: float,
    relative_to,
    initial_capital: float,
    *,
    minimum_buys: int,
) -> tuple[float, int, int]:
    buy_trades = int(candidate_metrics.get("buy_trades", candidate_metrics.get("total_trades", 0)))
    profit = training_profit_amount(candidate_metrics, benchmark_metrics, relative_to)
    penalty = activity_penalty(buy_trades, initial_capital, minimum_buys)
    return (
        profit - buy_trades * transaction_cost - penalty,
        -buy_trades,
        -int(candidate_metrics.get("total_trades", 0)),
    )
