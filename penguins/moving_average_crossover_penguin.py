from penguins.base_penguin import BasePenguin
from indicators.statsistics import sma, ema


class MovingAverageCrossoverPenguin(BasePenguin):
    def __init__(self, fast_period=5, slow_period=20, use_ema=False):
        super().__init__("Moving Average Crossover")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.use_ema = use_ema
        self.ma_func = ema if use_ema else sma
        self.prev_signal = None  # To avoid overtrading

    def decide(self, symbol, prices, portfolio):
        if len(prices) < self.slow_period + 1:
            return "HOLD", 0

        fast_ma = self.ma_func(prices, self.fast_period)
        slow_ma = self.ma_func(prices, self.slow_period)

        # Previous MAs
        prev_prices = prices[:-1]
        if len(prev_prices) >= self.slow_period:
            prev_fast = self.ma_func(prev_prices, self.fast_period)
            prev_slow = self.ma_func(prev_prices, self.slow_period)
        else:
            return "HOLD", 0

        # Crossover signals
        current_cross = fast_ma - slow_ma
        prev_cross = prev_fast - prev_slow

        qty = portfolio.get_position(symbol)
        cash = portfolio.cash

        if current_cross > 0 and prev_cross <= 0:  # Bullish crossover
            if qty <= 0 and cash >= prices[-1]:  # Not long, can buy
                return "BUY", 1
        elif current_cross < 0 and prev_cross >= 0:  # Bearish crossover
            if qty > 0:  # Long, sell
                return "SELL", qty

        return "HOLD", 0
