# penguins/careful_trend_penguin.py
from penguins.base_penguin import BasePenguin


class CarefulTrendPenguin(BasePenguin):
    def __init__(self, window_minutes=5, buy_threshold=4, sell_threshold=3):
        super().__init__("CarefulTrendPenguin")
        self.window_minutes = window_minutes
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold

    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        """
        Buy 1 if the stock rose in at least buy_threshold of the last
        window_minutes minutes. Sell all if it fell in at least sell_threshold
        of the last window_minutes minutes.
        """
        if bid <= 0 or ask <= 0:
            return "HOLD", 0

        # Need window_minutes changes, which requires window_minutes + 1 prices
        if len(mid_prices) < self.window_minutes + 1:
            return "HOLD", 0

        recent_window = mid_prices[-(self.window_minutes + 1) :]
        changes = [
            recent_window[i + 1] - recent_window[i]
            for i in range(len(recent_window) - 1)
        ]
        up_minutes = sum(1 for change in changes if change > 0)
        down_minutes = sum(1 for change in changes if change < 0)

        if up_minutes >= self.buy_threshold:
            max_affordable = int(portfolio.cash // ask)
            if max_affordable >= 1:
                return "BUY", 1
            return "HOLD", 0

        if down_minutes >= self.sell_threshold:
            qty = portfolio.get_position(symbol)
            if qty > 0:
                return "SELL", qty
            return "HOLD", 0

        return "HOLD", 0
