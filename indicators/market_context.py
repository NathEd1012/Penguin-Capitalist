from typing import List, Optional


def relative_strength(
    prices: List[float],
    spy_prices: Optional[List[float]] = None,
    period: int = 20,
) -> float:
    """Return stock return minus SPY return over the configured lookback."""
    if not prices or period <= 0:
        return 0.0

    if len(prices) <= period:
        return 0.0

    current_price = prices[-1]
    past_price = prices[-period - 1]
    if current_price <= 0 or past_price <= 0:
        return 0.0

    stock_return = current_price / past_price - 1.0

    if spy_prices is None or len(spy_prices) <= period:
        return stock_return

    spy_current = spy_prices[-1]
    spy_past = spy_prices[-period - 1]
    if spy_current <= 0 or spy_past <= 0:
        return stock_return

    spy_return = spy_current / spy_past - 1.0
    return stock_return - spy_return


def relative_volume(
    volumes: Optional[List[float]] = None,
    period: int = 20,
) -> float:
    """Return current volume divided by the average volume over the last N bars."""
    if not volumes or period <= 0:
        return 0.0

    if len(volumes) <= period:
        return 0.0

    current_volume = volumes[-1]
    if current_volume <= 0:
        return 0.0

    recent_volumes = volumes[-period - 1 :]
    avg_volume = sum(recent_volumes) / len(recent_volumes)
    if avg_volume <= 0:
        return 0.0

    return current_volume / avg_volume
