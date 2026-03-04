"""
Integration guide and examples for SyntheticSpreadModel.

This module demonstrates how to integrate the spread model into different parts
of the backtesting infrastructure.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtest.synthetic_spread_model import SyntheticSpreadModel
from datetime import datetime
import pytz


# ============================================================================
# EXAMPLE 1: Basic Usage - Single Candle
# ============================================================================

def example_basic_usage():
    """Simple example of calculating bid/ask for a single candle."""
    
    model = SyntheticSpreadModel()
    
    bid, ask, spread = model.get_bid_ask(
        mid_price=150.50,
        high=151.25,
        low=150.10,
        timestamp="2026-01-20T16:00:00Z"
    )
    
    print(f"Bid: ${bid:.4f}, Ask: ${ask:.4f}, Spread: ${spread:.4f}")


# ============================================================================
# EXAMPLE 2: Integration with Penguin Strategy
# ============================================================================

def example_penguin_integration():
    """
    How to use spread model in a penguin strategy's decide() method.
    """
    
    model = SyntheticSpreadModel()
    
    # Simulate a strategy decision with realistic execution prices
    def strategy_decide(symbol, mid_prices, candle_high, candle_low, 
                       timestamp, portfolio):
        """Example strategy decide method using spread model."""
        
        mid_price = mid_prices[-1]
        
        # Calculate realistic bid/ask
        bid, ask, spread = model.get_bid_ask(
            mid_price=mid_price,
            high=candle_high,
            low=candle_low,
            timestamp=timestamp
        )
        
        # Use ask price for BUY orders, bid price for SELL orders
        if should_buy(mid_prices):
            if portfolio.cash >= ask:  # Use ask instead of mid_price
                return "BUY", 1
        
        elif should_sell(portfolio, symbol):
            qty = portfolio.positions[symbol].qty
            # Entry price should be recorded at ask, exit at bid
            return "SELL", qty
        
        return "HOLD", 0
    
    def should_buy(prices):
        """Placeholder buy signal logic."""
        return True
    
    def should_sell(portfolio, symbol):
        """Placeholder sell signal logic."""
        return False


# ============================================================================
# EXAMPLE 3: Integration with Backtest Engine
# ============================================================================

def example_backtest_integration():
    """
    How to integrate spread model into the main backtest loop.
    Typically used in backtest/evaluator.py or scripts/backtest_runner.py
    """
    
    model = SyntheticSpreadModel(
        market_open_time="14:30",      # 9:30 AM ET
        market_close_time="20:00",     # 4:00 PM ET
        opening_period_minutes=15,      # First 15 min: 1.5x spread
        closing_period_minutes=15,      # Last 15 min: 1.2x spread
    )
    
    # In your backtest main loop:
    # for bar_index, timestamp in enumerate(sorted_timestamps):
    #     for symbol in active_symbols:
    #         prices = prices_by_symbol[symbol]
    #         candle = ohlcv[symbol][bar_index]
    #         
    #         # Get realistic bid/ask
    #         bid, ask, spread = model.get_bid_ask(
    #             mid_price=candle['close'],
    #             high=candle['high'],
    #             low=candle['low'],
    #             timestamp=timestamp
    #         )
    #         
    #         # Pass to strategy with realistic prices
    #         action, qty = strategy.decide(
    #             symbol, prices, bid, ask, portfolio, timestamp
    #         )
    #         
    #         # Execute at realistic prices
    #         if action == "BUY":
    #             portfolio.execute_buy(symbol, qty, ask, timestamp)
    #         elif action == "SELL":
    #             portfolio.execute_sell(symbol, qty, bid, timestamp)


# ============================================================================
# EXAMPLE 4: Analyzing Spread Impact on Returns
# ============================================================================

def example_spread_impact_analysis():
    """
    Demonstrates how to measure the cost of spreads on strategy returns.
    """
    
    model = SyntheticSpreadModel()
    
    mid_price = 150.50
    high = 151.25
    low = 150.10
    timestamp = "2026-01-20T16:00:00Z"
    
    bid, ask, spread = model.get_bid_ask(mid_price, high, low, timestamp)
    
    # Calculate spread cost as percentage of capital
    capital = 5000.0
    entry_price = ask
    exit_price = bid
    
    shares = capital / entry_price
    spread_cost = shares * (entry_price - exit_price)
    spread_cost_pct = (spread_cost / capital) * 100
    
    print(f"Entry at ask:  ${entry_price:.4f}")
    print(f"Exit at bid:   ${exit_price:.4f}")
    print(f"Spread cost:   ${spread_cost:.2f} ({spread_cost_pct:.4f}%)")
    print(f"Equivalent to: {-spread_cost_pct:.4f}% annual drag if 365 round trips/year")


# ============================================================================
# EXAMPLE 5: Custom Configuration for Different Market Conditions
# ============================================================================

def example_custom_configurations():
    """
    Different spread configurations for different trading scenarios.
    """
    
    # Conservative (wide spreads - like real markets)
    conservative = SyntheticSpreadModel(
        base_price_factor=0.0005,      # 0.05% of price
        volatility_factor=0.10,         # 10% of range
        opening_spread_multiplier=2.0,
        closing_spread_multiplier=1.5,
    )
    
    # Aggressive (tight spreads - like ECNs)
    aggressive = SyntheticSpreadModel(
        base_price_factor=0.00005,     # 0.005% of price
        volatility_factor=0.01,         # 1% of range
        opening_spread_multiplier=1.2,
        closing_spread_multiplier=1.1,
    )
    
    # Test both
    test_params = {
        'mid_price': 150.50,
        'high': 151.25,
        'low': 150.10,
        'timestamp': '2026-01-20T16:00:00Z'
    }
    
    _, _, conservative_spread = conservative.get_bid_ask(**test_params)
    _, _, aggressive_spread = aggressive.get_bid_ask(**test_params)
    
    print(f"Conservative: ${conservative_spread:.4f}")
    print(f"Aggressive:   ${aggressive_spread:.4f}")
    print(f"Ratio:        {conservative_spread/aggressive_spread:.2f}x")


# ============================================================================
# EXAMPLE 6: Compatibility with Different Timestamp Formats
# ============================================================================

def example_timestamp_formats():
    """
    Spread model handles multiple timestamp formats automatically.
    """
    
    model = SyntheticSpreadModel()
    
    # ISO string with Z
    bid1, ask1, _ = model.get_bid_ask(
        mid_price=150.50, high=151.25, low=150.10,
        timestamp="2026-01-20T16:00:00Z"
    )
    
    # ISO string with offset
    bid2, ask2, _ = model.get_bid_ask(
        mid_price=150.50, high=151.25, low=150.10,
        timestamp="2026-01-20T16:00:00+00:00"
    )
    
    # Python datetime object
    dt = datetime(2026, 1, 20, 16, 0, 0, tzinfo=pytz.UTC)
    bid3, ask3, _ = model.get_bid_ask(
        mid_price=150.50, high=151.25, low=150.10,
        timestamp=dt
    )
    
    assert bid1 == bid2 == bid3
    print("✓ All timestamp formats produce identical results")


if __name__ == "__main__":
    print("=" * 70)
    print("SYNTHETIC SPREAD MODEL - INTEGRATION EXAMPLES")
    print("=" * 70)
    print()
    
    print("Example 1: Basic Usage")
    example_basic_usage()
    print()
    
    print("Example 2: Penguin Integration (see code)")
    print()
    
    print("Example 3: Backtest Engine Integration (see code)")
    print()
    
    print("Example 4: Spread Impact Analysis")
    example_spread_impact_analysis()
    print()
    
    print("Example 5: Custom Configurations")
    example_custom_configurations()
    print()
    
    print("Example 6: Timestamp Format Compatibility")
    example_timestamp_formats()
    print()
