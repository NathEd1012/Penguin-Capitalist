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
        prices: List[float],
        portfolio: Portfolio,
    ) -> str:
        """
        BUY | SELL | HOLD
        """
