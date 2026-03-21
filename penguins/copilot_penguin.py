# penguins/copilot_penguin.py
from penguins.base_penguin import BasePenguin
from indicators.momentum import rsi, roc, sma


class CopilotPenguin(BasePenguin):
    LOOKBACK_BARS = 120  # Enough history for regime + short-term timing
    
    def __init__(self):
        super().__init__("CopilotPenguin")
        self.entry_bar = {}
        self.highest_price_since_entry = {}
        self.entry_mode = {}

        self.min_bars = 55
        self.max_spread_pct = 1.8
        self.max_holding_bars = 48
        self.max_position_size = 2

    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        """Adaptive hybrid: buy RSI pullbacks with regime-aware exits."""
        if bid <= 0 or ask <= 0:
            return "HOLD", 0

        if len(mid_prices) < self.min_bars:
            return "HOLD", 0

        # Avoid illiquid names completely
        spread_pct = (ask - bid) / bid * 100 if bid > 0 else 0
        if spread_pct > self.max_spread_pct:
            return "HOLD", 0

        # Core indicators
        rsi_fast = rsi(mid_prices, period=5)
        rsi_val = rsi(mid_prices, period=14)
        roc_short = roc(mid_prices, period=5)
        roc_long = roc(mid_prices, period=20)

        sma_20 = sma(mid_prices, 20)
        sma_50 = sma(mid_prices, 50)
        price = mid_prices[-1]
        recent_20 = mid_prices[-20:]
        range_20 = max(recent_20) - min(recent_20)
        range_pct = (range_20 / price) if price > 0 else 0

        is_trending = price > sma_50 and sma_20 > sma_50 and roc_long > 0.01
        is_weak_tape = roc_long < -0.01 or price < sma_50 * 0.985

        position_qty = portfolio.get_position(symbol)
        has_position = position_qty > 0
        current_index = len(mid_prices)

        def _cleanup_state():
            self.entry_bar.pop(symbol, None)
            self.highest_price_since_entry.pop(symbol, None)
            self.entry_mode.pop(symbol, None)

        if not has_position:
            oversold_threshold = 38 if is_trending else (26 if is_weak_tape else 31)
            dip_signal = rsi_val <= oversold_threshold and roc_short < 0
            trend_pullback = is_trending and rsi_val < 46 and roc_short < 0

            if dip_signal or trend_pullback:
                conviction = 0
                if rsi_val <= oversold_threshold - 4:
                    conviction += 1
                if rsi_fast < 20:
                    conviction += 1
                if range_pct < 0.10:
                    conviction += 1

                target_qty = 1 + int(conviction >= 2)
                target_qty = min(target_qty, self.max_position_size)
                affordable_qty = int(portfolio.cash // ask)
                buy_qty = min(target_qty, affordable_qty)

                if buy_qty > 0:
                    self.entry_bar[symbol] = current_index
                    self.highest_price_since_entry[symbol] = bid
                    self.entry_mode[symbol] = "trend_pullback" if trend_pullback else "mean_revert"
                    return "BUY", buy_qty

            return "HOLD", 0

        if has_position:
            entry_price = portfolio.cost_basis.get(symbol, 0.0)
            if entry_price <= 0:
                return "HOLD", 0

            bars_held = current_index - self.entry_bar.get(symbol, current_index)
            pnl_pct = ((bid - entry_price) / entry_price) if entry_price > 0 else 0
            mode = self.entry_mode.get(symbol, "mean_revert")

            self.highest_price_since_entry[symbol] = max(
                self.highest_price_since_entry.get(symbol, bid),
                bid,
            )

            if bars_held >= self.max_holding_bars:
                _cleanup_state()
                return "SELL", position_qty

            stop_loss = -0.018 if mode == "mean_revert" else -0.022
            if pnl_pct <= stop_loss:
                _cleanup_state()
                return "SELL", position_qty

            if rsi_val >= 71:
                _cleanup_state()
                return "SELL", position_qty

            profit_target = 0.012 if mode == "mean_revert" else 0.018
            if pnl_pct >= profit_target and rsi_val >= 56:
                _cleanup_state()
                return "SELL", position_qty

            if is_weak_tape and pnl_pct > 0 and rsi_val >= 52:
                _cleanup_state()
                return "SELL", position_qty

            if pnl_pct > 0.008:
                trail_gap = 0.007 if is_trending else 0.005
                trailing_stop = self.highest_price_since_entry[symbol] * (1 - trail_gap)
                if bid <= trailing_stop:
                    _cleanup_state()
                    return "SELL", position_qty

        return "HOLD", 0
