"""Active trading strategy (penguin) configuration."""

# Import all available penguin strategies
from penguins import (
    BreakoutPenguin,
    CopilotPenguin,
    MeanReversionPenguin,
    MultitimeframeRangeSRPenguin,
    MultitimeframeReactionSRPenguin,
    MinMaxSRPenguin,
    MovingAverageCrossoverPenguin,
    MomentumPenguin,
    SP500Penguin,
    RSIMeanReversionPenguin,
    SMA20Penguin,
    VolatilityBreakoutPenguin,
)

# ========== ACTIVE PENGUINS ==========
# List of penguin strategy classes to run in the backtest
# Comment out strategies you don't want to run
# Each strategy will be tested in parallel on the same data

ACTIVE_PENGUINS = [

    MinMaxSRPenguin,           # Single timeframe S/R
    #MultitimeframeReactionSRPenguin,    # Multi-TF S/R with reaction logic
    
    SMA20Penguin,                       # SMA-X crossover
    # MovingAverageCrossoverPenguin,    # Classic MA crossover
    
    CopilotPenguin,                     # AI-assisted strategy
 
    MomentumPenguin,                  # Pure momentum following
    ### TrendPenguin,                     # Trend following
    ### CarefulTrendPenguin,              # Conservative trend with filters

    MeanReversionPenguin,             # Mean Reversion (RSI Alias)
    RSIMeanReversionPenguin,          # RSI Mean Reversion (Improved)
  
    # BreakoutPenguin,                  # Price breakout detection
    # VolatilityBreakoutPenguin,        # Volatility-based breakouts

    SP500Penguin,                       # Buy & hold S&P 500 ETF benchmark (SPY)

    ### RandomPenguin,                    # Random trading (control)
    ### RandomPenguin2,                   # Alternative random implementation
]

__all__ = [
    "ACTIVE_PENGUINS",
]
