# penguins/careful_trend_penguin.py
from penguins.base_penguin import BasePenguin


class CarefulTrendPenguin(BasePenguin):
    def __init__(self, buy_consecutive=3, sell_consecutive=2):
        super().__init__("CarefulTrendPenguin")
        self.buy_consecutive = buy_consecutive
        self.sell_consecutive = sell_consecutive

    def decide(self, symbol, prices, portfolio):
        """
        Buy when stock has risen for buy_consecutive consecutive minutes.
        Sell when stock has fallen for sell_consecutive consecutive minutes.
        """
        if len(prices) < max(self.buy_consecutive, self.sell_consecutive):
            return "HOLD", 0

        # Check last buy_consecutive bars for buy signal
        recent_buy = prices[-self.buy_consecutive :]
        all_increasing = all(
            recent_buy[i] < recent_buy[i + 1] for i in range(len(recent_buy) - 1)
        )
        if all_increasing:
            increase = recent_buy[-1] - recent_buy[0]
            qty = max(1, int(increase / recent_buy[-1] * 100))
            return "BUY", qty

        # Check last sell_consecutive bars for sell signal
        recent_sell = prices[-self.sell_consecutive :]
        all_decreasing = all(
            recent_sell[i] > recent_sell[i + 1] for i in range(len(recent_sell) - 1)
        )
        if all_decreasing:
            return "SELL", 1  # sell 1 for now

        return "HOLD", 0
