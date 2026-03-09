#!/usr/bin/env python3
"""
Summary of the new plot_stocks_with_spreads visualization script
Created: 2026-03-09
"""

print("""
================================================================================
✅ NEW VISUALIZATION: STOCKS WITH SYNTHETIC SPREADS
================================================================================

Two new scripts have been added to assistive_scripts/:

1. plot_stocks_with_spreads.py
   └─ Main script for creating PDF visualizations
   └─ Generates one chart per stock showing bid/ask spreads

2. quick_spreads.py  
   └─ Convenience script with pre-configured presets
   └─ Quick access to common report types

================================================================================
QUICK START
================================================================================

# View stocks from your config with default historical data:
python assistive_scripts/plot_stocks_with_spreads.py

# Or use the convenience script:
python assistive_scripts/quick_spreads.py config

# Specific symbols and date range:
python assistive_scripts/plot_stocks_with_spreads.py \\
  --symbols AAPL MSFT GLD \\
  --start "2026-02-20" \\
  --end "2026-02-28"

# All available symbols:
python assistive_scripts/quick_spreads.py all

================================================================================
FEATURES
================================================================================

Each PDF page shows:
  ✓ Close price line (mid-price)
  ✓ Bid/Ask spread band (blue shaded region)
  ✓ Spread width coloring (red = wide, green = tight)
  ✓ Bid/ask prices as dashed lines
  ✓ Statistics (avg spread, max spread, price range)
  ✓ Data insights (number of bars, timestamp)

Colors:
  └─ Red: Wide spreads (higher trading costs)
  └─ Yellow: Medium spreads
  └─ Green: Tight spreads (lower trading costs)

================================================================================
COMMAND-LINE OPTIONS
================================================================================

python assistive_scripts/plot_stocks_with_spreads.py [OPTIONS]

  --symbols AAPL MSFT ...    Specific symbols to plot
  --all-symbols              Plot all symbols from config
  --start "2026-02-20"       Start date (YYYY-MM-DD)
  --end "2026-02-28"         End date (YYYY-MM-DD)
  --output path/to/file.pdf  Save location (default: run_current/...)

================================================================================
CONVENIENCE SCRIPT PRESETS
================================================================================

python assistive_scripts/quick_spreads.py [PRESET]

  config      - Use your configured symbols (default)
  recent      - Last 7 days of your assets
  all         - All symbols, last month
  tech        - Tech sector only
  commodities - Commodity ETFs only  
  miners      - Mining/metals ETFs only

================================================================================
EXAMPLES
================================================================================

# Analyze spreads for your current active penguins:
python assistive_scripts/plot_stocks_with_spreads.py \\
  --output run_current/current_spreads.pdf

# Deep dive: specific date range
python assistive_scripts/plot_stocks_with_spreads.py \\
  --symbols LMT GLD AMD \\
  --start "2026-02-01" \\
  --end "2026-02-28" \\
  --output run_current/spread_analysis_feb.pdf

# Quick market overview:
python assistive_scripts/quick_spreads.py all

# Tech sector analysis:
python assistive_scripts/quick_spreads.py tech

================================================================================
DATA & PERFORMANCE NOTES
================================================================================

✓ Uses Alpaca historical market data
✓ Calculates realistic bid/ask spreads based on:
  - Price level (0.02% of mid-price)
  - Volatility (5% of candle range)
  - Volume effects
  - Market hours adjustments

✓ Data is cached after first fetch for faster subsequent runs
✓ Typical performance: 
  - Single symbol: < 5 seconds
  - 10 symbols: 30-60 seconds
  - 20+ symbols: 2-5 minutes

================================================================================
TROUBLESHOOTING
================================================================================

❌ "No data available" error:
   → Check date range is in the past (avoid TODAY or very recent dates)
   → Ensure symbol is valid (check config/symbols.py)
   → Try: --start "2026-02-20" --end "2026-02-28"

❌ API subscription error ("does not permit querying recent SIP data"):
   → Use historical dates (at least 7 days old)
   → The script now defaults to 7 days ago instead of today

✓ Cached data speeds up subsequent runs significantly

================================================================================
INTEGRATION WITH YOUR BACKTEST
================================================================================

To analyze spreads from your most recent backtest:

1. Run your backtest:
   python run_simulation.py

2. Generate spread visualization using your backtest's symbol list:
   python assistive_scripts/plot_stocks_with_spreads.py

The script will:
  ✓ Use symbols from config.py (same as your backtest)
  ✓ Default to 7 days of historical data (to avoid API restrictions)
  ✓ Show realistic bid/ask costs for each symbol
  ✓ Help identify which symbols have tight/wide spreads

================================================================================
UNDERSTANDING THE VISUALIZATION
================================================================================

What each element tells you:

  SPREAD BAND (blue region):
    Wide band = More risk of slippage on entry/exit
    Narrow band = Tighter execution possible

  COLOR INTENSITY (red to green):
    Red dots (left side) = Less efficient market conditions
    Green dots (right side) = Better liquidity/tighter spreads

  STATISTICS BOX:
    Avg Spread: Expected cost per trade (% of price)
    Max Spread: Worst-case scenario in this period

Example interpretation:
  - If AAPL shows green dots → Excellent liquidity
  - If GLD shows red dots → Expect wider spreads on trades
  - Wider band near market close → Opening/closing premium costs

================================================================================
FILES ADDED
================================================================================

./assistive_scripts/plot_stocks_with_spreads.py
  │
  └─ Main visualization generator
     - Loads market data (Alpaca DataLoader)
     - Calculates synthetic spreads
     - Creates multi-page PDF reports
     - ~350 lines

./assistive_scripts/quick_spreads.py
  │
  └─ Convenience wrapper with presets
     - Pre-configured report types
     - ~150 lines

./assistive_scripts/PLOT_STOCKS_README.md
  │
  └─ Detailed usage documentation

================================================================================
NEXT STEPS
================================================================================

1. Try a simple test:
   python assistive_scripts/plot_stocks_with_spreads.py \\
     --symbols AAPL --start "2026-02-20" --end "2026-02-28"

2. Generate your current configuration report:
   python assistive_scripts/quick_spreads.py config

3. Use with your backtest:
   - Run simulation.py
   - Generate spreads: python assistive_scripts/quick_spreads.py config
   - Check spreads for your active penguins

4. Analyze different market segments:
   python assistive_scripts/quick_spreads.py tech
   python assistive_scripts/quick_spreads.py commodities
   python assistive_scripts/quick_spreads.py miners

================================================================================
""")
