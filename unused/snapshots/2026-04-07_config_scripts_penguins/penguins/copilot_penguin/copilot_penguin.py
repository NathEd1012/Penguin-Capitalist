"""
CopilotPenguin: Modular trend-following penguin with decision logging and tactic swapping.
"""
from penguins.base_penguin import BasePenguin
from penguins.copilot_penguin.decision_logger import get_logger, DecisionLogger
from penguins.copilot_penguin.tactics import TacticV1


class CopilotPenguin(BasePenguin):
    """
    Modular trading penguin that:
    - Uses swappable tactics for strategy evolution
    - Logs every decision with full reasoning
    - Tracks indicator values for analysis
    - Allows easy evaluation and improvement
    """
    
    def __init__(self, tactic=None):
        super().__init__("CopilotPenguin")
        
        # Tactic system
        self.tactic = tactic or TacticV1()
        self.logger = DecisionLogger(f"copilot_penguin_decisions.json")
        self.logger.current_tactic = self.tactic.name
        self.logger.tactic_version = self.tactic.version
        
        # Track stats
        self.total_decisions = 0
        self.buy_count = 0
        self.sell_count = 0
        self.hold_count = 0

    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        """
        Make a decision using current tactic and log it.
        """
        # Get decision from tactic
        decision, qty, checks = self.tactic.decide(symbol, mid_prices, bid, ask, portfolio)
        
        # Log the decision
        log = self.logger.log_decision(symbol, len(mid_prices), decision)
        log.price = bid if decision == "SELL" else ask if decision == "BUY" else (bid + ask) / 2
        log.quantity = qty
        log.checks = checks
        log.portfolio_value = portfolio.total_value
        
        # Add indicator values for analysis
        if len(mid_prices) >= 50:
            from indicators.momentum import rsi, roc
            try:
                log.indicators = {
                    "price": mid_prices[-1],
                    "sma_20": sum(mid_prices[-20:]) / 20,
                    "sma_50": sum(mid_prices[-50:]) / 50,
                    "rsi": rsi(mid_prices, n=14),
                    "roc_3": roc(mid_prices, n=3),
                    "roc_7": roc(mid_prices, n=7),
                    "atr_proxy": max(mid_prices[-10:]) - min(mid_prices[-10:]),
                }
            except:
                pass
        
        # Build reasoning
        reasoning_parts = []
        if decision == "BUY":
            if checks.get("uptrend"):
                reasoning_parts.append("uptrend")
            if checks.get("roc_medium_ok"):
                reasoning_parts.append(f"strong momentum (ROC7={log.indicators.get('roc_7', 0):.2%})")
            if checks.get("rsi_rising"):
                reasoning_parts.append("RSI rising")
            if checks.get("price_not_extended"):
                reasoning_parts.append("price not extended")
            if checks.get("has_cash"):
                reasoning_parts.append(f"cash available (qty={qty})")
            log.reasoning = "BUY: " + ", ".join(reasoning_parts)
        
        elif decision == "SELL":
            if checks.get("take_profit_hit"):
                entry_price = portfolio.positions[symbol].avg_price if symbol in portfolio.positions else ask
                pnl = (log.price - entry_price) * qty
                log.reasoning = f"SELL: Take profit hit (+${pnl:.2f})"
            elif checks.get("stop_loss_hit"):
                entry_price = portfolio.positions[symbol].avg_price if symbol in portfolio.positions else ask
                pnl = (log.price - entry_price) * qty
                log.reasoning = f"SELL: Stop loss hit (${pnl:.2f})"
            elif checks.get("trend_broken"):
                log.reasoning = "SELL: Trend broken (price < SMA20 + negative ROC)"
            else:
                log.reasoning = "SELL: Manual exit"
        
        else:  # HOLD
            reasons = []
            if not checks.get("valid_price"):
                reasons.append("invalid price")
            elif not checks.get("sufficient_bars"):
                reasons.append("insufficient history")
            elif not checks.get("uptrend"):
                reasons.append("no uptrend")
            elif not checks.get("roc_medium_ok"):
                reasons.append(f"weak momentum (ROC7={log.indicators.get('roc_7', 0):.2%})")
            elif not checks.get("rsi_in_range"):
                reasons.append(f"RSI out of range ({log.indicators.get('rsi', 0):.0f})")
            elif not checks.get("price_not_extended"):
                reasons.append("price too extended")
            elif not checks.get("no_cooldown"):
                reasons.append("in cooldown")
            elif checks.get("has_position"):
                reasons.append("already holding")
            
            if reasons:
                log.reasoning = "HOLD: " + ", ".join(reasons)
            else:
                log.reasoning = "HOLD: monitoring"
        
        # Update position tracking
        if symbol in portfolio.positions:
            log.position_after = portfolio.positions[symbol].qty
        else:
            log.position_after = 0
        
        # Track stats
        self.total_decisions += 1
        if decision == "BUY":
            self.buy_count += 1
        elif decision == "SELL":
            self.sell_count += 1
        else:
            self.hold_count += 1
        
        return decision, qty

    def switch_tactic(self, new_tactic):
        """Switch to a different tactic (for testing improvements)."""
        self.tactic = new_tactic
        self.logger.current_tactic = new_tactic.name
        self.logger.tactic_version = new_tactic.version

    def save_decisions_log(self, path: str):
        """Save decision log to file."""
        self.logger.save(path)

    def get_summary(self):
        """Get summary of all decisions."""
        return self.logger.get_summary()
