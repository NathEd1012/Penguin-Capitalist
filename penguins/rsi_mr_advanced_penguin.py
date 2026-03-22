from penguins.base_penguin import BasePenguin
from indicators.momentum import rsi, sma


class RSIMeanReversionAdvancedPenguin(BasePenguin):
    LOOKBACK_BARS = 60  # RSI + optional weak collapse guard context

    def __init__(
        self,
        rsi_period=14,
        oversold=30,
        overbought=70,
        stop_loss_pct=0.10,
        max_buy_size=3,
        use_collapse_filter=False,
        collapse_sma_period=50,
        collapse_threshold_pct=0.12,
    ):
        super().__init__("RSI MeanReversion Advanced")
        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought
        self.stop_loss_pct = stop_loss_pct
        self.max_buy_size = max_buy_size
        self.use_collapse_filter = use_collapse_filter
        self.collapse_sma_period = collapse_sma_period
        self.collapse_threshold_pct = collapse_threshold_pct

        # Entry basis is only needed for optional hard-stop risk control.
        self.entry_price = {}

    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        if bid <= 0 or ask <= 0:
            return "HOLD", 0

        min_bars = max(self.rsi_period + 1, self.collapse_sma_period)
        if len(mid_prices) < min_bars:
            return "HOLD", 0

        # Mean reversion edge: enter early while RSI is still oversold.
        rsi_now = rsi(mid_prices, self.rsi_period)
        if rsi_now is None:
            return "HOLD", 0

        price_now = mid_prices[-1]
        qty = portfolio.get_position(symbol)
        cash = portfolio.cash

        # Keep optional hard-stop state in sync.
        if qty <= 0:
            self.entry_price.pop(symbol, None)
        else:
            if symbol not in self.entry_price:
                self.entry_price[symbol] = portfolio.cost_basis.get(symbol, ask)

            # Optional, conservative hard stop only.
            if self.stop_loss_pct is not None and self.stop_loss_pct > 0:
                entry = self.entry_price[symbol]
                if entry > 0 and bid <= entry * (1 - self.stop_loss_pct):
                    return "SELL", qty

        # Exit remains simple: RSI overbought -> sell full position.
        if qty > 0 and rsi_now > self.overbought:
            return "SELL", qty

        # Optional weak filter: block entries only in clear collapses.
        if self.use_collapse_filter:
            sma_now = sma(mid_prices, self.collapse_sma_period)
            if sma_now is not None and sma_now > 0:
                collapse_floor = sma_now * (1.0 - self.collapse_threshold_pct)
                if price_now < collapse_floor:
                    return "HOLD", 0

        # Entry sizing by oversold depth, capped to avoid runaway exposure.
        if rsi_now < self.oversold and cash >= ask:
            depth = self.oversold - rsi_now
            if depth >= 15:
                desired_qty = 3
            elif depth >= 7:
                desired_qty = 2
            else:
                desired_qty = 1

            desired_qty = min(desired_qty, self.max_buy_size)
            affordable_qty = int(cash // ask)
            buy_qty = min(desired_qty, affordable_qty)

            if buy_qty > 0:
                # Keep first-entry basis so optional hard stop remains conservative.
                if qty <= 0:
                    self.entry_price[symbol] = ask
                return "BUY", buy_qty

        return "HOLD", 0

# Alias for backward compatibility with existing imports.
class RSIMeanReversionPenguin(RSIMeanReversionAdvancedPenguin):
    """Backward-compatible alias for the advanced RSI mean-reversion strategy."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "RSI MeanReversion Advanced"


class MeanReversionPenguin(RSIMeanReversionAdvancedPenguin):
    """Backward-compatible alias used by configuration imports."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "RSI MeanReversion"
