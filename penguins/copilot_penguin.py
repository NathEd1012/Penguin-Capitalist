# penguins/copilot_penguin.py
from penguins.base_penguin import BasePenguin
from indicators.momentum import rsi, roc


class CopilotPenguin(BasePenguin):
    def __init__(self):
        super().__init__("CopilotPenguin")
        self.entry_price = {}  # Track entry prices by symbol
        self.last_trade_index = {}  # Track last trade index by symbol

        # Strategy parameters
        self.min_bars = 20  # Reduced from 50
        self.cooldown_bars = 3  # Reduced from 5
        self.max_spread_pct = 2.0  # Increased from 1.0
        self.min_trend_roc = 0.0001  # Much more relaxed from 0.005
        self.stop_loss_atr_mult = 1.5
        self.take_profit_atr_mult = 2.0

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

        # Cooldown after last trade for this symbol
        current_index = len(mid_prices)
        last_trade_index = self.last_trade_index.get(symbol, -999)
        in_cooldown = (current_index - last_trade_index) <= self.cooldown_bars

        # ========== BUY SIGNALS ==========
        # Very relaxed entry: Just need positive momentum + RSI not extreme
        buy_signal = roc_medium > self.min_trend_roc and 30 <= rsi_val <= 80

        if buy_signal and not has_position and not in_cooldown:
            # Position size based on volatility proxy
            qty = 1 if atr_proxy / price > 0.02 else 2
            if portfolio.cash >= ask:
                self.last_trade_index[symbol] = current_index
                self.entry_price[symbol] = ask
                return "BUY", qty
            return "HOLD", 0

        # ========== SELL SIGNALS ==========
        # Exit conditions:
        # 1. Volatility-based take profit
        # 2. Volatility-based stop loss
        # 3. Trend breaks (price below SMA20)

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

            # Trend break exit
            if bid < sma_20 and roc_short < 0:
                self.last_trade_index[symbol] = current_index
                return "SELL", position_qty

        return "HOLD", 0
