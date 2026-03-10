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
    SMA20MultiTimeframePenguin,
    SupportResistancePenguin,
    TrendPenguin,
    VolatilityBreakoutPenguin,
)

# ========== ACTIVE PENGUINS ==========
# List of penguin strategy classes to run in the backtest
# Comment out strategies you don't want to run
# Each strategy will be tested in parallel on the same data

ACTIVE_PENGUINS = [
    # ─────────────────────────────────────────────────────
    # TECHNICAL ANALYSIS STRATEGIES
    # ─────────────────────────────────────────────────────
    
    # Support/Resistance based strategies
    SupportResistancePenguin,           # Single timeframe S/R
    MultitimeframeReactionSRPenguin,    # Multi-TF S/R with reaction logic
    # MultitimeframeRangeSRPenguin,     # Previous min/max range-extremes approach
    
    # Moving Average strategies
    SMA20MultiTimeframePenguin,         # SMA-20 with multi-timeframe confirmation
    # MovingAverageCrossoverPenguin,    # Classic MA crossover
    
    # AI/ML assisted
    CopilotPenguin,                     # AI-assisted strategy
    
    # ─────────────────────────────────────────────────────
    # MOMENTUM & TREND STRATEGIES
    # ─────────────────────────────────────────────────────
    
    # MomentumPenguin,                  # Pure momentum following
    # TrendPenguin,                     # Trend following
    # CarefulTrendPenguin,              # Conservative trend with filters
    
    # ─────────────────────────────────────────────────────
    # MEAN REVERSION STRATEGIES
    # ─────────────────────────────────────────────────────
    
    # MeanReversionPenguin,             # Basic mean reversion
    # RSIMeanReversionPenguin,          # RSI-based mean reversion
    
    # ─────────────────────────────────────────────────────
    # BREAKOUT STRATEGIES
    # ─────────────────────────────────────────────────────
    
    # BreakoutPenguin,                  # Price breakout detection
    # VolatilityBreakoutPenguin,        # Volatility-based breakouts
    
    # ─────────────────────────────────────────────────────
    # BUY & HOLD / BENCHMARKS
    # ─────────────────────────────────────────────────────
    
    SP500Penguin,                       # Buy & hold S&P 500 ETF benchmark (SPY)
    
    # ─────────────────────────────────────────────────────
    # RANDOM / CONTROL STRATEGIES
    # ─────────────────────────────────────────────────────
    
    # RandomPenguin,                    # Random trading (control)
    # RandomPenguin2,                   # Alternative random implementation
]

__all__ = [
    "ACTIVE_PENGUINS",
]
