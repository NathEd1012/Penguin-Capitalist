#!/usr/bin/env python3
"""Detailed evaluation of CopilotPenguin strategy performance."""
import sys
from pathlib import Path
import json
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Load metrics and trades data
metrics_file = BASE_DIR / "run_current/metrics_summary.json"
trades_file = BASE_DIR / "run_current/trades_log.txt"
curves_file = BASE_DIR / "run_current/curves_data.json"

print("=" * 80)
print("COPILOT PENGUIN - DETAILED EVALUATION")
print("=" * 80)

# Load metrics
with open(metrics_file, 'r') as f:
    metrics = json.load(f)

if 'CopilotPenguin' in metrics:
    cop = metrics['CopilotPenguin']
    
    print("\n📊 PERFORMANCE METRICS")
    print("-" * 80)
    print(f"Initial Capital:     ${cop.get('initial_capital', 5000):,.2f}")
    print(f"Final Value:         ${cop['final_value']:,.2f}")
    print(f"Total Return:        ${cop['total_return']:.2f} (+{cop['return_pct']:.2f}%)")
    print(f"Max Drawdown:        {cop['max_drawdown']:.2f}%")
    print(f"Sharpe Ratio:        {cop['sharpe_ratio']:.2f}")
    print(f"Total Trades:        {cop['total_trades']} ({cop['buy_trades']} buys, {cop['sell_trades']} sells)")
    
    print("\n📈 CAPITAL CURVE ANALYSIS")
    print("-" * 80)
    with open(curves_file, 'r') as f:
        curves = json.load(f)
    
    if 'CopilotPenguin' in curves:
        cop_curve = curves['CopilotPenguin']
        
        # Find best and worst periods
        max_value = max(cop_curve)
        min_value = min(cop_curve)
        max_idx = cop_curve.index(max_value)
        min_idx = cop_curve.index(min_value)
        
        print(f"Starting Value:      ${cop_curve[0]:,.2f}")
        print(f"Peak Value:          ${max_value:,.2f} (Bar {max_idx + 1})")
        print(f"Lowest Value:        ${min_value:,.2f} (Bar {min_idx + 1})")
        print(f"Final Value:         ${cop_curve[-1]:,.2f}")
        
        # Calculate volatility
        changes = []
        for i in range(1, len(cop_curve)):
            pct_change = (cop_curve[i] - cop_curve[i-1]) / cop_curve[i-1] * 100
            changes.append(pct_change)
        
        avg_change = sum(changes) / len(changes) if changes else 0
        max_gain = max(changes) if changes else 0
        max_loss = min(changes) if changes else 0
        
        print(f"Avg Bar Change:      {avg_change:.4f}%")
        print(f"Max Single Gain:     {max_gain:.2f}%")
        print(f"Max Single Loss:     {max_loss:.2f}%")

    print("\n💰 TRADE ANALYSIS")
    print("-" * 80)
    
    # Parse trades from log
    cop_trades = []
    current_positions = {}
    
    with open(trades_file, 'r') as f:
        for line in f:
            if 'CopilotPenguin:' in line:
                parts = line.strip().split()
                if 'BUY' in line:
                    # Extract: BUY qty SYMBOL @ $price
                    idx = parts.index('BUY')
                    qty = int(parts[idx + 1])
                    symbol = parts[idx + 2]
                    price = float(parts[idx + 4].replace('$', ''))
                    
                    if symbol not in current_positions:
                        current_positions[symbol] = {'qty': 0, 'cost': 0}
                    current_positions[symbol]['qty'] += qty
                    current_positions[symbol]['cost'] += qty * price
                    
                    cop_trades.append({
                        'type': 'BUY',
                        'symbol': symbol,
                        'qty': qty,
                        'price': price
                    })
                    
                elif 'SELL' in line:
                    idx = parts.index('SELL')
                    qty = int(parts[idx + 1])
                    symbol = parts[idx + 2]
                    price = float(parts[idx + 4].replace('$', ''))
                    
                    cop_trades.append({
                        'type': 'SELL',
                        'symbol': symbol,
                        'qty': qty,
                        'price': price
                    })
    
    # Count by type
    buy_count = sum(1 for t in cop_trades if t['type'] == 'BUY')
    sell_count = sum(1 for t in cop_trades if t['type'] == 'SELL')
    
    print(f"Total Trades:        {len(cop_trades)}")
    print(f"  - Buy Orders:      {buy_count}")
    print(f"  - Sell Orders:     {sell_count}")
    
    # Symbol distribution
    symbol_counts = {}
    for trade in cop_trades:
        symbol = trade['symbol']
        if symbol not in symbol_counts:
            symbol_counts[symbol] = 0
        symbol_counts[symbol] += 1
    
    print(f"\n📦 TRADING BY SYMBOL")
    print("-" * 80)
    for symbol, count in sorted(symbol_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {symbol:6s}: {count:3d} trades")
    
    print("\n🎯 IMPROVED STRATEGY PARAMETERS")
    print("-" * 80)
    print("  Min Bars Required:    50 (↑ for reliability)")
    print("  Cooldown Bars:        3")
    print("  Max Spread:           2.0%")
    print("  Min ROC:              0.002 (20× stricter)")
    print("  RSI Range:            40-70 (healthy range)")
    print("  Stop Loss:            1.0 × ATR (↓ tighter)")
    print("  Take Profit:          1.5 × ATR (↓ closer)")
    print("  Trailing Stop:        0.75 × ATR (NEW)")
    print("  Position Size:        1-3 shares (dynamic)")
    
    print("\n📝 IMPROVED STRATEGY LOGIC")
    print("-" * 80)
    print("  Entry Conditions (STRICTER):")
    print("    - ROC(7) > 0.002 AND ROC(3) > 0")
    print("    - RSI 40-70 (healthy)")
    print("    - Uptrend: price > SMA20 > SMA50")
    print("    - Signal-based sizing (1-3 shares)")
    print("    - Not in cooldown (3 bars)")
    print("    - Spread < 2%")
    print()
    print("  Exit Conditions (ENHANCED):")
    print("    - Take profit: entry + 1.5×ATR")
    print("    - Initial stop: entry - 1.0×ATR")
    print("    - Trailing stop: 0.75×ATR from peak (if profit > 1.0×ATR)")
    print("    - Reversal exit: ROC(3) < -0.003 AND RSI < 40")
    print("    - Trend break: price < SMA20 AND ROC(7) < -0.001")
    
    print("\n⚖️ COMPARISON WITH OTHER STRATEGIES")
    print("-" * 80)
    strategies = ['CopilotPenguin', 'SMA20MultiTimeframePenguin', 
                  'SupportResistancePenguin', 'RSI Mean Reversion']
    
    for strat in strategies:
        if strat in metrics:
            m = metrics[strat]
            print(f"{strat:30s}: {m['total_return']:+7.2f}% | "
                  f"Trades: {m['total_trades']:4d} | "
                  f"Sharpe: {m['sharpe_ratio']:+.2f}")
    
    # Rank
    rankings = sorted([(k, v['total_return']) for k, v in metrics.items()], 
                     key=lambda x: x[1], reverse=True)
    cop_rank = [i+1 for i, (name, _) in enumerate(rankings) if name == 'CopilotPenguin'][0]
    
    print(f"\n🏆 CopilotPenguin Ranking: #{cop_rank} of {len(rankings)}")

else:
    print("❌ CopilotPenguin data not found in metrics")

print("\n" + "=" * 80)
