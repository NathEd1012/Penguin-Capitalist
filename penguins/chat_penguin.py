from penguins.base_penguin import BasePenguin
from indicators.momentum import rsi
from indicators.statsistics import sma
import numpy as np
from datetime import datetime


class RSIMeanReversionSelectivePenguin(BasePenguin):
    """
    Low-frequency, high-quality RSI mean reversion strategy.

    Improvements:
    - Stronger RSI thresholds (quality > quantity)
    - Trend filter (avoid fighting strong trends)
    - Volatility filter (avoid noise)
    - Cooldown between trades
    - Hard cap on trades per day
    """

    LOOKBACK_BARS = 100

    def __init__(
        self,
        rsi_period=14,
        oversold=25,         # stricter → better signals
        overbought=75,
        sma_period=50,
        min_volatility=0.002,   # ~0.2% std threshold
        cooldown_bars=10,
        max_trades_per_day=8,
    ):
        super().__init__("RSI Mean Reversion Selective")

        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought
        self.sma_period = sma_period
        self.min_volatility = min_volatility
        self.cooldown_bars = cooldown_bars
        self.max_trades_per_day = max_trades_per_day

        # State
        self.last_trade_bar = {}
        self.current_date = None
        self.daily_trade_count = 0

    def set_current_timestamp(self, timestamp):
        if not isinstance(timestamp, datetime):
            return

        new_date = timestamp.date()
        if self.current_date is not None and new_date != self.current_date:
            self.daily_trade_count = 0

        self.current_date = new_date

    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        if bid <= 0 or ask <= 0:
            return "HOLD", 0

        if len(mid_prices) < self.LOOKBACK_BARS:
            return "HOLD", 0

        # --- Daily trade cap ---
        if self.daily_trade_count >= self.max_trades_per_day:
            return "HOLD", 0

        # --- Cooldown ---
        current_bar = len(mid_prices)
        last_bar = self.last_trade_bar.get(symbol, -np.inf)
        if current_bar - last_bar < self.cooldown_bars:
            return "HOLD", 0

        # --- Indicators ---
        rsi_val = rsi(mid_prices, self.rsi_period)
        sma_val = sma(mid_prices, self.sma_period)

        recent_prices = np.array(mid_prices[-20:])
        volatility = np.std(recent_prices) / np.mean(recent_prices)

        price = mid_prices[-1]
        qty = portfolio.get_position(symbol)
        cash = portfolio.cash

        # --- Volatility filter ---
        if volatility < self.min_volatility:
            return "HOLD", 0

        # --- Trend filter ---
        # Avoid strong trends → only mean revert in neutral zones
        distance_from_sma = (price - sma_val) / sma_val

        if abs(distance_from_sma) > 0.03:  # ~3% away → trending
            return "HOLD", 0

        # --- Decision ---
        action = "HOLD"
        trade_qty = 0

        # Strong mean reversion entries only
        if rsi_val < self.oversold and cash >= ask:
            action = "BUY"
            trade_qty = 1

        elif rsi_val > self.overbought and qty > 0:
            action = "SELL"
            trade_qty = qty

        if action != "HOLD":
            self.daily_trade_count += 1
            self.last_trade_bar[symbol] = current_bar

        return action, trade_qty