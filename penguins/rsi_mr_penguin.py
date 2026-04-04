from penguins.base_penguin import BasePenguin
from indicators.momentum import rsi


class RSIMeanReversionPenguin(BasePenguin):
    LOOKBACK_BARS = 30  # Only needs last 30 bars for RSI calculation
    
    def __init__(self, rsi_period=14, oversold=30, overbought=70):
        super().__init__("RSIMeanReversionPenguin")
        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought

    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        if bid <= 0 or ask <= 0:
            return "HOLD", 0

        if len(mid_prices) < self.rsi_period + 1:
            return "HOLD", 0

        rsi_val = rsi(mid_prices, self.rsi_period)
        qty = portfolio.get_position(symbol)
        cash = portfolio.cash

        if rsi_val < self.oversold and cash >= ask: # and qty <= 0
            return "BUY", 1
        elif rsi_val > self.overbought and qty > 0 and bid > 0:
            return "SELL", qty

        return "HOLD", 0


class _RSIMeanReversionStrictBase(RSIMeanReversionPenguin):
    """RSI variant that mirrors base behavior with optional buy cooldown."""

    def __init__(self, name, rsi_period, oversold, overbought, cooldown_bars):
        super().__init__(rsi_period=rsi_period, oversold=oversold, overbought=overbought)
        self.name = name
        self.cooldown_bars = cooldown_bars
        self._last_buy_bar = {}

    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        if bid <= 0 or ask <= 0:
            return "HOLD", 0

        if len(mid_prices) < self.rsi_period + 1:
            return "HOLD", 0

        rsi_val = rsi(mid_prices, self.rsi_period)
        qty = portfolio.get_position(symbol)
        cash = portfolio.cash
        current_bar = len(mid_prices)

        if rsi_val < self.oversold and cash >= ask:
            if self.cooldown_bars > 0:
                last_buy_bar = self._last_buy_bar.get(symbol)
                if last_buy_bar is not None and (current_bar - last_buy_bar) < self.cooldown_bars:
                    return "HOLD", 0
            self._last_buy_bar[symbol] = current_bar
            return "BUY", 1
        elif rsi_val > self.overbought and qty > 0 and bid > 0:
            return "SELL", qty

        return "HOLD", 0


class RSIMeanReversionPenguinStrict1(_RSIMeanReversionStrictBase):
    """Strict variant 1: looser than before, still stricter than original."""

    def __init__(self):
        super().__init__(
            name="RSIMeanReversionPenguinStrict1",
            rsi_period=14,
            oversold=30,
            overbought=70,
            cooldown_bars=0,
        )


class RSIMeanReversionPenguinStrict2(_RSIMeanReversionStrictBase):
    """Strict variant 2: midpoint between Strict1 and prior Strict2 settings."""

    def __init__(self):
        super().__init__(
            name="RSIMeanReversionPenguinStrict2",
            rsi_period=14,
            oversold=17,
            overbought=71,
            cooldown_bars=0,
        )
