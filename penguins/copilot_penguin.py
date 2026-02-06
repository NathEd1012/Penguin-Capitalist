# penguins/copilot_penguin.py
from penguins.base_penguin import BasePenguin
from indicators.momentum import rsi, roc


class CopilotPenguin(BasePenguin):
    def __init__(self):
        super().__init__("CopilotPenguin")
        self.position_size = 1  # Track position size
        self.entry_price = {}  # Track entry prices by symbol

    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        """
        Advanced hybrid strategy combining:
        - RSI for mean reversion (overbought/oversold)
        - Rate of Change (ROC) for momentum confirmation
        - Volatility-aware position sizing
        - Trend filtering
        """
        if len(mid_prices) < 20:
            return "HOLD", 0

        # Calculate indicators
        rsi_val = rsi(mid_prices, n=14)
        roc_short = roc(mid_prices, n=3)  # Short-term momentum
        roc_medium = roc(mid_prices, n=7)  # Medium-term momentum
        
        # Trend detection: Is price above 20-SMA?
        sma_20 = sum(mid_prices[-20:]) / 20
        price = mid_prices[-1]
        is_uptrend = price > sma_20
        is_downtrend = price < sma_20
        
        # Volatility (simple measure based on price range)
        recent_high = max(mid_prices[-10:])
        recent_low = min(mid_prices[-10:])
        volatility = (recent_high - recent_low) / recent_low if recent_low > 0 else 0
        
        # Check if we have a position
        has_position = symbol in portfolio.positions and portfolio.positions[symbol].qty > 0
        
        # ========== BUY SIGNALS ==========
        # Buy conditions:
        # 1. RSI oversold (< 35) + positive momentum + in uptrend
        # 2. Strong positive ROC + RSI not overbought
        # 3. Price breaks above recent high (momentum)
        
        buy_signal_rsi = rsi_val < 35 and roc_short > 0 and is_uptrend
        buy_signal_momentum = roc_medium > 0.02 and rsi_val < 65
        buy_signal_breakout = price > recent_high and roc_short > 0.005
        
        if (buy_signal_rsi or buy_signal_momentum or buy_signal_breakout) and not has_position:
            # Size position based on volatility (smaller in volatile markets)
            qty = 1 if volatility > 0.05 else 2
            return "BUY", qty
        
        # ========== SELL SIGNALS ==========
        # Sell conditions:
        # 1. Take profit: Price up 2%+ from entry with overbought RSI
        # 2. Stop loss: Price down 1% from entry
        # 3. Strong bearish momentum
        # 4. Price breaks below support
        
        if has_position:
            entry_price = portfolio.positions[symbol].avg_price
            current_pnl_pct = (price - entry_price) / entry_price if entry_price > 0 else 0
            
            # Take profit condition
            if current_pnl_pct > 0.02 and rsi_val > 70:
                qty = portfolio.positions[symbol].qty
                return "SELL", qty
            
            # Stop loss condition
            if current_pnl_pct < -0.01:
                qty = portfolio.positions[symbol].qty
                return "SELL", qty
            
            # Strong bearish momentum
            if roc_medium < -0.02 and rsi_val > 50:
                qty = portfolio.positions[symbol].qty
                return "SELL", qty
            
            # Price breaks below support
            if price < recent_low and roc_short < -0.005:
                qty = portfolio.positions[symbol].qty
                return "SELL", qty
        
        return "HOLD", 0
