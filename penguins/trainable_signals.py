from collections.abc import Sequence


def is_volume_explosion(
    volumes: Sequence[float],
    lookback: int,
    multiplier: float,
) -> bool:
    """Return whether current volume is a multiple of prior average volume."""
    if lookback <= 0 or multiplier <= 0 or len(volumes) < lookback + 1:
        return False

    current_volume = float(volumes[-1])
    previous_volumes = [float(value) for value in volumes[-lookback - 1 : -1]]
    average_volume = sum(previous_volumes) / lookback
    return average_volume > 0 and current_volume >= average_volume * multiplier


def average_relative_strength_return(
    stock_prices: Sequence[float],
    benchmark_prices: Sequence[float],
    lookback: int,
) -> float | None:
    """Average tick return of Stock/SPY over the latest aligned observations."""
    if lookback <= 0:
        return None

    observations = min(len(stock_prices), len(benchmark_prices), lookback + 1)
    if observations < lookback + 1:
        return None

    stock_window = stock_prices[-observations:]
    benchmark_window = benchmark_prices[-observations:]
    relative_returns = []

    for index in range(1, observations):
        stock_previous = float(stock_window[index - 1])
        stock_current = float(stock_window[index])
        benchmark_previous = float(benchmark_window[index - 1])
        benchmark_current = float(benchmark_window[index])
        if min(stock_previous, stock_current, benchmark_previous, benchmark_current) <= 0:
            return None

        previous_ratio = stock_previous / benchmark_previous
        current_ratio = stock_current / benchmark_current
        relative_returns.append((current_ratio / previous_ratio) - 1.0)

    return sum(relative_returns) / len(relative_returns)
