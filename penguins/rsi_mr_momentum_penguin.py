from penguins.base_penguin import BasePenguin
from indicators.momentum import rsi, roc, sma


class RSIMeanReversionMomentumPenguin(BasePenguin):
    """
    RSI Mean Reversion with Market State Detection.
    Adjusts oversold/overbought boundaries based on 3 market states:
    - RISING: Momentum positive, more aggressive thresholds
    - FALLING: Momentum negative, more defensive thresholds
    - HOLDING: Momentum neutral, standard thresholds
    """
    LOOKBACK_BARS = 50  # Need more history for momentum calculation
    
    def __init__(self, rsi_period=14, momentum_period=10):
        super().__init__("RSIMeanReversionMomentumPenguin")
        self.rsi_period = rsi_period
        self.momentum_period = momentum_period
        
        # Base RSI thresholds (HOLDING state)
        self.base_oversold = 30
        self.base_overbought = 70
        
        # Current state
        self.current_state = "HOLDING"  # RISING, FALLING, HOLDING
        self.oversold = self.base_oversold
        self.overbought = self.base_overbought
        
        # State thresholds for momentum
        self.momentum_threshold = 0.01  # +/- 1% ROC threshold for state change
    
    def _detect_market_state(self, prices):
        """Detect market state using momentum (ROC) and SMA."""
        if len(prices) < max(self.momentum_period + 1, 20):
            return "HOLDING"
        
        # Calculate Rate of Change (momentum)
        momentum = roc(prices, self.momentum_period)
        
        # Calculate SMA to confirm trend
        sma_short = sma(prices[-20:], 5)
        sma_long = sma(prices[-20:], 20)
        
        # Determine state based on momentum
        if momentum > self.momentum_threshold and sma_short > sma_long:
            return "RISING"
        elif momentum < -self.momentum_threshold and sma_short < sma_long:
            return "FALLING"
        else:
            return "HOLDING"
    
    def _set_thresholds_for_state(self, state):
        """Set RSI thresholds based on market state."""
        if state == "RISING":
            # Uptrend: More aggressive, wider RSI range (catch momentum trades)
            # Looser oversold (easier to buy), tighter overbought (take profits quickly)
            self.oversold = 25      # More generous buy signal
            self.overbought = 65    #  Holder for bigger gains in uptrend
        
        elif state == "FALLING":
            # Downtrend: More defensive, narrow RSI range (avoid losses)
            # Tighter oversold (harder to buy), tighter overbought (eager to sell)
            self.oversold = 35      # More strict buy signal
            self.overbought = 75    #Sell sooner in uptrend

        else:  # HOLDING
            # Neutral market: Use standard mean reversion thresholds
            self.oversold = self.base_oversold
            self.overbought = self.base_overbought

    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        if bid <= 0 or ask <= 0:
            return "HOLD", 0

        if len(mid_prices) < self.rsi_period + 1:
            return "HOLD", 0

        # Detect current market state and adjust thresholds
        self.current_state = self._detect_market_state(mid_prices)
        self._set_thresholds_for_state(self.current_state)

        # Calculate RSI
        rsi_val = rsi(mid_prices, self.rsi_period)
        qty = portfolio.get_position(symbol)
        cash = portfolio.cash

        action = "HOLD"
        trade_qty = 0

        # Buy signal: RSI below oversold threshold and we have cash
        if rsi_val < self.oversold and cash >= ask:
            action = "BUY"
            trade_qty = 1
        
        # Sell signal: RSI above overbought threshold and we hold position
        elif rsi_val > self.overbought and qty > 0 and bid > 0:
            action = "SELL"
            trade_qty = qty

        return action, trade_qty
