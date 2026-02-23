"""Pricing utilities for the simulation."""


def synthetic_price_bar(symbol, price_history):
    """Generate synthetic price when Alpaca has no data - returns last known price."""
    if symbol not in price_history or not price_history[symbol]:
        return 100.0 + hash(symbol) % 50
    last = price_history[symbol][-1]
    # Ensure last price is valid
    if last <= 0:
        return 100.0 + hash(symbol) % 50
    # Return exact last price without any variance
    return last
