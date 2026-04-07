"""
Tactic base class and Tactic v1: Strict Momentum + RSI Rising + Price Extension Filter
"""
from abc import ABC, abstractmethod
from typing import Dict, Tuple, Optional, Any
from indicators.momentum import rsi, roc


class BaseTactic(ABC):
    """Base class for different CopilotPenguin strategies."""
    
    def __init__(self, name: str, version: str):
        self.name = name
        self.version = version
        self.last_trade_index = {}  # Track last trade index by symbol
        self.entry_price = {}  # Track entry prices by symbol
        
    @abstractmethod
    def decide(self, symbol: str, mid_prices: list, bid: float, ask: float, 
               portfolio: Any) -> Tuple[str, int, Dict[str, Any]]:
        """
        Make a trade decision.
        
        Returns:
            (decision, quantity, checks_dict)
            decision: "BUY", "SELL", or "HOLD"
            quantity: number of shares (0 if HOLD)
            checks_dict: dict of all decision factors for logging
        """
        pass
    
    def get_description(self) -> str:
        """Get human-readable description of this tactic."""
        return f"{self.name} v{self.version}"


class TacticV1(BaseTactic):
    """
    Tactic v1: Strict Momentum Entry Filters
    
    Entry requirements (ALL must pass):
    - Uptrend: SMA20 > SMA50
    - Strong momentum: ROC(7) > 1.5% AND ROC(3) > 1.0%
    - RSI confirmation: 50-70 AND rising
    - Price not extended: < 95% of 50-bar high
    - Not in cooldown: 8 bars since last trade
    
    Exit on ANY:
    - Take profit: Entry + 2.5×ATR
    - Stop loss: Entry - 1.0×ATR
    - Trend break: Price < SMA20 AND ROC(3) < 0
    """
    
    def __init__(self):
        super().__init__("Momentum+RSI+Extension", "1.0")
        self.min_bars = 50
        self.cooldown_bars = 8
        self.max_spread_pct = 1.0
        self.min_trend_roc = 0.015  # 1.5%
        self.min_roc_short = 0.010  # 1.0%
        self.stop_loss_atr_mult = 1.0
        self.take_profit_atr_mult = 2.5
        
    def decide(self, symbol: str, mid_prices: list, bid: float, ask: float, 
               portfolio: Any) -> Tuple[str, int, Dict[str, Any]]:
        """Trend-following with strict entry confirmation."""
        
        checks = {
            "valid_price": False,
            "sufficient_bars": False,
            "spread_ok": False,
            "uptrend": False,
            "roc_medium_ok": False,
            "roc_short_ok": False,
            "rsi_in_range": False,
            "rsi_rising": False,
            "price_not_extended": False,
            "no_cooldown": False,
            "has_cash": False,
            "has_position": False,
            "take_profit_hit": False,
            "stop_loss_hit": False,
            "trend_broken": False,
        }
        reasoning = []
        
        # Price validation
        if bid <= 0 or ask <= 0:
            return "HOLD", 0, checks
        checks["valid_price"] = True
        
        if len(mid_prices) < self.min_bars:
            return "HOLD", 0, checks
        checks["sufficient_bars"] = True
        
        # Spread check
        spread_pct = (ask - bid) / bid * 100 if bid > 0 else 100
        if spread_pct > self.max_spread_pct:
            return "HOLD", 0, checks
        checks["spread_ok"] = True
        
        # Calculate indicators
        price = mid_prices[-1]
        sma_20 = sum(mid_prices[-20:]) / 20
        sma_50 = sum(mid_prices[-50:]) / 50
        rsi_val = rsi(mid_prices, n=14)
        rsi_prev = rsi(mid_prices[:-1], n=14) if len(mid_prices) > 5 else 0
        roc_short = roc(mid_prices, n=3)
        roc_medium = roc(mid_prices, n=7)
        
        # Volatility proxy
        recent_high = max(mid_prices[-10:])
        recent_low = min(mid_prices[-10:])
        atr_proxy = max(recent_high - recent_low, 0.01)
        
        # Uptrend check
        is_uptrend = price > sma_20 > sma_50
        checks["uptrend"] = is_uptrend
        
        # Momentum checks
        roc_medium_ok = roc_medium > self.min_trend_roc
        roc_short_ok = roc_short > self.min_roc_short
        checks["roc_medium_ok"] = roc_medium_ok
        checks["roc_short_ok"] = roc_short_ok
        
        # RSI checks
        rsi_in_range = 50 <= rsi_val <= 70
        rsi_rising = rsi_val >= rsi_prev
        checks["rsi_in_range"] = rsi_in_range
        checks["rsi_rising"] = rsi_rising
        
        # Price extension
        bar_50_high = max(mid_prices[-50:])
        bar_50_low = min(mid_prices[-50:])
        bar_50_range = bar_50_high - bar_50_low
        extension_pct = (price - bar_50_low) / bar_50_range if bar_50_range > 0 else 0.5
        price_not_extended = extension_pct < 0.95
        checks["price_not_extended"] = price_not_extended
        
        # Position check
        has_position = (
            symbol in portfolio.positions and portfolio.positions[symbol].qty > 0
        )
        position_qty = portfolio.positions[symbol].qty if has_position else 0
        checks["has_position"] = has_position
        
        # Cooldown check
        current_index = len(mid_prices)
        last_trade_index = self.last_trade_index.get(symbol, -999)
        no_cooldown = (current_index - last_trade_index) > self.cooldown_bars
        checks["no_cooldown"] = no_cooldown
        
        # ========== BUY LOGIC ==========
        buy_signal = (is_uptrend and roc_medium_ok and roc_short_ok and 
                     rsi_in_range and rsi_rising and price_not_extended)
        
        if buy_signal and not has_position and no_cooldown:
            checks["has_cash"] = portfolio.cash >= ask
            if portfolio.cash >= ask:
                qty = 1 if atr_proxy / price > 0.02 else 2
                self.last_trade_index[symbol] = current_index
                self.entry_price[symbol] = ask
                reasoning.append(f"Uptrend with strong momentum (ROC7={roc_medium:.2%}, ROC3={roc_short:.2%})")
                reasoning.append(f"RSI={rsi_val:.0f} (rising from {rsi_prev:.0f}), price at {extension_pct:.0%} of 50-bar range")
                return "BUY", qty, checks
        
        # ========== SELL LOGIC ==========
        if has_position:
            entry_price = portfolio.positions[symbol].avg_price
            take_profit_price = entry_price + self.take_profit_atr_mult * atr_proxy
            stop_loss_price = entry_price - self.stop_loss_atr_mult * atr_proxy
            
            if bid >= take_profit_price:
                checks["take_profit_hit"] = True
                self.last_trade_index[symbol] = current_index
                pnl = (bid - entry_price) * position_qty
                reasoning.append(f"Take profit hit: ${pnl:.2f} profit (+{(bid-entry_price)/entry_price:.2%})")
                return "SELL", position_qty, checks
            
            if bid <= stop_loss_price:
                checks["stop_loss_hit"] = True
                self.last_trade_index[symbol] = current_index
                pnl = (bid - entry_price) * position_qty
                reasoning.append(f"Stop loss hit: ${pnl:.2f} loss ({(bid-entry_price)/entry_price:.2%})")
                return "SELL", position_qty, checks
            
            if bid < sma_20 and roc_short < 0:
                checks["trend_broken"] = True
                self.last_trade_index[symbol] = current_index
                reasoning.append(f"Trend broken: price below SMA20, ROC negative")
                return "SELL", position_qty, checks
        
        return "HOLD", 0, checks
    
    def get_description(self) -> str:
        desc = f"{self.name} v{self.version}\n"
        desc += "Entry rules (ALL required):\n"
        desc += f"  • Uptrend: SMA20 > SMA50\n"
        desc += f"  • Strong momentum: ROC(7)>{self.min_trend_roc:.1%} AND ROC(3)>{self.min_roc_short:.1%}\n"
        desc += f"  • RSI {50}-{70} and rising\n"
        desc += f"  • Price < 95% of 50-bar high\n"
        desc += f"  • Cooldown: {self.cooldown_bars}+ bars since last trade\n"
        desc += "Exit on ANY:\n"
        desc += f"  • Take profit: Entry + {self.take_profit_atr_mult:.1f}×ATR\n"
        desc += f"  • Stop loss: Entry - {self.stop_loss_atr_mult:.1f}×ATR\n"
        desc += f"  • Trend break: Price < SMA20 AND ROC < 0\n"
        return desc
