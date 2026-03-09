# penguins/copilot_penguin.py
from penguins.base_penguin import BasePenguin
from indicators.momentum import rsi, roc


class CopilotPenguin(BasePenguin):
    def __init__(self):
        super().__init__("CopilotPenguin")
        self.entry_price = {}  # Track entry prices by symbol
        self.last_trade_index = {}  # Track last trade index by symbol
        self.highest_price_since_entry = {}  # For trailing stop

        # Improved strategy parameters
        self.min_bars = 50  # Increased for better indicator reliability
        self.cooldown_bars = 3
        self.max_spread_pct = 2.0
        self.min_trend_roc = 0.002  # Stronger momentum required (20x previous)
        self.stop_loss_atr_mult = 1.0  # Tighter stop (was 1.5)
        self.take_profit_atr_mult = 1.5  # Closer target (was 2.0)
        self.trailing_stop_trigger = 1.0  # Activate trailing after 1×ATR profit

    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        """
        Trend-following strategy with cooldown and volatility-aware exits.
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
        rsi_val = rsi(mid_prices, period=14)
        roc_short = roc(mid_prices, period=3)
        roc_medium = roc(mid_prices, period=7)

        # Trend detection: SMA20 above SMA50
        sma_20 = sum(mid_prices[-20:]) / 20
        sma_50 = sum(mid_prices[-50:]) / 50
        price = mid_prices[-1]
        is_uptrend = price > sma_20 > sma_50

        # Volatility proxy (range over last 10 bars)
        recent_high = max(mid_prices[-10:])
        recent_low = min(mid_prices[-10:])
        atr_proxy = max(recent_high - recent_low, 0.01)

        # Check if we have a position
        has_position = (
            symbol in portfolio.positions and portfolio.positions[symbol].qty > 0
        )
        position_qty = portfolio.positions[symbol].qty if has_position else 0

        # Current index for bookkeeping when recording trades
        current_index = len(mid_prices)

        # ========== BUY SIGNALS ==========
        # Improved entry: Strong momentum + healthy RSI + confirmed uptrend
        strong_momentum = roc_medium > self.min_trend_roc and roc_short > 0
        healthy_rsi = 40 <= rsi_val <= 70  # Avoid overbought/oversold
        buy_signal = strong_momentum and healthy_rsi and is_uptrend

        if buy_signal:
            # Dynamic position sizing based on signal strength
            # Stronger signals (higher ROC + centered RSI) get larger positions
            rsi_strength = 1.0 - abs(rsi_val - 55) / 55  # Peak at RSI=55
            roc_strength = min(roc_medium / 0.01, 1.0)  # Cap at 1%
            signal_strength = (rsi_strength + roc_strength) / 2
            
            # Size: 1-3 shares based on signal strength and volatility
            if atr_proxy / price > 0.03:  # High volatility
                qty = 1
            elif signal_strength > 0.7:  # Very strong signal
                qty = 3
            elif signal_strength > 0.5:  # Good signal
                qty = 2
            else:
                qty = 1
                
            if portfolio.cash >= ask * qty:
                self.last_trade_index[symbol] = current_index
                self.entry_price[symbol] = ask
                self.highest_price_since_entry[symbol] = bid  # Initialize trailing stop
                return "BUY", qty
            return "HOLD", 0

        # ========== SELL SIGNALS ==========
        # Improved exit conditions:
        # 1. Tighter take profit
        # 2. Tighter stop loss with trailing protection
        # 3. Trend break exit
        # 4. Momentum reversal exit

        if has_position:
            entry_price = portfolio.positions[symbol].avg_price
            take_profit_price = entry_price + self.take_profit_atr_mult * atr_proxy
            initial_stop_loss = entry_price - self.stop_loss_atr_mult * atr_proxy
            
            # Update highest price for trailing stop
            if symbol not in self.highest_price_since_entry:
                self.highest_price_since_entry[symbol] = bid
            else:
                self.highest_price_since_entry[symbol] = max(
                    self.highest_price_since_entry[symbol], bid
                )
            
            # Calculate profit
            profit = bid - entry_price
            
            # Take profit at target
            if bid >= take_profit_price:
                self.last_trade_index[symbol] = current_index
                del self.highest_price_since_entry[symbol]
                return "SELL", position_qty
            
            # Trailing stop: Once profit exceeds trigger, protect gains
            if profit >= self.trailing_stop_trigger * atr_proxy:
                # Trail from highest price instead of entry
                trailing_stop = self.highest_price_since_entry[symbol] - (0.75 * atr_proxy)
                if bid <= trailing_stop:
                    self.last_trade_index[symbol] = current_index
                    del self.highest_price_since_entry[symbol]
                    return "SELL", position_qty
            else:
                # Initial stop loss (tighter than before)
                if bid <= initial_stop_loss:
                    self.last_trade_index[symbol] = current_index
                    del self.highest_price_since_entry[symbol]
                    return "SELL", position_qty
            
            # Early exit on strong reversal signals
            if roc_short < -0.003 and rsi_val < 40:
                self.last_trade_index[symbol] = current_index
                del self.highest_price_since_entry[symbol]
                return "SELL", position_qty
            
            # Trend break exit (stronger condition)
            if bid < sma_20 and roc_medium < -0.001:
                self.last_trade_index[symbol] = current_index
                del self.highest_price_since_entry[symbol]
                return "SELL", position_qty

        return "HOLD", 0
