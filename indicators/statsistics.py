import numpy as np


def zscore(prices, n=20):
    if len(prices) < n:
        return 0
    mean = np.mean(prices[-n:])
    std = np.std(prices[-n:])
    return (prices[-1] - mean) / std if std > 0 else 0
