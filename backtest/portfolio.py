"""Portfolio management for backtesting."""
from typing import Dict, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Trade:
    """Represents a single trade."""
    symbol: str
    action: str  # BUY or SELL
    quantity: int
    price: float
    timestamp: datetime
    
    def __str__(self):
        return f"{self.action} {self.quantity} {self.symbol} @ ${self.price:.2f} at {self.timestamp}"


class Portfolio:
    """Tracks positions, cash, and performance during backtesting."""
    
    def __init__(self, initial_capital: float = 5000.0, transaction_cost: float = 0.0):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.transaction_cost = transaction_cost
        
        # Positions: symbol -> quantity
        self.positions: Dict[str, int] = {}
        
        # Track the cost basis for each position for P&L calculation
        self.cost_basis: Dict[str, float] = {}
        
        # Trade history
        self.trades: List[Trade] = []
        
        # Value snapshots for curve tracking
        self.value_history: List[float] = []
        
    def get_position(self, symbol: str) -> int:
        """Get current quantity of a symbol."""
        return self.positions.get(symbol, 0)
    
    def get_total_value(self, current_prices: Dict[str, float]) -> float:
        """Calculate total portfolio value (cash + positions at current prices)."""
        total = self.cash
        for symbol, quantity in self.positions.items():
            if quantity > 0 and symbol in current_prices:
                total += quantity * current_prices[symbol]
        return total
    
    def buy(self, symbol: str, quantity: int, price: float, timestamp: datetime) -> bool:
        """
        Execute a buy order.
        Returns True if successful, False if insufficient cash.
        """
        cost = quantity * price + self.transaction_cost
        
        if cost > self.cash:
            return False
        
        self.cash -= cost
        self.positions[symbol] = self.positions.get(symbol, 0) + quantity
        
        # Update cost basis (weighted average)
        old_quantity = self.positions.get(symbol, quantity) - quantity
        old_cost = self.cost_basis.get(symbol, 0)
        
        if old_quantity > 0:
            new_cost_basis = (old_cost * old_quantity + price * quantity) / (old_quantity + quantity)
        else:
            new_cost_basis = price
        
        self.cost_basis[symbol] = new_cost_basis
        
        trade = Trade(
            symbol=symbol,
            action="BUY",
            quantity=quantity,
            price=price,
            timestamp=timestamp
        )
        self.trades.append(trade)
        
        return True
    
    def sell(self, symbol: str, quantity: int, price: float, timestamp: datetime) -> bool:
        """
        Execute a sell order.
        Returns True if successful, False if insufficient position.
        """
        current_qty = self.get_position(symbol)
        
        if quantity > current_qty:
            return False
        
        proceeds = quantity * price - self.transaction_cost
        self.cash += proceeds
        self.positions[symbol] -= quantity
        
        if self.positions[symbol] == 0:
            del self.positions[symbol]
        
        trade = Trade(
            symbol=symbol,
            action="SELL",
            quantity=quantity,
            price=price,
            timestamp=timestamp
        )
        self.trades.append(trade)
        
        return True
    
    def sell_all(self, current_prices: Dict[str, float], timestamp: datetime):
        """Sell all positions at current prices."""
        symbols_to_sell = list(self.positions.keys())
        
        for symbol in symbols_to_sell:
            quantity = self.get_position(symbol)
            if quantity > 0 and symbol in current_prices:
                self.sell(symbol, quantity, current_prices[symbol], timestamp)
    
    def add_value_snapshot(self, value: float):
        """Record a portfolio value snapshot."""
        self.value_history.append(value)
    
    def get_pnl(self, current_prices: Dict[str, float]) -> Tuple[float, float]:
        """
        Calculate current P&L.
        Returns: (absolute_pnl, percentage_pnl)
        """
        total_value = self.get_total_value(current_prices)
        absolute_pnl = total_value - self.initial_capital
        percentage_pnl = (absolute_pnl / self.initial_capital) * 100 if self.initial_capital > 0 else 0
        
        return absolute_pnl, percentage_pnl
    
    def get_trade_count(self) -> int:
        """Get total number of trades executed."""
        return len(self.trades)
