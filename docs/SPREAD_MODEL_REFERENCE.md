"""
Synthetic Spread Model - Documentation and Reference

Overview
========
The SyntheticSpreadModel generates realistic bid/ask spreads for historical
OHLCV backtesting when actual bid/ask data is unavailable.

Design Principles
=================
1. **Realistic**: Spreads widen during high-volatility periods and market open/close
2. **Efficient**: Processes 800K+ candles per second
3. **Flexible**: Configurable for different market conditions
4. **Accurate**: Based on real market microstructure patterns

Spread Calculation
==================

Base Spread Components:
  spread = max(price_component, volatility_component)

Where:
  price_component = mid_price * base_price_factor
                   (default: 0.02% of price)
  
  volatility_component = (high - low) * volatility_factor
                        (default: 5% of candle range)

Market Hours Adjustments:
  - Opening period (first 15 minutes): spread *= 1.5
  - Closing period (last 15 minutes):  spread *= 1.2
  - Regular hours: no adjustment

Execution Prices:
  bid = mid_price - spread / 2
  ask = mid_price + spread / 2
  
  BUY orders execute at ask (worst price for buyer)
  SELL orders execute at bid (worst price for seller)


Class Reference
================

Constructor Parameters:
  base_price_factor (float, default=0.0002)
    - Spread as fraction of price (0.0002 = 0.02%)
    - Higher values = wider spreads (less liquid markets)
    - Lower values = tighter spreads (highly liquid markets)
  
  volatility_factor (float, default=0.05)
    - Multiplier for (high - low) range (0.05 = 5%)
    - Controls spread sensitivity to intrabar price movement
    - 5% means spread is 5% of candle range
  
  market_open_time (str, default="14:30")
    - Market open time in "HH:MM" format (UTC)
    - Alpaca: 9:30 AM ET = 14:30 UTC (winter) or 13:30 UTC (summer)
    - For example: "14:30" or "09:30"
  
  market_close_time (str, default="20:00")
    - Market close time in "HH:MM" format (UTC)
    - Alpaca: 4:00 PM ET = 20:00 UTC (winter) or 21:00 UTC (summer)
  
  opening_period_minutes (int, default=15)
    - Minutes after market open to apply opening multiplier
    - 15 minutes is standard (market open is volatile)
  
  closing_period_minutes (int, default=15)
    - Minutes before market close to apply closing multiplier
    - 15 minutes is standard (portfolio adjustments before close)
  
  opening_spread_multiplier (float, default=1.5)
    - Multiplier applied during first N minutes (1.5 = 50% wider)
    - Reflects higher volatility and order flow at open
  
  closing_spread_multiplier (float, default=1.2)
    - Multiplier applied during last N minutes (1.2 = 20% wider)
    - Reflects portfolio adjustments and lower liquidity
  
  timezone (str, default="UTC")
    - Timezone for interpreting timestamps
    - Typical values: "UTC", "US/Eastern", "US/Pacific"


Methods:

  get_bid_ask(mid_price, high, low, timestamp, volume=None)
    Returns: (bid, ask, spread)
    - mid_price (float): Candle close price (used as mid price)
    - high (float): Candle high price
    - low (float): Candle low price
    - timestamp (datetime or str): Candle timestamp (ISO or datetime)
    - volume (float, optional): Trading volume (reserved for future use)
    
    Example:
      bid, ask, spread = model.get_bid_ask(
        mid_price=150.50,
        high=151.25,
        low=150.10,
        timestamp="2026-01-20T16:00:00Z"
      )
      # Returns: (150.4712, 150.5288, 0.0575)
  
  get_spread_only(mid_price, high, low, timestamp)
    Returns: spread (float)
    - Convenience method if you only need the spread value


Usage Patterns
==============

Pattern 1: Simple Backtesting
  model = SyntheticSpreadModel()
  for timestamp in timecourse:
    bid, ask, spread = model.get_bid_ask(
      mid_price=candle.close,
      high=candle.high,
      low=candle.low,
      timestamp=timestamp
    )
    if strategy.should_buy():
      portfolio.buy_at_price(ask)
    elif strategy.should_sell():
      portfolio.sell_at_price(bid)


Pattern 2: Dynamic Spread Adjustment
  model = SyntheticSpreadModel(
    base_price_factor=0.0001,  # Tighter spreads
    opening_spread_multiplier=1.3  # Less opening widening
  )


Pattern 3: Market-Specific Configuration
  # For forex (spreads in pips)
  forex_model = SyntheticSpreadModel(
    base_price_factor=0.0002,
    volatility_factor=0.03
  )
  
  # For crypto (often wider spreads)
  crypto_model = SyntheticSpreadModel(
    base_price_factor=0.0005,
    opening_spread_multiplier=2.0
  )


Validation & Benchmarks
========================

Typical Spreads (mid-market for $150 stock):
  - Tight candle (1¢ range):      $0.030 (0.02% of price)
  - Normal candle (75¢ range):    $0.038 (0.03% of price)
  - Volatile candle ($5 range):   $0.250 (0.17% of price)

Market Hours Impact:
  - Mid-day:                      1.0x (base spread)
  - First 15 min (open):         1.5x (50% wider)
  - Last 15 min (close):         1.2x (20% wider)

Cost per Round Trip (buy then sell):
  At $150 per share:
    - Base spread: $0.058 (0.038% of price)
    - Entry cost: $0.029 (half the spread at ask)
    - Exit cost: $0.029 (half the spread at bid)
    - Total cost per trade: ~0.038% of capital


Performance Characteristics
============================

Performance (measured on test machine):
  - ~870K candles per second
  - 0.0011 ms per candle
  - Negligible overhead vs raw backtest

Memory:
  - Model instance: ~1 KB
  - No per-candle memory allocation
  - Suitable for very large datasets


Integration Points
===================

In backtest/evaluator.py:
  - Initialize model in __init__
  - Use in execute_trade() when applying orders

In scripts/backtest_runner.py:
  - Create model instance
  - Pass to strategy.decide() calls

In penguins/*_penguin.py:
  - Already receive bid/ask from engine
  - No changes needed (backward compatible)


Edge Cases & Considerations
============================

1. Pre-market and After-hours
   - Model assumes standard market hours (14:30-20:00 UTC)
   - Candles outside these hours get closing period treatment
   - Can be overridden with custom timezone/hours

2. Holiday Closures
   - Model does not account for holidays
   - Spreads may be artificially tight on non-trading days
   - Consider filtering data to trading days only

3. Micro-gaps and Limit Moves
   - Model does not generate gaps or limit-up/limit-down
   - Assumes normal market conditions
   - Historical data used as-is

4. Volume Consideration
   - Volume parameter reserved for future use
   - Not currently applied but available for enhancement
   - Could multiply spreads based on volume anomalies


Testing & Validation
====================

Run test suite:
  $ python assistive_scripts/test_spread_model.py
  
  Validates:
  - Bid/ask calculation accuracy
  - Market hours detection
  - Volatility sensitivity
  - Performance benchmark

View examples:
  $ python assistive_scripts/spread_model_examples.py
  
  Demonstrates:
  - Basic usage
  - Strategy integration
  - Spread impact analysis
  - Custom configurations
  - Timestamp format compatibility


Historical Performance Impact
=============================

Estimated annual drag from spreads (assuming multiple trades):
  - 1 trade/day:  -13.9% per year (-0.038% per trade)
  - 5 trades/day: -69.6% per year
  - 10 trades/day: -139% per year (!)

This emphasizes why realistic spreads are critical for backtesting
and why strategies must generate edge > spread cost.
"""

# This file is for documentation only; see:
# - backtest/synthetic_spread_model.py for implementation
# - assistive_scripts/test_spread_model.py for tests
# - assistive_scripts/spread_model_examples.py for examples
