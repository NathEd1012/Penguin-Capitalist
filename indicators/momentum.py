"""Momentum indicators: RSI, ROC."""
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


def rsi(prices: List[float], period: int = 14) -> float:
    """
    Calculate Relative Strength Index (RSI).
    
    Args:
        prices: List of prices
        period: RSI period (default 14)
    
    Returns:
        RSI value (0-100)
    """
    if len(prices) < period + 1:
        return 50  # Neutral

    gain_sum = 0.0
    loss_sum = 0.0
    start = len(prices) - period
    for i in range(start, len(prices)):
        delta = prices[i] - prices[i - 1]
        if delta > 0:
            gain_sum += delta
        elif delta < 0:
            loss_sum -= delta

    avg_gain = gain_sum / period
    avg_loss = loss_sum / period
    
    if avg_loss == 0:
        return 100 if avg_gain > 0 else 50
    
    rs = avg_gain / avg_loss
    rsi_val = 100 - (100 / (1 + rs))
    
    return rsi_val


def roc(prices: List[float], period: int) -> float:
    """
    Calculate Rate of Change (ROC).
    
    Args:
        prices: List of prices
        period: ROC period
    
    Returns:
        ROC as decimal (e.g., 0.05 for +5%)
    """
    if len(prices) < period + 1:
        return 0
    
    old_price = prices[-period-1]
    new_price = prices[-1]
    
    if old_price == 0:
        return 0
    
    return (new_price - old_price) / old_price


def atr(prices_high: List[float], prices_low: List[float], prices_close: List[float], period: int = 14) -> float:
    """
    Calculate Average True Range (ATR).
    
    Args:
        prices_high: List of high prices
        prices_low: List of low prices
        prices_close: List of close prices
        period: ATR period
    
    Returns:
        ATR value
    """
    if len(prices_close) < period:
        return 0
    
    trs = []
    for i in range(1, len(prices_close)):
        h_l = prices_high[i] - prices_low[i]
        h_c = abs(prices_high[i] - prices_close[i-1])
        l_c = abs(prices_low[i] - prices_close[i-1])
        tr = max(h_l, h_c, l_c)
        trs.append(tr)
    
    return sum(trs[-period:]) / period


def bolinger_bands(prices: List[float], period: int = 20, num_std: float = 2) -> tuple:
    """
    Calculate Bollinger Bands.
    
    Args:
        prices: List of prices
        period: MA period
        num_std: Number of standard deviations
    
    Returns:
        (upper_band, middle_band, lower_band)
    """
    if len(prices) < period:
        return 0, 0, 0
    
    mid = sma(prices, period)
    
    recent = prices[-period:]
    variance = sum((p - mid) ** 2 for p in recent) / period
    std_dev = variance ** 0.5
    
    upper = mid + num_std * std_dev
    lower = mid - num_std * std_dev
    
    return upper, mid, lower
