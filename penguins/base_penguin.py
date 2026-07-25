from abc import ABC, abstractmethod
from typing import List, Optional
from backtest.portfolio import Portfolio


class BasePenguin(ABC):
    """Base class for all trading strategies."""
    # Default lookback window: can be overridden by subclasses
    LOOKBACK_BARS = 1000
    TRAINABLE = False

    def __init__(self, name: str):
        self.name = self.__class__.__name__

    @abstractmethod
    def decide(
        self,
        symbol: str,
        mid_prices: List[float],
        bid: float,
        ask: float,
        portfolio: Portfolio,
        spy_prices: Optional[List[float]] = None,
        volumes: Optional[List[float]] = None,
    ) -> tuple[str, int]:
        """
        Make trading decision based on mid-price history and current bid/ask.

        Args:
            symbol: Stock symbol
            mid_prices: Historical mid-prices for analysis
            bid: Current bid price (sell at this)
            ask: Current ask price (buy at this)
            portfolio: Current portfolio

        Returns:
            (BUY | SELL | HOLD, quantity)
        """
