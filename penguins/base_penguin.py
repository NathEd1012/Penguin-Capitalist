from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import List
from backtest.portfolio import Portfolio


class BasePenguin(ABC):
    """Base class for all trading strategies."""
    # Default lookback window: can be overridden by subclasses
    LOOKBACK_BARS = 1000
    
    def __init__(self, name: str):
        self.name = name
        self._market_price_history: Mapping[str, Sequence[float]] = {}
        self._market_volume_history: Mapping[str, Sequence[float]] = {}

    def set_market_context(
        self,
        price_history: Mapping[str, Sequence[float]],
        volume_history: Mapping[str, Sequence[float]],
    ) -> None:
        """Expose read-only cross-symbol price and volume histories to a strategy.

        The runners retain ownership of both mappings and update their lists in
        place on every bar. Strategies must treat this context as read-only.
        """
        self._market_price_history = price_history
        self._market_volume_history = volume_history

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
