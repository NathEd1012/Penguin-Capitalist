"""Active trading strategy (penguin) configuration."""

# Import all available penguin strategies
from penguins import (
    BreakoutPenguin,
    CarefulTrendPenguin,
    CopilotPenguin,
    MeanReversionPenguin,
    MultitimeframeRangeSRPenguin,
    MultitimeframeReactionSRPenguin,
    MovingAverageCrossoverPenguin,
    MomentumPenguin,
    SP500Penguin,
    RandomPenguin,
    RandomPenguin2,
    RSIMeanReversionPenguin,
    SMA20Penguin,
    SupportResistancePenguin,
    TrendPenguin,
    VolatilityBreakoutPenguin,
)

# ========== ACTIVE PENGUINS ==========
# List of penguin strategy classes to run in the backtest
# Comment out strategies you don't want to run
# Each strategy will be tested in parallel on the same data

ACTIVE_PENGUINS = [

    SupportResistancePenguin,           # Single timeframe S/R
    #MultitimeframeReactionSRPenguin,    # Multi-TF S/R with reaction logic
    
    SMA20Penguin,                       # SMA-20 crossover
    # MovingAverageCrossoverPenguin,    # Classic MA crossover
    
    CopilotPenguin,                     # AI-assisted strategy
 
    # MomentumPenguin,                  # Pure momentum following
    # TrendPenguin,                     # Trend following
    # CarefulTrendPenguin,              # Conservative trend with filters

    # MeanReversionPenguin,             # Basic mean reversion
    RSIMeanReversionPenguin,          # RSI-based mean reversion
  
    # BreakoutPenguin,                  # Price breakout detection
    # VolatilityBreakoutPenguin,        # Volatility-based breakouts

    SP500Penguin,                       # Buy & hold S&P 500 ETF benchmark (SPY)

    # RandomPenguin,                    # Random trading (control)
    # RandomPenguin2,                   # Alternative random implementation
]

__all__ = [
    "ACTIVE_PENGUINS",
]
