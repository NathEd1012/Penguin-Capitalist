import numpy as np


def sma(prices, n=10):
    if len(prices) < n:
        return prices[-1] if prices else 0
    return np.mean(prices[-n:])


def ema(prices, n=10):
    """Exponential Moving Average"""
    if len(prices) < n:
        return prices[-1] if prices else 0
    
    # Simple EMA calculation
    weights = np.exp(np.linspace(-1., 0., n))
    weights /= weights.sum()
    
    return np.convolve(prices[-n:], weights, mode='valid')[0] if len(prices) >= n else prices[-1]


def zscore(prices, n=20):
    if len(prices) < n:
        return 0
    mean = np.mean(prices[-n:])
    std = np.std(prices[-n:])
    return (prices[-1] - mean) / std if std > 0 else 0
