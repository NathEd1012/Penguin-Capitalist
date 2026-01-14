import numpy as np


def roc(prices, n=5):
    if len(prices) < n + 1:
        return 0.0
    return (prices[-1] - prices[-n - 1]) / prices[-n - 1]


def rsi(prices, n=14):
    if len(prices) < n + 1:
        return 50

    deltas = np.diff(prices[-(n + 1) :])
    gains = deltas[deltas > 0].sum()
    losses = -deltas[deltas < 0].sum()

    if losses == 0:
        return 100
    rs = gains / losses
    return 100 - (100 / (1 + rs))
