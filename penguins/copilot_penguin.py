# penguins/copilot_penguin.py
from penguins.base_penguin import BasePenguin
from indicators.momentum import rsi, roc, sma


class CopilotPenguin(BasePenguin):
    LOOKBACK_BARS = 120  # Enough history for regime + short-term timing
    
    def __init__(self):
        super().__init__("CopilotPenguin")
        self.entry_bar = {}
        self.last_exit_bar = {}
        self.highest_price_since_entry = {}
        self.entry_mode = {}
        self.entry_momentum_trust = {}

        self.min_bars = 80
        self.max_spread_pct = 1.8
        self.max_holding_bars = 60
        self.min_holding_bars = 3
        self.cooldown_bars = 8
        self.max_position_size = 1

    @staticmethod
    def _clamp(value, lo, hi):
        return max(lo, min(hi, value))

    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        """Adaptive hybrid: dynamically trust momentum vs mean reversion by regime."""
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

        trend_strength = 0.0
        if price > sma_20:
            trend_strength += 0.30
        if sma_20 > sma_50:
            trend_strength += 0.25
        trend_component = (roc_long - 0.002) / 0.04
        if trend_component < 0.0:
            trend_component = 0.0
        elif trend_component > 1.0:
            trend_component = 1.0
        trend_strength += 0.45 * trend_component

        weakness = 0.0
        if price < sma_20:
            weakness += 0.25
        if sma_20 < sma_50:
            weakness += 0.25
        weakness_component = (-roc_long - 0.002) / 0.04
        if weakness_component < 0.0:
            weakness_component = 0.0
        elif weakness_component > 1.0:
            weakness_component = 1.0
        weakness += 0.50 * weakness_component

        flatness = 1.0 - (abs(roc_long) / 0.02)
        if flatness < 0.0:
            flatness = 0.0
        elif flatness > 1.0:
            flatness = 1.0

        momentum_trust = 0.55 + (0.45 * trend_strength) - (0.55 * weakness) - (0.10 * flatness)
        if momentum_trust < 0.10:
            momentum_trust = 0.10
        elif momentum_trust > 0.90:
            momentum_trust = 0.90
        mean_reversion_trust = 1.0 - momentum_trust

        is_trending = trend_strength >= 0.55
        is_weak_tape = weakness >= 0.55

        position_qty = portfolio.get_position(symbol)
        has_position = position_qty > 0
        current_index = len(mid_prices)

        def _cleanup_state():
            self.entry_bar.pop(symbol, None)
            self.highest_price_since_entry.pop(symbol, None)
            self.entry_mode.pop(symbol, None)
            self.entry_momentum_trust.pop(symbol, None)
            self.last_exit_bar[symbol] = current_index

        if not has_position:
            bars_since_exit = current_index - self.last_exit_bar.get(symbol, -10_000)
            if bars_since_exit < self.cooldown_bars:
                return "HOLD", 0

            oversold_threshold = 24 + (12 * mean_reversion_trust)
            if is_weak_tape:
                oversold_threshold -= 2

            mean_revert_score = 0
            if rsi_val <= oversold_threshold:
                mean_revert_score += 1
            if rsi_fast < 22:
                mean_revert_score += 1
            if roc_short < -0.003:
                mean_revert_score += 1
            if range_pct < 0.11:
                mean_revert_score += 1
            if flatness > 0.35 or is_weak_tape:
                mean_revert_score += 1

            momentum_score = 0
            if trend_strength > 0.55:
                momentum_score += 1
            if roc_short > 0.005:
                momentum_score += 1
            if price > sma_20:
                momentum_score += 1
            if 52 <= rsi_val <= 68:
                momentum_score += 1
            if roc_long > 0.010:
                momentum_score += 1

            mean_revert_conf = (mean_revert_score / 5.0) * mean_reversion_trust
            momentum_conf = (momentum_score / 5.0) * momentum_trust
            best_conf = max(mean_revert_conf, momentum_conf)

            if best_conf >= 0.50:
                if momentum_conf > mean_revert_conf + 0.05:
                    mode = "momentum"
                    confidence = momentum_conf
                elif mean_revert_conf > momentum_conf + 0.05:
                    mode = "mean_revert"
                    confidence = mean_revert_conf
                else:
                    mode = "blended"
                    confidence = best_conf

                if mode == "momentum" and momentum_score < 4:
                    return "HOLD", 0
                if mode != "momentum" and mean_revert_score < 4:
                    return "HOLD", 0

                conviction = 0
                if confidence >= 0.50:
                    conviction += 1
                if confidence >= 0.65:
                    conviction += 1
                if mode == "momentum" and roc_short > 0.01:
                    conviction += 1
                if mode != "momentum" and rsi_val <= oversold_threshold - 3:
                    conviction += 1

                target_qty = 1 + int(conviction >= 2)
                target_qty = min(target_qty, self.max_position_size)
                affordable_qty = int(portfolio.cash // ask)
                buy_qty = min(target_qty, affordable_qty)

                if buy_qty > 0:
                    self.entry_bar[symbol] = current_index
                    self.highest_price_since_entry[symbol] = bid
                    self.entry_mode[symbol] = mode
                    self.entry_momentum_trust[symbol] = momentum_trust
                    return "BUY", buy_qty

            return "HOLD", 0

        if has_position:
            entry_price = portfolio.cost_basis.get(symbol, 0.0)
            if entry_price <= 0:
                return "HOLD", 0

            bars_held = current_index - self.entry_bar.get(symbol, current_index)
            pnl_pct = ((bid - entry_price) / entry_price) if entry_price > 0 else 0
            mode = self.entry_mode.get(symbol, "blended")
            entry_trust = self.entry_momentum_trust.get(symbol, momentum_trust)

            self.highest_price_since_entry[symbol] = max(
                self.highest_price_since_entry.get(symbol, bid),
                bid,
            )

            if bars_held >= self.max_holding_bars:
                _cleanup_state()
                return "SELL", position_qty

            if bars_held < self.min_holding_bars and pnl_pct > -0.010:
                return "HOLD", 0

            if mode == "momentum":
                stop_loss = -0.020 - (0.010 * entry_trust)
            elif mode == "mean_revert":
                stop_loss = -0.014 - (0.006 * (1.0 - entry_trust))
            else:
                stop_loss = -0.018

            if pnl_pct <= stop_loss:
                _cleanup_state()
                return "SELL", position_qty

            if mode == "momentum" and rsi_val >= 74 and pnl_pct > 0:
                _cleanup_state()
                return "SELL", position_qty

            if mode != "momentum" and rsi_val >= 63:
                _cleanup_state()
                return "SELL", position_qty

            if mode == "momentum":
                profit_target = 0.018 + (0.016 * entry_trust)
            elif mode == "mean_revert":
                profit_target = 0.007 + (0.006 * (1.0 - entry_trust))
            else:
                profit_target = 0.014

            if pnl_pct >= profit_target and rsi_val >= 56:
                _cleanup_state()
                return "SELL", position_qty

            if mode == "momentum" and momentum_trust < 0.35 and pnl_pct > 0:
                _cleanup_state()
                return "SELL", position_qty

            if mode != "momentum" and is_weak_tape and pnl_pct > 0 and rsi_val >= 52:
                _cleanup_state()
                return "SELL", position_qty

            if pnl_pct > 0.008:
                if mode == "momentum":
                    trail_gap = 0.006 + (0.008 * entry_trust)
                elif mode == "mean_revert":
                    trail_gap = 0.004 + (0.003 * (1.0 - entry_trust))
                else:
                    trail_gap = 0.006
                trailing_stop = self.highest_price_since_entry[symbol] * (1 - trail_gap)
                if bid <= trailing_stop:
                    _cleanup_state()
                    return "SELL", position_qty

        return "HOLD", 0
