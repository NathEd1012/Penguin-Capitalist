import numpy as np


def sma(prices, n=10):
    if len(prices) < n:
        return prices[-1] if prices else 0
    return np.mean(prices[-n:])


def ema(prices, n=10):
    if len(prices) < n:
        return prices[-1] if prices else 0
    alpha = 2 / (n + 1)
    ema_val = prices[0]
    for price in prices[1:]:
        ema_val = alpha * price + (1 - alpha) * ema_val
    return ema_val


def zscore(prices, n=20):
    if len(prices) < n:
        return 0
    mean = np.mean(prices[-n:])
    std = np.std(prices[-n:])
    return (prices[-1] - mean) / std if std > 0 else 0
