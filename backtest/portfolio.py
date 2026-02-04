from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Trade:
    """Record of a single buy/sell transaction."""

    symbol: str
    side: str  # "BUY" or "SELL"
    qty: int
    price: float
    fee: float


@dataclass
class Position:
    qty: int
    avg_price: float


@dataclass
class Portfolio:
    cash: float = 5000.0
    fee_per_trade: float = 1.0
    enable_fees: bool = True
    positions: Dict[str, Position] = field(default_factory=dict)
    trades: int = 0
    trade_history: List[Trade] = field(default_factory=list)  # Track all trades

    def buy(self, symbol: str, price: float, qty: int):
        # Prevent buying at $0 (data retrieval error)
        if price <= 0:
            return False

        fee = self.fee_per_trade if self.enable_fees else 0.0
        cost = price * qty + fee
        if cost > self.cash:
            return False

        self.cash -= cost
        self.trades += 1
        self.trade_history.append(Trade(symbol, "BUY", qty, price, fee))

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

        fee = self.fee_per_trade if self.enable_fees else 0.0
        self.cash += price * qty - fee
        self.trades += 1
        self.trade_history.append(Trade(symbol, "SELL", qty, price, fee))
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

    def get_position(self, symbol: str) -> int:
        """Return the quantity held for the given symbol."""
        if symbol in self.positions:
            return self.positions[symbol].qty
        return 0

    def get_symbol_summary(self):
        """Return summary of trades per symbol: {symbol: {buys, total_qty, pnl, etc}}."""
        summary = {}

        for trade in self.trade_history:
            symbol = trade.symbol
            if symbol not in summary:
                summary[symbol] = {
                    "buy_count": 0,
                    "sell_count": 0,
                    "total_qty_bought": 0,
                    "total_qty_sold": 0,
                    "total_cost": 0,  # Total spent on buys (including fees)
                    "total_revenue": 0,  # Total received from sells (minus fees)
                }

            if trade.side == "BUY":
                summary[symbol]["buy_count"] += 1
                summary[symbol]["total_qty_bought"] += trade.qty
                summary[symbol]["total_cost"] += trade.qty * trade.price + trade.fee
            else:  # SELL
                summary[symbol]["sell_count"] += 1
                summary[symbol]["total_qty_sold"] += trade.qty
                summary[symbol]["total_revenue"] += trade.qty * trade.price - trade.fee

        # Calculate PnL for each symbol
        for symbol in summary:
            cost = summary[symbol]["total_cost"]
            revenue = summary[symbol]["total_revenue"]
            pnl = revenue - cost
            summary[symbol]["pnl"] = pnl
            summary[symbol]["pnl_pct"] = (pnl / cost * 100) if cost > 0 else 0

        return summary
