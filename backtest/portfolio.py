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
        # Prevent selling at $0 (data retrieval error)
        if price <= 0:
            return False

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
            if s in prices and prices[s] > 0:
                v += p.qty * prices[s]
            elif s not in prices or prices[s] <= 0:
                # If price is missing or invalid, use avg purchase price as fallback
                v += p.qty * p.avg_price
        return v

    def get_position(self, symbol: str) -> int:
        """Return the quantity held for the given symbol."""
        if symbol in self.positions:
            return self.positions[symbol].qty
        return 0

    def get_symbol_summary(self, prices: Dict[str, float] | None = None):
        """Return summary of trades per symbol, including current position info."""
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

        # Ensure symbols with open positions are included
        for symbol in self.positions:
            if symbol not in summary:
                summary[symbol] = {
                    "buy_count": 0,
                    "sell_count": 0,
                    "total_qty_bought": 0,
                    "total_qty_sold": 0,
                    "total_cost": 0,
                    "total_revenue": 0,
                }

        # Calculate PnL for each symbol (realized + unrealized)
        for symbol in summary:
            cost = summary[symbol]["total_cost"]
            revenue = summary[symbol]["total_revenue"]
            realized_pnl = revenue - cost

            pos = self.positions.get(symbol)
            position_qty = pos.qty if pos else 0
            position_avg_price = pos.avg_price if pos else 0.0
            market_price = prices.get(symbol) if prices and symbol in prices else None
            market_value = (
                position_qty * market_price if market_price is not None else 0.0
            )
            unrealized_pnl = (
                (market_price - position_avg_price) * position_qty
                if market_price is not None
                else 0.0
            )
            total_pnl = realized_pnl + unrealized_pnl
            total_pnl_pct = (total_pnl / cost * 100) if cost > 0 else 0

            summary[symbol]["realized_pnl"] = realized_pnl
            summary[symbol]["unrealized_pnl"] = unrealized_pnl
            summary[symbol]["total_pnl"] = total_pnl
            summary[symbol]["pnl_pct"] = total_pnl_pct
            summary[symbol]["position_qty"] = position_qty
            summary[symbol]["market_value"] = market_value
            summary[symbol]["market_price"] = market_price

        return summary
