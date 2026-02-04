# penguins/careful_trend_penguin.py
from penguins.base_penguin import BasePenguin


class CarefulTrendPenguin(BasePenguin):
    def __init__(self, buy_consecutive=3, sell_consecutive=2):
        super().__init__("CarefulTrendPenguin")
        self.buy_consecutive = buy_consecutive
        self.sell_consecutive = sell_consecutive

    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        """
        Buy when stock has risen for buy_consecutive consecutive minutes.
        Sell when stock has fallen for sell_consecutive consecutive minutes.
        """
        if len(mid_prices) < max(self.buy_consecutive, self.sell_consecutive):
            return "HOLD", 0

        # Check last buy_consecutive bars for buy signal
        recent_buy = mid_prices[-self.buy_consecutive :]
        all_increasing = all(
            recent_buy[i] < recent_buy[i + 1] for i in range(len(recent_buy) - 1)
        )
        if all_increasing:
            increase = recent_buy[-1] - recent_buy[0]
            qty = max(1, int(increase / recent_buy[-1] * 100))
            return "BUY", qty

        # Check last sell_consecutive bars for sell signal
        recent_sell = mid_prices[-self.sell_consecutive :]
        all_decreasing = all(
            recent_sell[i] > recent_sell[i + 1] for i in range(len(recent_sell) - 1)
        )
        if all_decreasing:
            qty = portfolio.get_position(symbol)
            if qty > 0:
                return "SELL", qty
            else:
                return "HOLD", 0

        return "HOLD", 0
