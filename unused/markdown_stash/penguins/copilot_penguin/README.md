# CopilotPenguin: Modular Trading Strategy System

## Overview

CopilotPenguin is a modular, tactic-based trading strategy with comprehensive decision logging and easy evaluation. It's designed for rapid strategy iteration and learning through experimentation.

**Key Features:**
- ✅ **Modular Tactics:** Switch between different strategies without changing core code
- ✅ **Decision Logging:** Every decision is logged with full reasoning and indicator values
- ✅ **Easy Evaluation:** Analyze performance with `python evaluate_copilot.py`
- ✅ **Tactic History:** Documentation of all strategies tried and why
- ✅ **Rapid Testing:** Test new tactics, measure, improve

---

## Folder Structure

```
penguins/copilot_penguin/
├── __init__.py                 # Package exports
├── copilot_penguin.py          # Main penguin class with logging
├── decision_logger.py          # Decision tracking and analysis
├── tactics.py                  # BaseTactic + all tactic implementations
└── TACTICS_HISTORY.md          # Documentation of tactics and evolution
```

---

## Quick Start

### Running a Simulation

```bash
cd /Users/nathanael/Documents/Uni/Masterarbeit/VSCode/Penguin-Capitalist
./venvPeng/bin/python run_simulation.py
```

CopilotPenguin will automatically:
1. Use the current tactic (v1.0: Strict Momentum)
2. Log all decisions to `run_current/copilot_penguin_decisions.json`
3. Print periodic summaries to console

### Evaluating Performance

After the simulation completes, analyze CopilotPenguin's decisions:

```bash
# Show full report
python evaluate_copilot.py

# Show only losing trades
python evaluate_copilot.py --failed-only

# Show last 50 decisions
python evaluate_copilot.py --limit 50

# Use custom log file
python evaluate_copilot.py path/to/log.json
```

**Output includes:**
- Decision breakdown (BUY/SELL/HOLD counts)
- Trade analysis (win rate, PnL, closed trades)
- Decision patterns (what blocked entries most?)
- Specific losing trades with full reasoning

---

## Understanding the Decision Log

Each decision is logged with:

```json
{
  "symbol": "AMD",
  "minute": 15,
  "decision": "BUY",
  "price": 217.60,
  "quantity": 2,
  "indicators": {
    "price": 217.60,
    "sma_20": 216.84,
    "sma_50": 216.21,
    "rsi": 62,
    "roc_3": 0.015,
    "roc_7": 0.018,
    "atr_proxy": 1.23
  },
  "checks": {
    "uptrend": true,
    "roc_medium_ok": true,
    "roc_short_ok": true,
    "rsi_in_range": true,
    "rsi_rising": true,
    "price_not_extended": true
  },
  "reasoning": "BUY: uptrend, strong momentum (ROC7=1.8%), RSI rising, price not extended, cash available (qty=2)"
}
```

---

## Current Tactic: v1.0

**Name:** Strict Momentum + RSI Rising + Price Extension Filter  
**File:** `penguins/copilot_penguin/tactics.py` class `TacticV1`  
**Philosophy:** Conservative trend-following with multiple confirmation layers

### Entry Rules (ALL required):
1. ✅ Uptrend: SMA20 > SMA50
2. ✅ Strong momentum: ROC(7) > 1.5% AND ROC(3) > 1.0%
3. ✅ RSI confirmation: 50-70 AND rising
4. ✅ Price not extended: < 95% of 50-bar high
5. ✅ Not in cooldown: ≥8 bars since last trade
6. ✅ Liquidity: Spread ≤ 1%

### Exit Rules (ANY one triggers):
- **Take Profit:** Price ≥ Entry + 2.5×ATR
- **Stop Loss:** Price ≤ Entry - 1.0×ATR
- **Trend Break:** Price < SMA20 AND ROC(3) < 0

### See Full Details:
```bash
cat penguins/copilot_penguin/TACTICS_HISTORY.md
```

---

## Testing a New Tactic

### 1. Create the New Tactic

Edit `penguins/copilot_penguin/tactics.py` and add:

```python
class TacticV2(BaseTactic):
    """Your new strategy description."""
    
    def __init__(self):
        super().__init__("TacticName", "2.0")
        # Your parameters here
        self.param1 = 0.5
        self.param2 = 10
    
    def decide(self, symbol, mid_prices, bid, ask, portfolio):
        """
        Make a decision.
        
        Returns:
            (decision, quantity, checks_dict)
        """
        checks = {"param1_check": False, "param2_check": False, ...}
        
        # Your logic here
        if condition:
            return "BUY", 2, checks
        elif other_condition:
            return "SELL", qty, checks
        else:
            return "HOLD", 0, checks
```

### 2. Test the Tactic

```python
from penguins.copilot_penguin.tactics import TacticV2

# Manually test
tactic = TacticV2()
decision, qty, checks = tactic.decide(symbol, prices, bid, ask, portfolio)
print(tactic.get_description())
```

### 3. Document the Tactic

Edit `penguins/copilot_penguin/TACTICS_HISTORY.md` and add a section describing:
- Tactic philosophy
- All entry/exit rules
- Changes from previous tactic
- Expected performance
- Known issues

### 4. Enable for Next Run

Currently, CopilotPenguin uses Tactic v1 by default. To switch:

**Option A: Modify default in code**
```python
# penguins/copilot_penguin/copilot_penguin.py
def __init__(self, tactic=None):
    super().__init__("CopilotPenguin")
    self.tactic = tactic or TacticV2()  # Change this line
```

**Option B: Switch during simulation** (advanced)
```python
from penguins.copilot_penguin import CopilotPenguin
from penguins.copilot_penguin.tactics import TacticV2

penguin = CopilotPenguin()
penguin.switch_tactic(TacticV2())
```

### 5. Analyze Results

Run the simulation and analyze:

```bash
python evaluate_copilot.py
```

Compare to Tactic v1 results to measure improvement.

---

## Example: How to Improve a Tactic

1. **Run simulation with current tactic**
   ```bash
   python run_simulation.py
   ```

2. **Analyze performance**
   ```bash
   python evaluate_copilot.py --failed-only
   # Review: What trades lost most money? Why?
   # What entry signals were blocked most often?
   ```

3. **Identify pattern**
   - Example: "Most losses occurred when RSI > 60"
   - Example: "75% of entries were blocked by ROC < threshold"

4. **Create Tactic v2 with fix**
   - Example: "Tighten RSI to < 60 at entry"
   - Example: "Lower ROC requirement to 0.8%"

5. **Test and compare**
   - Run simulation with new tactic
   - Compare metrics: Win rate, avg trade PnL, trade frequency

6. **Iterate**
   - If better: become new default
   - If worse: understand why (was it edge case vs systematic issue?)

---

## API Reference

### CopilotPenguin Class

```python
from penguins.copilot_penguin import CopilotPenguin, TacticV1

# Create penguin with default tactic (v1)
penguin = CopilotPenguin()

# Or specify tactic
penguin = CopilotPenguin(tactic=custom_tactic)

# Switch tactic mid-run (advanced)
from penguins.copilot_penguin.tactics import TacticV2
penguin.switch_tactic(TacticV2())

# Make a decision
decision, qty = penguin.decide(symbol, mid_prices, bid, ask, portfolio)

# Get summary
summary = penguin.get_summary()
# Returns: {'total_decisions': N, 'buy_count': ..., 'sell_count': ..., ...}

# Save decision log
penguin.save_decisions_log("path/to/log.json")
```

### DecisionLogger Class

```python
from penguins.copilot_penguin.decision_logger import DecisionLogger

logger = DecisionLogger("my_log.json")
logger.current_tactic = "MyTactic"
logger.tactic_version = "1.0"

# Log a decision
log = logger.log_decision(symbol, minute, "BUY")
log.price = 100.50
log.quantity = 2
log.indicators = {"rsi": 62, "roc": 0.015}
log.reasoning = "Strong momentum signal"

# Analyze
summary = logger.get_summary()
for trade in logger.analyze_failed_trades():
    print(f"Lost {trade['pnl']} on {trade['symbol']}")

# Save
logger.save("/path/to/log.json")
```

### BaseTactic & TacticV1 Classes

```python
from penguins.copilot_penguin.tactics import BaseTactic, TacticV1

# Use existing tactic
tactic = TacticV1()
print(tactic.get_description())

# Call decide method
decision, qty, checks = tactic.decide(symbol, prices, bid, ask, portfolio)
# decision: "BUY", "SELL", or "HOLD"
# qty: number of shares (0 if HOLD)
# checks: dict of all decision factors for debugging
```

---

## Key Files

| File | Purpose |
|------|---------|
| `penguins/copilot_penguin/__init__.py` | Package exports |
| `penguins/copilot_penguin/copilot_penguin.py` | Main penguin with logging |
| `penguins/copilot_penguin/decision_logger.py` | Decision tracking system |
| `penguins/copilot_penguin/tactics.py` | All tactic implementations |
| `penguins/copilot_penguin/TACTICS_HISTORY.md` | Strategy documentation |
| `evaluate_copilot.py` | Analysis tool (root dir) |

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'copilot_penguin'"
- Check: `ls penguins/copilot_penguin/` should show `__init__.py`
- Fix: Ensure you're using `from penguins import CopilotPenguin` not direct path

### Decision log not being created
- Check: Does `copilot_penguin.py` call `self.save_decisions_log()`?
- Fix: Look at end of `run_simulation.py` - add these lines:

```python
for penguin in penguins:
    if hasattr(penguin, 'save_decisions_log'):
        penguin.save_decisions_log(f"{RUN_CURRENT_DIR}/{penguin.name}_decisions.json")
```

### analyze_failed_trades() returns nothing
- Check: Are there any closed trades? (BUY + SELL pairs)
- Debug: Run `evaluate_copilot.py --limit 100` to see all decisions

---

## Next Steps

1. **Run the next simulation** with improved v1 tactic
2. **Evaluate results** with `python evaluate_copilot.py`
3. **Identify improvement** by analyzing failed trades
4. **Create Tactic v2** with specific fixes
5. **Test and measure** to confirm improvement
6. **Document progress** in TACTICS_HISTORY.md

---

## Notes

- Each tactic should be independent and testable
- Keep TACTICS_HISTORY.md updated for future reference
- Use `get_description()` to understand a tactic's rules
- The decision log is your source of truth for analysis
- Preserve old tactics for comparison and learning

**Remember:** The goal is to understand trading patterns, not just maximize profits. Each failed trade teaches you something.
