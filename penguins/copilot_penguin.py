# penguins/copilot_penguin.py
from penguins.base_penguin import BasePenguin
from indicators.momentum import rsi, roc


class CopilotPenguin(BasePenguin):
    def __init__(self):
        super().__init__("CopilotPenguin")
        self.entry_price = {}  # Track entry prices by symbol
        self.last_trade_index = {}  # Track last trade index by symbol
        self.entry_rsi = {}  # Track RSI at entry for validation

        # Strategy parameters - IMPROVED for fewer false signals
        self.min_bars = 50
        self.cooldown_bars = 8  # Increased from 5 to avoid whipsaws
        self.max_spread_pct = 1.0
        self.min_trend_roc = 0.015  # Increased from 0.5% to 1.5% (stricter momentum)
        self.min_roc_short = 0.01  # ROC(3) must also be positive
        self.stop_loss_atr_mult = 1.0  # Reduced from 1.5 (stops were too loose)
        self.take_profit_atr_mult = 2.5  # Increased from 2.0 (need bigger targets)
        self.rsi_momentum_lookback = 5  # RSI must be rising over this period

    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        """
        Improved trend-following strategy with stricter entry and better exits.
        
        Key improvements:
        - Higher momentum threshold (ROC > 1.5%) to avoid premature entries
        - RSI confirmation: RSI must be rising (not just in range)
        - Both short and medium ROC must be positive
        - Tighter stops (1.0x ATR) to exit early from failed setups
        - Longer cooldown (8 bars) to reduce whipsaw losses
        """
        if bid <= 0 or ask <= 0:
            return "HOLD", 0

        if len(mid_prices) < self.min_bars:
            return "HOLD", 0

        # Avoid trading on wide spreads
        spread_pct = (ask - bid) / bid * 100 if bid > 0 else 0
        if spread_pct > self.max_spread_pct:
            return "HOLD", 0

        # Calculate indicators
        rsi_val = rsi(mid_prices, n=14)
        rsi_prev = rsi(mid_prices[:-1], n=14) if len(mid_prices) > self.rsi_momentum_lookback else 0
        roc_short = roc(mid_prices, n=3)
        roc_medium = roc(mid_prices, n=7)

        # Trend detection: SMA20 above SMA50
        sma_20 = sum(mid_prices[-20:]) / 20
        sma_50 = sum(mid_prices[-50:]) / 50
        price = mid_prices[-1]
        is_uptrend = price > sma_20 > sma_50

        # Volatility proxy (range over last 10 bars)
        recent_high = max(mid_prices[-10:])
        recent_low = min(mid_prices[-10:])
        atr_proxy = max(recent_high - recent_low, 0.01)

        # Price extension filter: don't buy near 50-bar highs
        bar_50_high = max(mid_prices[-50:])
        bar_50_low = min(mid_prices[-50:])
        bar_50_range = bar_50_high - bar_50_low
        extension_pct = (price - bar_50_low) / bar_50_range if bar_50_range > 0 else 0.5
        price_too_extended = extension_pct > 0.95  # At 95%+ of 50-bar high

        # Check if we have a position
        has_position = (
            symbol in portfolio.positions and portfolio.positions[symbol].qty > 0
        )
        position_qty = portfolio.positions[symbol].qty if has_position else 0

        # Cooldown after last trade for this symbol
        current_index = len(mid_prices)
        last_trade_index = self.last_trade_index.get(symbol, -999)
        in_cooldown = (current_index - last_trade_index) <= self.cooldown_bars

        # ========== BUY SIGNALS ==========
        # IMPROVED: Multiple confirmations required
        # 1. Strong uptrend (SMA20 > SMA50)
        # 2. Strong momentum (ROC(7) > 1.5% AND ROC(3) > 1.0%)
        # 3. RSI confirmation (50-70 range AND rising)
        # 4. Price not too extended (< 95% of 50-bar high)
        
        rsi_rising = rsi_val >= rsi_prev  # RSI must be increasing
        strong_momentum = roc_medium > self.min_trend_roc and roc_short > self.min_roc_short
        buy_signal = (is_uptrend and strong_momentum and 50 <= rsi_val <= 70 
                     and rsi_rising and not price_too_extended)

        if buy_signal and not has_position and not in_cooldown:
            # Position size based on volatility proxy
            qty = 1 if atr_proxy / price > 0.02 else 2
            if portfolio.cash >= ask:
                self.last_trade_index[symbol] = current_index
                self.entry_price[symbol] = ask
                self.entry_rsi[symbol] = rsi_val
                return "BUY", qty
            return "HOLD", 0

        # ========== SELL SIGNALS ==========
        # Exit conditions:
        # 1. Tight stop loss (1.0x ATR) - exit early from failed setups
        # 2. Take profit (2.5x ATR) - capture strong moves
        # 3. Trend break (price < SMA20 AND negative ROC)
        # 4. RSI divergence (price rising but RSI falling) - warning signal

        if has_position:
            entry_price = portfolio.positions[symbol].avg_price
            take_profit_price = entry_price + self.take_profit_atr_mult * atr_proxy
            stop_loss_price = entry_price - self.stop_loss_atr_mult * atr_proxy

            if bid >= take_profit_price:
                self.last_trade_index[symbol] = current_index
                return "SELL", position_qty

            if bid <= stop_loss_price:
                self.last_trade_index[symbol] = current_index
                return "SELL", position_qty

            # Trend break exit (tighter: must be below SMA20 AND ROC negative)
            if bid < sma_20 and roc_short < 0:
                self.last_trade_index[symbol] = current_index
                return "SELL", position_qty

        return "HOLD", 0
