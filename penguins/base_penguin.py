from abc import ABC, abstractmethod
from typing import List
from backtest.portfolio import Portfolio


class BasePenguin(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def decide(
        self,
        symbol: str,
        mid_prices: List[float],
        bid: float,
        ask: float,
        portfolio: Portfolio,
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
