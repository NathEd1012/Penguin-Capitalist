from penguins.base_penguin import BasePenguin
from indicators.momentum import rsi
from datetime import datetime


class RSIMeanReversionReducedPenguin(BasePenguin):
    """
    Adaptive RSI Mean Reversion strategy that targets 1-10 trades per day.
    Dynamically adjusts oversold/overbought boundaries based on previous day's trading activity.
    """
    LOOKBACK_BARS = 30  # Only needs last 30 bars for RSI calculation
    
    # LIST 2: Trade only these symbols
    TRADED_SYMBOLS = {
        # Tech giants & growth
        "SPY", "NVDA", "AAPL", "PLTR", "AMD", "MSTR", "MSFT", "TSLA",
        # Materials & Mining
        "MP",
        # Defense
        "NOC", "LMT",
        # International
        "NVO",
        # ETFs / Commodity ETFs
        "GLD", "SLV", "PPLT", "COPX", "JO", "LIT", "URTH", "GDXJ", "SIL", "REMX", "PICK",
    }
    
    def __init__(self, rsi_period=14, target_trades_min=1, target_trades_max=10):
        super().__init__("RSIMeanReversionReducedPenguin")
        self.rsi_period = rsi_period
        self.target_trades_min = target_trades_min
        self.target_trades_max = target_trades_max
        
        # Base boundaries
        self.base_oversold = 30
        self.base_overbought = 70
        
        # Current adaptive boundaries
        self.oversold = self.base_oversold
        self.overbought = self.base_overbought
        
        # Tracking for daily trades
        self.current_date = None
        self.daily_trade_count = 0
        self.previous_day_trade_count = 0
    
    def set_current_timestamp(self, timestamp):
        """Called at each bar to track day changes and adapt boundaries."""
        if not isinstance(timestamp, datetime):
            return
        
        new_date = timestamp.date()
        
        # Day changed - adapt boundaries based on previous day's trades
        if self.current_date is not None and new_date != self.current_date:
            self.previous_day_trade_count = self.daily_trade_count
            self.daily_trade_count = 0
            self._adapt_boundaries()
        
        self.current_date = new_date
    
    def _adapt_boundaries(self):
        """Adjust oversold/overbought based on previous day's trade count."""
        trades = self.previous_day_trade_count
        
        # If too many trades, tighten boundaries (make RSI thresholds stricter)
        if trades > self.target_trades_max:
            # Reduce threshold range significantly
            adjustment = min(10, (trades - self.target_trades_max) * 2)
            self.oversold = min(self.base_oversold + adjustment, 40)
            self.overbought = max(self.base_overbought - adjustment, 60)
        
        # If too few trades, loosen boundaries (make RSI thresholds more generous)
        elif trades < self.target_trades_min:
            # Expand threshold range significantly
            adjustment = max(0, (self.target_trades_min - trades) * 3)
            self.oversold = max(self.base_oversold - adjustment, 10)
            self.overbought = min(self.base_overbought + adjustment, 90)
        
        # Within target range - use base boundaries
        else:
            self.oversold = self.base_oversold
            self.overbought = self.base_overbought

    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        if bid <= 0 or ask <= 0:
            return "HOLD", 0

        if len(mid_prices) < self.rsi_period + 1:
            return "HOLD", 0

        rsi_val = rsi(mid_prices, self.rsi_period)
        qty = portfolio.get_position(symbol)
        cash = portfolio.cash

        action = "HOLD"
        trade_qty = 0

        # Buy signal: RSI below oversold threshold and we have cash
        if rsi_val < self.oversold and cash >= ask:
            action = "BUY"
            trade_qty = 1
            self.daily_trade_count += 1
        
        # Sell signal: RSI above overbought threshold and we hold position
        elif rsi_val > self.overbought and qty > 0 and bid > 0:
            action = "SELL"
            trade_qty = qty
            self.daily_trade_count += 1

        return action, trade_qty
