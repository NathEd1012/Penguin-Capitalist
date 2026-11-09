from abc import ABC, abstractmethod
from typing import List, Optional
from backtest.portfolio import Portfolio


class BasePenguin(ABC):
    """Base class for all trading strategies."""
    # Default lookback window: can be overridden by subclasses
    LOOKBACK_BARS = 1000
    # None infers parameter periods or LOOKBACK_BARS; () declares no indicators.
    COVERAGE_WINDOWS = None
    COVERAGE_FIXED_WINDOWS = ()
    def __init__(self, name: str):
        self.name = self.__class__.__name__

    @abstractmethod
    def decide(
        self,
        symbol: str,
        mid_prices: List[float],
        low_price: float,
        high_price: float,
        portfolio: Portfolio,
        spy_prices: Optional[List[float]] = None,
        volumes: Optional[List[float]] = None,
    ) -> tuple[str, int]:
        """
        Make a trading decision and size buys using the completed candle's high.

        Execution uses a separate synthetic bid/ask quote on the execution bar.
        Batch strategies receive the same (low, high) decision-price pairs.

        Args:
            symbol: Stock symbol
            mid_prices: Historical mid-prices for analysis
            low_price: Current completed candle's low price
            high_price: Current completed candle's high, used for buy sizing
            portfolio: Current portfolio

        Returns:
            (BUY | SELL | HOLD, quantity)
        """
