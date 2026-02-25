"""Statistical indicators: SMA, EMA, etc."""
from typing import List


def sma(prices: List[float], period: int) -> float:
    """Calculate Simple Moving Average."""
    if len(prices) < period:
        return 0
    return sum(prices[-period:]) / period


def ema(prices: List[float], period: int) -> float:
    """Calculate Exponential Moving Average (simplified)."""
    if len(prices) < period:
        return 0
    
    alpha = 2 / (period + 1)
    ema_val = prices[0]
    
    for price in prices[1:]:
        ema_val = alpha * price + (1 - alpha) * ema_val
    
    return ema_val
