from __future__ import annotations

import inspect
from typing import Any, List, Optional

from backtest.portfolio import Portfolio


def rsi(prices: List[float], period: int) -> float:
    if len(prices) < period + 1:
        return 50.0
    gain_sum = 0.0
    loss_sum = 0.0
    for index in range(len(prices) - period, len(prices)):
        delta = prices[index] - prices[index - 1]
        if delta > 0:
            gain_sum += delta
        elif delta < 0:
            loss_sum -= delta
    if loss_sum == 0:
        return 100.0
    return 100.0 - (100.0 / (1.0 + gain_sum / loss_sum))


def trend_quality(prices: List[float]) -> float:
    sma_10 = sum(prices[-10:]) / 10
    sma_30 = sum(prices[-30:]) / 30
    sma_60 = sum(prices[-60:]) / 60
    score = 0.0
    if sma_10 > sma_30:
        score += 0.35
    if sma_30 > sma_60:
        score += 0.35
    if prices[-1] > sma_30:
        score += 0.20
    if prices[-1] > prices[-5]:
        score += 0.10
    return min(score, 1.0)


def bollinger_bands(
    prices: List[float], period: int, num_std: float
) -> tuple[float, float, float]:
    recent = prices[-period:]
    middle = sum(recent) / period
    variance = sum((price - middle) ** 2 for price in recent) / period
    std_dev = variance ** 0.5
    return middle + num_std * std_dev, middle, middle - num_std * std_dev


def adx_proxy(prices: List[float], period: int) -> float:
    if len(prices) < period + 1:
        return 0.0
    directional_up = 0.0
    directional_down = 0.0
    true_range = 0.0
    for index in range(len(prices) - period, len(prices)):
        change = prices[index] - prices[index - 1]
        true_range += abs(change)
        if change > 0:
            directional_up += change
        elif change < 0:
            directional_down -= change
    if true_range <= 0:
        return 0.0
    return 100.0 * abs(directional_up - directional_down) / true_range


def relative_strength(
    prices: List[float],
    spy_prices: Optional[List[float]] = None,
    period: int = 20,
) -> float:
    if not prices or period <= 0 or len(prices) <= period:
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
    return stock_return - (spy_current / spy_past - 1.0)


def relative_volume(volumes: Optional[List[float]] = None, period: int = 20) -> float:
    if not volumes or period <= 0 or len(volumes) <= period:
        return 0.0
    current_volume = volumes[-1]
    if current_volume <= 0:
        return 0.0
    recent_volumes = volumes[-period - 1 :]
    average_volume = sum(recent_volumes) / len(recent_volumes)
    if average_volume <= 0:
        return 0.0
    return current_volume / average_volume


def call_penguin_decide(
    penguin: Any,
    symbol: str,
    mid_prices: List[float],
    bid: float,
    ask: float,
    portfolio: Portfolio,
    spy_prices: Optional[List[float]] = None,
    volumes: Optional[List[float]] = None,
) -> tuple[str, int]:
    """Call a penguin's decide method while remaining compatible with both legacy and context-aware signatures."""
    try:
        signature = inspect.signature(penguin.decide)
    except (TypeError, ValueError):
        signature = None

    if signature is not None:
        parameters = list(signature.parameters.values())
        has_spy_and_volumes = any(
            parameter.name in {"spy_prices", "volumes"} for parameter in parameters
        )
        if has_spy_and_volumes:
            return penguin.decide(
                symbol,
                mid_prices,
                bid,
                ask,
                portfolio,
                spy_prices=spy_prices,
                volumes=volumes,
            )

    return penguin.decide(symbol, mid_prices, bid, ask, portfolio)
