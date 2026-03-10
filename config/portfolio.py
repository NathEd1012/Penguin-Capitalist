"""Portfolio configuration settings for backtesting."""

# ========== PORTFOLIO CAPITAL ==========
# Initial capital to start backtesting with (USD)
INITIAL_CAPITAL = 7000.0

# ========== TRANSACTION COSTS ==========
# Fixed transaction cost per trade (USD)
# Set to 0 for commission-free trading simulation
# Typical values: 0 (Robinhood/Webull), 1-5 (traditional brokers)
TRANSACTION_COST = 0

__all__ = [
    "INITIAL_CAPITAL",
    "TRANSACTION_COST",
]
