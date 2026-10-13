from penguins.base_penguin import BasePenguin
from indicators.momentum import rsi, roc
from indicators.statsistics import sma
import numpy as np
from datetime import datetime


class SmartRSIConfluencePenguin(BasePenguin):
    LOOKBACK_BARS = 100  # More context for stable filters

    def __init__(
        self,
        rsi_period=14,
        oversold=30,
        overbought=70,
        sma_period=50,
        roc_period=5,
        min_confidence=3,    # stricter minimum score
        max_buy_size=2,      # smaller position sizes
        max_trades_per_day=10,
        cooldown_bars=20,
        max_spread_pct=1.5,
    ):
        super().__init__("Smart RSI Confluence")

        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought
        self.sma_period = sma_period
        self.roc_period = roc_period

        self.min_confidence = min_confidence
        self.max_buy_size = max_buy_size
        self.max_trades_per_day = max_trades_per_day
        self.cooldown_bars = cooldown_bars
        self.max_spread_pct = max_spread_pct

        self.current_date = None
        self.daily_trade_count = 0
        self.last_trade_bar = {}

    def set_current_timestamp(self, timestamp):
        if not isinstance(timestamp, datetime):
            return

        new_date = timestamp.date()
        if self.current_date is not None and new_date != self.current_date:
            self.daily_trade_count = 0
        self.current_date = new_date

    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        # ===== BASIC CHECKS =====
        if bid <= 0 or ask <= 0:
            return "HOLD", 0

        spread_pct = (ask - bid) / bid * 100 if bid > 0 else 0
        if spread_pct > self.max_spread_pct:
            return "HOLD", 0

        if len(mid_prices) < self.LOOKBACK_BARS:
            return "HOLD", 0

        if self.daily_trade_count >= self.max_trades_per_day:
            return "HOLD", 0

        price = mid_prices[-1]
        qty = portfolio.get_position(symbol)
        cash = portfolio.cash

        current_bar = len(mid_prices)
        last_bar = self.last_trade_bar.get(symbol, -np.inf)
        if current_bar - last_bar < self.cooldown_bars:
            return "HOLD", 0

        # ===== INDICATORS =====
        rsi_val = rsi(mid_prices, self.rsi_period)
        sma_val = sma(mid_prices, self.sma_period)
        momentum = roc(mid_prices, self.roc_period)

        recent_prices = mid_prices[-20:]
        mean_price = np.mean(recent_prices)
        volatility = (np.std(recent_prices) / mean_price) if mean_price > 0 else 0

        # ===== SCORING SYSTEM =====
        score = 0

        # --- RSI Signal ---
        if rsi_val < self.oversold:
            score += 2   # strong base signal
        elif rsi_val < self.oversold + 5:
            score += 1   # weaker signal

        # --- Trend Filter (avoid catching falling knives) ---
        if price > sma_val:
            score += 1   # aligned with uptrend
        else:
            score -= 1   # downtrend penalty

        # --- Momentum Confirmation ---
        if momentum > 0:
            score += 1
        else:
            score -= 1

        # --- Volatility Sweet Spot ---
        # Too low = no movement, too high = chaos
        if 0.003 < volatility < 0.03:
            score += 1
        elif volatility >= 0.03:
            score -= 1

        # ===== BUY LOGIC =====
        # Only open when flat; no pyramiding.
        if qty == 0 and score >= self.min_confidence:
            # Confidence-based sizing
            strength = min(score, self.max_buy_size)

            # Don’t overbuy relative to cash
            affordable_qty = int(cash // ask)
            qty_to_buy = min(strength, affordable_qty)

            if qty_to_buy > 0:
                self.daily_trade_count += 1
                self.last_trade_bar[symbol] = current_bar
                return "BUY", qty_to_buy

        # ===== SELL LOGIC =====
        if qty > 0:
            sell_score = 0

            if rsi_val > self.overbought:
                sell_score += 2

            if momentum < 0:
                sell_score += 1

            if price < sma_val:
                sell_score += 1

            if sell_score >= 2:
                self.daily_trade_count += 1
                self.last_trade_bar[symbol] = current_bar
                return "SELL", qty

        return "HOLD", 0
