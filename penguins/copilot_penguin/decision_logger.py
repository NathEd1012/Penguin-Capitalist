"""
Decision logger for CopilotPenguin.
Tracks all decisions, reasoning, and indicator values for analysis and evaluation.
"""
from datetime import datetime
from typing import Dict, Optional, Any, List
import json


class DecisionLog:
    """Single decision record with full context."""
    
    def __init__(self, symbol: str, minute: int, decision: str):
        self.symbol = symbol
        self.minute = minute
        self.decision = decision  # BUY, SELL, HOLD
        self.price = None
        self.quantity = None
        self.indicators = {}  # RSI, ROC, SMA values, etc.
        self.checks = {}  # All decision checks (passed/failed)
        self.reasoning = None  # Plain English explanation
        self.portfolio_value = None
        self.position_after = None  # How many shares after decision
        
    def to_dict(self):
        return {
            'symbol': self.symbol,
            'minute': self.minute,
            'decision': self.decision,
            'price': self.price,
            'quantity': self.quantity,
            'indicators': self.indicators,
            'checks': self.checks,
            'reasoning': self.reasoning,
            'portfolio_value': self.portfolio_value,
            'position_after': self.position_after,
        }


class DecisionLogger:
    """Logs all CopilotPenguin decisions with full reasoning."""
    
    def __init__(self, filename: Optional[str] = None):
        self.logs: List[DecisionLog] = []
        self.filename = filename or "copilot_penguin_decisions.json"
        self.current_tactic = None
        self.tactic_version = None
        
    def log_decision(self, symbol: str, minute: int, decision: str) -> DecisionLog:
        """Create a new decision log entry."""
        log = DecisionLog(symbol, minute, decision)
        self.logs.append(log)
        return log
    
    def save(self, path: str):
        """Save all logs to JSON file."""
        data = {
            'metadata': {
                'generated': datetime.now().isoformat(),
                'total_decisions': len(self.logs),
                'current_tactic': self.current_tactic,
                'tactic_version': self.tactic_version,
            },
            'decisions': [log.to_dict() for log in self.logs]
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics."""
        buys = [l for l in self.logs if l.decision == 'BUY']
        sells = [l for l in self.logs if l.decision == 'SELL']
        holds = [l for l in self.logs if l.decision == 'HOLD']
        
        return {
            'total_decisions': len(self.logs),
            'buy_count': len(buys),
            'sell_count': len(sells),
            'hold_count': len(holds),
            'unique_symbols': len(set(l.symbol for l in self.logs)),
            'current_tactic': self.current_tactic,
            'tactic_version': self.tactic_version,
        }
    
    def analyze_failed_trades(self) -> List[Dict]:
        """Identify trades that resulted in losses."""
        trades = {}  # symbol -> list of buy-sell pairs
        
        for log in self.logs:
            if log.decision == 'BUY':
                if log.symbol not in trades:
                    trades[log.symbol] = []
                trades[log.symbol].append({'action': 'BUY', 'log': log})
            elif log.decision == 'SELL':
                if log.symbol in trades and trades[log.symbol]:
                    # Pair with last buy
                    if trades[log.symbol][-1]['action'] == 'BUY':
                        pair = {
                            'symbol': log.symbol,
                            'buy_price': trades[log.symbol][-1]['log'].price,
                            'sell_price': log.price,
                            'buy_quantity': trades[log.symbol][-1]['log'].quantity,
                            'buy_minute': trades[log.symbol][-1]['log'].minute,
                            'sell_minute': log.minute,
                            'buy_reasoning': trades[log.symbol][-1]['log'].reasoning,
                            'sell_reasoning': log.reasoning,
                            'buy_checks': trades[log.symbol][-1]['log'].checks,
                            'pnl': (log.price - trades[log.symbol][-1]['log'].price) * log.quantity,
                        }
                        pair['is_loss'] = pair['pnl'] < 0
                        yield pair
                        trades[log.symbol].pop()
    
    def get_decisions_for_symbol(self, symbol: str) -> List[DecisionLog]:
        """Get all decisions for a specific symbol."""
        return [log for log in self.logs if log.symbol == symbol]
    
    def get_decisions_at_minute(self, minute: int) -> List[DecisionLog]:
        """Get all decisions made at a specific minute."""
        return [log for log in self.logs if log.minute == minute]
    
    def format_decision_report(self, limit: int = 20) -> str:
        """Format a human-readable report of recent decisions."""
        report = f"\n{'='*100}\nCOPILOT PENGUIN DECISION LOG\n{'='*100}\n"
        report += f"Tactic: {self.current_tactic} (v{self.tactic_version})\n"
        report += f"Total Decisions: {len(self.logs)}\n\n"
        
        # Recent decisions
        recent = self.logs[-limit:] if len(self.logs) > limit else self.logs
        for log in recent:
            report += f"Min {log.minute:2d} | {log.symbol:6s} | {log.decision:4s}"
            if log.price:
                report += f" @ ${log.price:7.2f}"
            if log.quantity:
                report += f" x{log.quantity}"
            if log.reasoning:
                report += f"\n           → {log.reasoning}\n"
            else:
                report += "\n"
        
        report += f"\n{'='*100}\n"
        return report


# Global logger instance (initialized by CopilotPenguin)
_decision_logger = None


def get_logger() -> DecisionLogger:
    """Get or create the global logger."""
    global _decision_logger
    if _decision_logger is None:
        _decision_logger = DecisionLogger()
    return _decision_logger


def set_logger(logger: DecisionLogger):
    """Set the global logger."""
    global _decision_logger
    _decision_logger = logger
