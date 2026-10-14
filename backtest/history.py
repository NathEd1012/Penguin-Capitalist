"""Shared history and warmup calculations for backtests and training."""
from typing import List


def penguin_history_requirements(penguin) -> tuple[int, int]:
    """Return (visible history window, minimum history before trading)."""
    try:
        lookback_bars = int(getattr(penguin, "LOOKBACK_BARS", 1000))
    except (TypeError, ValueError):
        lookback_bars = 1000

    try:
        min_history_required = int(getattr(penguin, "MIN_HISTORY_REQUIRED", 0))
    except (TypeError, ValueError):
        min_history_required = 0

    lookback_bars = max(1, lookback_bars)
    min_history_required = max(0, min_history_required)

    parameters = getattr(penguin, "params", None)
    if parameters is not None:
        period_values = [
            int(value)
            for name, value in vars(parameters).items()
            if name.endswith("_period") and isinstance(value, (int, float))
        ]
        if period_values:
            min_history_required = max(min_history_required, max(period_values) + 2)

    return max(lookback_bars, min_history_required), max(lookback_bars, min_history_required)


def binning_to_minutes(binning: str) -> int:
    mapping = {
        "1m": 1,
        "5m": 5,
        "15m": 15,
        "1h": 60,
        "1d": 1440,
    }
    try:
        return mapping[binning.strip().lower()]
    except KeyError as exc:
        raise ValueError(f"Unsupported binning: {binning}") from exc


def history_warmup_bars(penguin_classes: List, max_period: int = 0) -> int:
    max_period = max(0, int(max_period))
    return max(
        (
            max(
                penguin_history_requirements(penguin_class)[1],
                max_period + 2
                if max_period and not hasattr(penguin_class, "params")
                else 0,
            )
            for penguin_class in penguin_classes
        ),
        default=0,
    )
