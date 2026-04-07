# CopilotPenguin: Quick Start Guide

## TL;DR

**Run simulation:**
```bash
python run_simulation.py
```

**Evaluate performance:**
```bash
python evaluate_copilot.py
```

---

## What's New

CopilotPenguin is now a **modular, strategy-swappable trading system** with comprehensive decision logging.

### Key Capabilities

1. **Full decision logging** - Every trade decision is recorded with:
   - Indicator values (RSI, ROC, SMA, etc.)
   - All checks performed (passed/failed)
   - Human-readable reasoning

2. **Easy evaluation** - Analyze performance:
   ```bash
   python evaluate_copilot.py          # Full report
   python evaluate_copilot.py --failed-only  # Show losing trades
   ```

3. **Strategy swapping** - Test new tactics without changing code:
   ```python
   penguin = CopilotPenguin(tactic=TacticV2())
   ```

4. **Pattern recognition** - Automatic analysis of:
   - Win rate per trade
   - Most common entry blockers
   - Specific failing trade patterns

---

## Current Strategy: Tactic v1.0

**Name:** Strict Momentum + RSI Rising + Price Extension Filter

### Entry Requires ALL:
- ✓ Uptrend (SMA20 > SMA50)
- ✓ Strong momentum (ROC(7) > 1.5% AND ROC(3) > 1.0%)
- ✓ RSI confirmation (50-70 range AND rising)
- ✓ Price not extended (< 95% of 50-bar high)
- ✓ No recent trades (8+ bars since last trade on symbol)

### Exit on ANY:
- Take profit at Entry + 2.5×ATR
- Stop loss at Entry - 1.0×ATR
- Trend break (Price < SMA20 AND ROC(3) < 0)

---

## File Structure

```
penguins/copilot_penguin/
├── copilot_penguin.py         Main penguin class (145 lines)
├── tactics.py                 All strategies (207 lines)
├── decision_logger.py         Decision tracking (160 lines)
├── __init__.py                Package exports (8 lines)
├── TACTICS_HISTORY.md         Strategy documentation
├── README.md                  Full user guide
└── REFACTORING_SUMMARY.md     What changed
```

---

## Typical Workflow

### 1. Run Simulation
```bash
./venvPeng/bin/python run_simulation.py
```
Output: `run_current/CopilotPenguin_decisions.json` (with all decisions logged)

### 2. Analyze Results
```bash
python evaluate_copilot.py
```
Get:
- Total decisions by type
- Win rate and PnL
- Specific losing trades with reasoning
- Most common entry blockers

### 3. Identify Pattern
Example: "Most losses when RSI > 65 at entry"

### 4. Create New Tactic
Edit `penguins/copilot_penguin/tactics.py`:
```python
class TacticV2(BaseTactic):
    def __init__(self):
        super().__init__("ImprovedMomentum", "2.0")
        self.max_rsi = 65  # Tighten from 70
    
    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        # Your logic here
        ...
```

### 5. Test New Tactic
Next simulation will use it if set as default, or specify:
```python
penguin = CopilotPenguin(tactic=TacticV2())
```

### 6. Compare Results
```bash
python evaluate_copilot.py
```
Did win rate improve? Did PnL improve? Keep or iterate?

### 7. Document
Update `penguins/copilot_penguin/TACTICS_HISTORY.md` with findings.

---

## Evaluation Output Example

```
============================================================================
COPILOT PENGUIN EVALUATION REPORT
============================================================================

Tactic: Momentum+RSI+Extension v1.0
Total Decisions: 4,320

Decision Breakdown:
  BUY:  287 ( 6.6%)
  SELL: 268 ( 6.2%)
  HOLD: 3765 (87.2%)

Symbols Traded: 19
  AMD, AAPL, PLTR, MSTR, ...

============================================================================
TRADE ANALYSIS
============================================================================

Closed Trades: 268
  Winning: 67 | Total PnL: $+234.50
  Losing:  201 | Total PnL: $-189.20
  Win Rate: 25.0%

WORST TRADES (Top 5 Losers):
MSFT : Buy $389 → Sell $385 LOSS $-8.70  (-1.12%)
TSLA : Buy $408 → Sell $405 LOSS $-4.56  (-0.56%)
...

DECISION PATTERNS:
Most Common Entry Blockers:
  • uptrend               : 1240 times (52.1%)
  • roc_medium_ok         : 890 times (37.4%)
  • price_not_extended    : 450 times (18.9%)
```

---

## Advanced: Creating Custom Tactics

### Anatomy of a Tactic

```python
from penguins.copilot_penguin.tactics import BaseTactic

class TacticV3(BaseTactic):
    """Your strategy description."""
    
    def __init__(self):
        # Set name and version
        super().__init__("CustomStrategy", "3.0")
        
        # Your parameters
        self.param1 = 0.5
        self.param2 = 10
        self.last_trade_index = {}
    
    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        """
        Make decision.
        
        Returns:
            (decision, qty, checks_dict)
            decision: "BUY", "SELL", "HOLD"
            qty: number of shares (0 if HOLD)
            checks: dict with decision factors (for logging)
        """
        
        # Initialize checks dict
        checks = {
            "condition1": False,
            "condition2": False,
            ...
        }
        
        # Validate data
        if bid <= 0 or ask <= 0:
            return "HOLD", 0, checks
        
        if len(mid_prices) < 50:
            return "HOLD", 0, checks
        
        # Calculate indicators
        price = mid_prices[-1]
        # ... your calculations ...
        
        # Decision logic
        checks["condition1"] = (some_indicator > threshold)
        checks["condition2"] = (another_check)
        
        if checks["condition1"] and checks["condition2"]:
            return "BUY", 2, checks
        
        return "HOLD", 0, checks
    
    def get_description(self):
        """Return human-readable strategy description."""
        return f"{self.name} v{self.version}\n..."
```

### Required Methods
- `__init__()` - Initialize with name, version, and parameters
- `decide()` - Return (decision, qty, checks_dict)
- `get_description()` - Human-readable rules

### Testing Custom Tactic

```python
from penguins.copilot_penguin import CopilotPenguin
from penguins.copilot_penguin.tactics import TacticV3

# Create and test
tactic = TacticV3()
print(tactic.get_description())

penguin = CopilotPenguin(tactic=tactic)
decision, qty = penguin.decide("AAPL", prices, bid, ask, portfolio)
```

---

## Troubleshooting

### Issue: Decision log not created
**Solution:** Check end of run_simulation.py has log saving code:
```python
for penguin in penguins:
    if hasattr(penguin, 'save_decisions_log'):
        log_path = os.path.join(RUN_CURRENT_DIR, f"{penguin.name}_decisions.json")
        penguin.save_decisions_log(log_path)
```

### Issue: evaluate_copilot.py fails
**Solution:** Check log file exists:
```bash
ls run_current/CopilotPenguin_decisions.json
python evaluate_copilot.py --help
```

### Issue: Import error
**Solution:** Verify folder structure:
```bash
ls -la penguins/copilot_penguin/
# Should show: __init__.py, copilot_penguin.py, tactics.py, decision_logger.py
```

---

## Next: Try It Out

1. **Verify everything works:**
   ```bash
   python verify_copilot_refactoring.py
   ```
   (Should show ✓ All verification tests PASSED)

2. **Run a simulation:**
   ```bash
   python run_simulation.py
   ```

3. **Analyze results:**
   ```bash
   python evaluate_copilot.py
   ```

4. **Iterate** - Identify patterns, create new tactic, test, repeat!

---

## Documentation Files

| File | Purpose |
|------|---------|
| `penguins/copilot_penguin/README.md` | Full user guide |
| `penguins/copilot_penguin/TACTICS_HISTORY.md` | All strategies documented |
| `penguins/copilot_penguin/REFACTORING_SUMMARY.md` | What changed |
| `evaluate_copilot.py` | Evaluation tool (in root) |
| `verify_copilot_refactoring.py` | Verification script (in root) |

---

**Happy trading! 🐧 📊**
