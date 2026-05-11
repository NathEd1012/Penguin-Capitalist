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
    """
    Tracks positions, cash, and performance during backtesting.
    
    **SYMBOL-SPECIFIC PRICE TRACKING:**
    All price tracking is indexed by symbol to ensure multi-asset correctness.
    - positions[symbol]: quantity held
    - cost_basis[symbol]: average entry price
    - last_known_prices[symbol]: last known price for this symbol
    Never use a global/shared previous_price variable.
    """
    
    def __init__(self, initial_capital: float = 5000.0, transaction_cost: float = 0.0):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.transaction_cost = transaction_cost
        self.max_leverage = 1.0
        
        # Positions: symbol -> quantity (last_price_by_symbol equivalent)
        self.positions: Dict[str, int] = {}
        
        # Track the cost basis for each position for P&L calculation
        # symbol -> average entry price (previous_close_by_symbol for cost tracking)
        self.cost_basis: Dict[str, float] = {}
        
        # Track last known good price for each symbol (fallback if price data missing)
        # symbol -> price (previous_close_by_symbol: price_history[symbol])
        self.last_known_prices: Dict[str, float] = {}
        
        # Trade history
        self.trades: List[Trade] = []

        # Cached trade counts for fast reporting
        self.buy_trade_count = 0
        self.sell_trade_count = 0
        
        # Value snapshots for curve tracking
        self.value_history: List[float] = []
        
    def get_position(self, symbol: str) -> int:
        """Get current quantity of a symbol."""
        return self.positions.get(symbol, 0)
    
    def get_total_value(self, current_prices: Dict[str, float]) -> float:
        """
        Calculate total portfolio value (cash + positions at current prices).
        Uses last-known-good price if current price is not available to prevent
        artificial drops when price data is missing.
        
        SYMBOL-SPECIFIC PRICE TRACKING (previous_close_by_symbol):
        - current_prices[symbol]: latest price for this symbol
        - self.last_known_prices[symbol]: fallback price for this symbol
        - Never uses a global/shared previous_price
        
        Args:
            current_prices: Dict of current symbol prices {symbol: price}
        
        Returns:
            Total portfolio value
        """
        total = self.cash
        for symbol, quantity in self.positions.items():
            if quantity > 0:
                # Use current price if available, otherwise fall back to last known price for THIS symbol
                if symbol in current_prices and current_prices[symbol] > 0:
                    price = current_prices[symbol]
                    self.last_known_prices[symbol] = price  # Update last known price
                elif symbol in self.last_known_prices and self.last_known_prices[symbol] > 0:
                    # Use previous price for this symbol (carry forward)
                    price = self.last_known_prices[symbol]
                else:
                    # No price available at all, skip this position
                    continue
                
                total += quantity * price
        
        return total
    
    def buy(self, symbol: str, quantity: int, price: float, timestamp: datetime) -> bool:
        """
        Execute a buy order.
        
        SYMBOL-SPECIFIC PRICE TRACKING (last_price_by_symbol):
        - Updates last_known_prices[symbol] for this specific symbol
        - Tracks cost_basis[symbol] for this symbol's positions
        
        Args:
            symbol: The symbol being bought
            quantity: Quantity to buy
            price: Price per share for THIS symbol
            timestamp: Trade timestamp
        
        Returns:
            True if successful, False if insufficient cash.
        """
        if quantity <= 0 or price <= 0:
            return False

        cost = quantity * price + self.transaction_cost

        if self.max_leverage <= 1.0:
            if cost > self.cash:
                return False
        else:
            # With leverage enabled, allow negative cash as long as gross exposure
            # stays within equity * max_leverage after the trade.
            current_position_value = 0.0
            for pos_symbol, pos_qty in self.positions.items():
                if pos_qty <= 0:
                    continue
                if pos_symbol == symbol:
                    pos_price = price
                else:
                    pos_price = self.last_known_prices.get(pos_symbol, 0.0)
                if pos_price > 0:
                    current_position_value += pos_qty * pos_price

            new_cash = self.cash - cost
            new_position_value = current_position_value + quantity * price
            new_equity = new_cash + new_position_value
            max_allowed_exposure = max(0.0, new_equity) * self.max_leverage

            if new_position_value > max_allowed_exposure:
                return False
        
        self.cash -= cost
        self.positions[symbol] = self.positions.get(symbol, 0) + quantity
        
        # Track last known price for fallback valuation
        if price > 0:
            self.last_known_prices[symbol] = price
        
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
        self.buy_trade_count += 1
        
        return True
    
    def sell(self, symbol: str, quantity: int, price: float, timestamp: datetime) -> bool:
        """
        Execute a sell order.
        
        SYMBOL-SPECIFIC PRICE TRACKING (last_price_by_symbol):
        - Updates last_known_prices[symbol] for this specific symbol
        - Closes position[symbol] tracking
        
        Args:
            symbol: The symbol being sold
            quantity: Quantity to sell
            price: Price per share for THIS symbol
            timestamp: Trade timestamp
        
        Returns:
            True if successful, False if insufficient position.
        """
        current_qty = self.get_position(symbol)
        
        if quantity > current_qty:
            return False
        
        # Track last known price for fallback valuation
        if price > 0:
            self.last_known_prices[symbol] = price
        
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
        self.sell_trade_count += 1
        
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
    
    def get_symbol_summary(self, prices: Dict[str, float] = None) -> Dict:
        """
        Return summary of trades per symbol, including current position info.
        
        Args:
            prices: Dict of current market prices for each symbol
        
        Returns:
            Dict with per-symbol trade and position statistics
        """
        if prices is None:
            prices = {}
        
        summary = {}
        
        # Process all trades
        for trade in self.trades:
            symbol = trade.symbol
            if symbol not in summary:
                summary[symbol] = {
                    "buy_count": 0,
                    "sell_count": 0,
                    "total_qty_bought": 0,
                    "total_qty_sold": 0,
                    "total_cost": 0,  # Total spent on buys
                    "total_revenue": 0,  # Total received from sells
                }
            
            if trade.action == "BUY":
                summary[symbol]["buy_count"] += 1
                summary[symbol]["total_qty_bought"] += trade.quantity
                summary[symbol]["total_cost"] += trade.quantity * trade.price + self.transaction_cost
            else:  # SELL
                summary[symbol]["sell_count"] += 1
                summary[symbol]["total_qty_sold"] += trade.quantity
                summary[symbol]["total_revenue"] += trade.quantity * trade.price - self.transaction_cost
        
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
        
        # Calculate P&L for each symbol
        for symbol in summary:
            cost = summary[symbol]["total_cost"]
            revenue = summary[symbol]["total_revenue"]
            realized_pnl = revenue - cost
            
            position_qty = self.positions.get(symbol, 0)
            cost_basis_price = self.cost_basis.get(symbol, 0.0)
            market_price = prices.get(symbol) if symbol in prices else None
            market_value = position_qty * market_price if market_price is not None else 0.0
            unrealized_pnl = (market_price - cost_basis_price) * position_qty if market_price is not None and cost_basis_price > 0 else 0.0
            
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

