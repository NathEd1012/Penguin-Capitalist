"""
Evaluate CopilotPenguin: Analyze decisions and performance from a run.

Usage:
    python evaluate_copilot.py [log_file] [--failed-only] [--limit N]
    
    log_file: Path to copilot_penguin_decisions.json (default: run_current/)
    --failed-only: Show only losing trades
    --limit N: Show only first N decision records (default: all)
"""
import sys
import json
from pathlib import Path
from typing import List, Dict, Any


def load_log(path: str) -> Dict[str, Any]:
    """Load decision log from JSON file."""
    with open(path, 'r') as f:
        return json.load(f)


def analyze_decisions(data: Dict[str, Any], limit: int = None) -> None:
    """Print detailed analysis of decisions."""
    metadata = data.get('metadata', {})
    decisions = data.get('decisions', [])
    
    print("=" * 100)
    print("COPILOT PENGUIN EVALUATION REPORT")
    print("=" * 100)
    print(f"\nTactic: {metadata.get('current_tactic', 'Unknown')} v{metadata.get('tactic_version', '?')}")
    print(f"Total Decisions: {len(decisions)}")
    
    # Count decision types
    buy_decisions = [d for d in decisions if d['decision'] == 'BUY']
    sell_decisions = [d for d in decisions if d['decision'] == 'SELL']
    hold_decisions = [d for d in decisions if d['decision'] == 'HOLD']
    
    print(f"\nDecision Breakdown:")
    print(f"  BUY:  {len(buy_decisions):3d} ({len(buy_decisions)/len(decisions)*100:5.1f}%)")
    print(f"  SELL: {len(sell_decisions):3d} ({len(sell_decisions)/len(decisions)*100:5.1f}%)")
    print(f"  HOLD: {len(hold_decisions):3d} ({len(hold_decisions)/len(decisions)*100:5.1f}%)")
    
    # Symbols traded
    symbols = set(d['symbol'] for d in decisions)
    print(f"\nSymbols Traded: {len(symbols)}")
    print(f"  {', '.join(sorted(symbols))}")
    
    # Recent decisions
    print(f"\n{'='*100}")
    print("RECENT DECISIONS (with reasoning)")
    print(f"{'='*100}\n")
    
    display_decisions = decisions[-limit:] if limit else decisions
    for d in display_decisions:
        print(f"Min {d['minute']:2d} | {d['symbol']:6s} | {d['decision']:4s}", end="")
        if d['price']:
            print(f" @ ${d['price']:7.2f}", end="")
        if d['quantity']:
            print(f" x{d['quantity']}", end="")
        print()
        if d['reasoning']:
            print(f"         └→ {d['reasoning']}")
        print()


def analyze_trades(data: Dict[str, Any], failed_only: bool = False) -> None:
    """Analyze closed trades (buy-sell pairs)."""
    decisions = data.get('decisions', [])
    
    # Reconstruct trades
    open_positions = {}  # symbol -> list of buy entries
    closed_trades = []
    
    for dec in decisions:
        symbol = dec['symbol']
        if dec['decision'] == 'BUY':
            if symbol not in open_positions:
                open_positions[symbol] = []
            open_positions[symbol].append(dec)
        elif dec['decision'] == 'SELL' and symbol in open_positions and open_positions[symbol]:
            buy_dec = open_positions[symbol].pop(0)
            trade = {
                'symbol': symbol,
                'entry_minute': buy_dec['minute'],
                'exit_minute': dec['minute'],
                'entry_price': buy_dec['price'],
                'exit_price': dec['price'],
                'quantity': buy_dec['quantity'],
                'entry_reasoning': buy_dec['reasoning'],
                'exit_reasoning': dec['reasoning'],
            }
            if buy_dec['price'] and dec['price']:
                trade['pnl'] = (dec['price'] - buy_dec['price']) * buy_dec['quantity']
                trade['pnl_pct'] = (dec['price'] - buy_dec['price']) / buy_dec['price'] * 100
                closed_trades.append(trade)
    
    # Print trade analysis
    print(f"\n{'='*100}")
    print("TRADE ANALYSIS")
    print(f"{'='*100}\n")
    
    winning = [t for t in closed_trades if t['pnl'] > 0]
    losing = [t for t in closed_trades if t['pnl'] < 0]
    
    print(f"Closed Trades: {len(closed_trades)}")
    print(f"  Winning: {len(winning)} | Total PnL: ${sum(t['pnl'] for t in winning):+.2f}")
    print(f"  Losing:  {len(losing)} | Total PnL: ${sum(t['pnl'] for t in losing):+.2f}")
    print(f"  Win Rate: {len(winning)/(len(closed_trades)) if closed_trades else 0:.1%}\n")
    
    if not closed_trades:
        print("No completed trades to analyze.\n")
        return
    
    # Show trades
    trades_to_show = losing if failed_only else closed_trades
    trades_to_show = sorted(trades_to_show, key=lambda t: t['pnl'])
    
    print(f"Trades ({len(trades_to_show)} shown):")
    print("-" * 100)
    for trade in trades_to_show:
        status = "✓ WIN" if trade['pnl'] > 0 else "✗ LOSS"
        print(f"{trade['symbol']:6s} ({trade['entry_minute']:2d}→{trade['exit_minute']:2d}) " +
              f"${trade['entry_price']:7.2f} → ${trade['exit_price']:7.2f} " +
              f"{status} ${trade['pnl']:+7.2f} ({trade['pnl_pct']:+6.2f}%)")
        print(f"  Buy:  {trade['entry_reasoning']}")
        print(f"  Sell: {trade['exit_reasoning']}")
        print()


def identify_patterns(data: Dict[str, Any]) -> None:
    """Identify patterns in decisions."""
    decisions = data.get('decisions', [])
    
    print(f"\n{'='*100}")
    print("DECISION PATTERNS")
    print(f"{'='*100}\n")
    
    # Failed entry patterns
    buy_decisions = [d for d in decisions if d['decision'] == 'BUY']
    if not buy_decisions:
        print("No buy decisions to analyze.\n")
        return
    
    # Check which buy signals were blocked most often
    check_failures = {}
    for d in decisions:
        if d['decision'] == 'HOLD' and d['checks']:
            for check, passed in d['checks'].items():
                if not passed and check != 'has_position':
                    check_failures[check] = check_failures.get(check, 0) + 1
    
    print("Most Common Entry Blockers:")
    for check, count in sorted(check_failures.items(), key=lambda x: -x[1])[:5]:
        pct = count / len(buy_decisions) * 100 if buy_decisions else 0
        print(f"  • {check:30s}: {count:3d} times ({pct:5.1f}%)")
    
    # Hold decision patterns
    print("\nWhy HOLD?")
    hold_reasons = {}
    for d in decisions:
        if d['reasoning'] and 'HOLD:' in d['reasoning']:
            reason = d['reasoning'].replace('HOLD: ', '')
            reasons = [r.strip() for r in reason.split(',')]
            for r in reasons:
                hold_reasons[r] = hold_reasons.get(r, 0) + 1
    
    for reason, count in sorted(hold_reasons.items(), key=lambda x: -x[1])[:5]:
        print(f"  • {reason:30s}: {count:3d} times")


def main():
    """Main evaluation entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Evaluate CopilotPenguin performance from decision log"
    )
    parser.add_argument(
        "logfile",
        nargs='?',
        default="run_current/copilot_penguin_decisions.json",
        help="Path to copilot_penguin_decisions.json"
    )
    parser.add_argument("--failed-only", action="store_true", help="Show only losing trades")
    parser.add_argument("--limit", type=int, default=None, help="Show only first N decision records")
    
    args = parser.parse_args()
    
    # Load log
    log_path = Path(args.logfile)
    if not log_path.exists():
        print(f"Error: Log file not found: {log_path}")
        return 1
    
    try:
        data = load_log(str(log_path))
    except json.JSONDecodeError as e:
        print(f"Error: Could not parse JSON: {e}")
        return 1
    
    # Analyze
    analyze_decisions(data, limit=args.limit)
    analyze_trades(data, failed_only=args.failed_only)
    identify_patterns(data)
    
    print("\n" + "=" * 100)
    print("END OF REPORT")
    print("=" * 100 + "\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
