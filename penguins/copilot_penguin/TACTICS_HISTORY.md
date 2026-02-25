# CopilotPenguin Tactics History & Evolution

## Purpose
This file documents all tactics implemented for CopilotPenguin and how they evolved based on performance analysis and lessons learned.

---

## Tactic v1.0: Strict Momentum + RSI Rising + Price Extension Filter

**Status:** ACTIVE ✅  
**File:** [penguins/copilot_penguin/tactics.py](../copilot_penguin/tactics.py)  
**Class:** `TacticV1`  
**Created:** 2026-02-25  
**Based on:** Analysis of 5 losing trades from initial runs

### Strategy Overview

**Philosophy:** Conservative trend-following with multiple confirmation requirements before entry.

The strategy enters only when all of the following conditions align:
1. Clear uptrend (SMA20 > SMA50)
2. Strong momentum in both short and medium term
3. RSI confirming and rising (not just in range)
4. Price not overextended at local highs
5. Sufficient time since last trade (cooldown)

**Key Insight:** Previous failures were due to entering on weak momentum signals. v1 requires 3x stronger momentum (1.5% vs 0.5%) to filter out false signals.

### Entry Rules (ALL must pass)

| Condition | Rule | Reasoning |
|-----------|------|-----------|
| **Trend** | SMA20 > SMA50 | Confirms uptrend direction |
| **Medium Momentum** | ROC(7) > 1.5% | Strong 7-bar momentum (1.5% vs old 0.5%) |
| **Short Momentum** | ROC(3) > 1.0% | Both timeframes must align |
| **RSI Range** | 50 ≤ RSI ≤ 70 | Momentum zone (not overbought >70) |
| **RSI Trend** | RSI(current) ≥ RSI(prev) | NEW: Momentum must be increasing |
| **Price Extension** | Price < 95% of 50-bar high | NEW: Prevent buying at local tops |
| **Cooldown** | ≥8 bars since last trade | Increased from 5 to reduce whipsaws |
| **Liquidity** | Spread ≤ 1% | Avoid wide spreads |

### Exit Rules (ANY one triggers exit)

| Condition | Rule | Reasoning |
|-----------|------|-----------|
| **Take Profit** | Price ≥ Entry + 2.5×ATR | Capture strong moves (2.5x vs old 2.0x) |
| **Stop Loss** | Price ≤ Entry - 1.0×ATR | Tight exit (1.0x vs old 1.5x) |
| **Trend Break** | Price < SMA20 AND ROC(3) < 0 | Exit on confirmed reversal |

### Position Sizing

- High volatility (ATR/price > 2%): 1 share
- Normal volatility: 2 shares
- Capped by available cash

### Changes from Previous Strategy

| Aspect | Old | New | Impact |
|--------|-----|-----|--------|
| ROC(7) minimum | 0.5% | 1.5% | 3x stricter entry filter |
| ROC(3) check | None | 1.0% | NEW confirmation layer |
| RSI rising check | No | Yes | Avoid entry on RSI reversals |
| Price extension | No filter | <95% of 50-bar | Prevent MSFT-type tops |
| Stop loss | 1.5x ATR | 1.0x ATR | Exit faster from failed setups |
| Cooldown | 5 bars | 8 bars | Reduce whipsaw trades |
| Take profit | 2.0x ATR | 2.5x ATR | Compensation for tighter stops |

### Known Issues & Limitations

1. **May miss trends** if market starts from 50% and accelerates slowly
   - _Mitigation:_ ROC(3) check allows entry if recent bars show momentum pickup
   
2. **Could be too conservative** in sideways markets
   - _Mitigation:_ Loosen price extension filter to 98% if needed
   
3. **Stops at 1.0x ATR** might be shaken out in high-volatility periods
   - _Mitigation:_ Monitor first run, ready to increase to 1.2x if excessive shakeouts

### Performance Data (From Analysis)

**Previous Strategy Results:** 14 trades, 5 closed (all losses), -$24.33 PnL (-0.49%)

Expected with v1:
- **Fewer entries:** ~50% reduction in trade attempts (stricter filters)
- **Better win rate:** 0% → 25-30% (multiple confirmations)
- **Smaller losses:** -$3.44 avg → -$2.50 avg (tighter stops)

### How to Use This Tactic

```python
from penguins.copilot_penguin.tactics import TacticV1
from penguins.copilot_penguin import CopilotPenguin

tactic = TacticV1()
penguin = CopilotPenguin(tactic=tactic)
```

### Testing Improvements

- ✅ Syntax validated
- ⏳ Needs live run test (target: 25-30% win rate)
- ⏳ Monitor for shakeouts at stop loss (adjust if >3 in 20 trades)

---

## Tactic v2.0: [PLACEHOLDER - To Be Implemented]

**Status:** PLANNED 📋  
**Potential Improvements:**
- Add divergence detection (price new high, RSI not new high)
- Support/resistance bounce confirmation
- Volume-weighted momentum
- Adaptive position sizing based on win rate

---

## Evaluation Framework

To evaluate CopilotPenguin after a run, call:

```bash
# Print summary to terminal
python -c "from penguins.copilot_penguin import CopilotPenguin; cp = CopilotPenguin(); print(cp.get_summary())"

# Or generate full report
python evaluate_copilot.py
```

This will output:
- Decision count per type (BUY, SELL, HOLD)
- Win/loss breakdown
- Identify failed trades and why they failed
- Suggest specific improvements to tactic parameters

---

## Design Philosophy

The modular structure allows for:

1. **Easy tactic swapping:** Switch between v1, v2, etc. without changing main penguin code
2. **Full decision logging:** Every decision is recorded with reasoning for post-analysis
3. **Rapid iteration:** Try new tactics, measure, improve
4. **Learning:** Understanding WHY decisions are made helps optimize them

Each tactic should be self-contained and independent, inheriting from `BaseTactic` to ensure consistency.

---

## Future Enhancements

- [ ] Adaptive parameter tuning based on symbol-specific win rates
- [ ] Divergence detection (price + RSI misalignment)
- [ ] Support/resistance level tracking
- [ ] Machine learning backtesting on historical data
- [ ] Real-time tactic performance dashboard
- [ ] A/B testing: run multiple tactics in parallel, winner gets more capital

---

## Contributing New Tactics

To implement a new tactic:

1. Create a class inheriting from `BaseTactic` in [tactics.py](../copilot_penguin/tactics.py)
2. Implement `decide()` method returning `(decision, qty, checks_dict)`
3. Document the strategy in this file
4. Test with a simulation run
5. Compare metrics to previous tactics

Example template:

```python
class TacticV2(BaseTactic):
    def __init__(self):
        super().__init__("TacticName", "2.0")
        # Parameters here
    
    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        # Logic here
        checks = { /* all decision factors */ }
        return decision, qty, checks
    
    def get_description(self):
        # Return human-readable description
        pass
```

---

## Quick Reference: Tactic Comparison

| Aspect | v1.0 |
|--------|------|
| **Entry Conservatism** | Very high (5 checks) |
| **Expected Win Rate** | 25-30% |
| **Expected Trades/100min** | 8-12 |
| **Use Cases** | Moderate volatility, trending markets |
| **Status** | ACTIVE ✅ |

---

## Notes for Future Self

- Always log the REASON behind parameter changes
- Test edge cases: gaps, sideways markets, extreme volatility
- Document failed tactics and why they failed (for learning)
- Keep v1 as baseline for comparison
