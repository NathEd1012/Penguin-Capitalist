from dataclasses import dataclass, field
from typing import Dict


@dataclass
class Position:
    qty: int
    avg_price: float


@dataclass
class Portfolio:
    cash: float = 5000.0
    fee_per_trade: float = 1.0
    positions: Dict[str, Position] = field(default_factory=dict)
    trades: int = 0

    def buy(self, symbol: str, price: float, qty: int):
        cost = price * qty + self.fee_per_trade
        if cost > self.cash:
            return False

        self.cash -= cost
        self.trades += 1

        if symbol in self.positions:
            pos = self.positions[symbol]
            total_qty = pos.qty + qty
            pos.avg_price = (pos.avg_price * pos.qty + price * qty) / total_qty
            pos.qty = total_qty
        else:
            self.positions[symbol] = Position(qty, price)

        return True

    def sell(self, symbol: str, price: float, qty: int):
        if symbol not in self.positions:
            return False

        pos = self.positions[symbol]
        qty = min(qty, pos.qty)

        self.cash += price * qty - self.fee_per_trade
        self.trades += 1
        pos.qty -= qty

        if pos.qty == 0:
            del self.positions[symbol]

        return True

    def value(self, prices: Dict[str, float]) -> float:
        v = self.cash
        for s, p in self.positions.items():
            if s in prices:
                v += p.qty * prices[s]
        return v
