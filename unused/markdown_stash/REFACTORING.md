# Code Restructuring Summary

## Goal
Reduce the size and complexity of `run_simulation.py` by extracting utility functions into focused, single-purpose modules.

## Changes Made

### 1. New `scripts/` Module
Extracted utility functions from `run_simulation.py` into focused modules:

#### `scripts/pricing.py`
- **`synthetic_price_bar()`** - Generates synthetic prices when Alpaca data unavailable
- Returns last known price without variance (ensures stable liquidation pricing)

#### `scripts/plotting.py`
- **`plot_capital_curves()`** - Plots and saves capital curves visualization
- **`create_final_report_pdf()`** - Generates final PDF report with capital curves and trade summary

#### `scripts/validation.py`
- **`check_consistency()`** - Validates portfolio positions against trade history
- Detects suspicious price jumps and inconsistencies

#### `scripts/archiving.py`
- **`save_run_results_to_archive()`** - Saves run results to both `run_old/YYMMDD/HHMM/` and keeps in `run_current/`
- Handles timestamping and 10-minute rounding

#### `scripts/support_resistance.py`
- **`compute_and_log_support_resistance_zones()`** - Computes and logs Support & Resistance zones
- Handles multi-scale analysis, zone merging, and logging

#### `scripts/__init__.py`
- Exports all utility functions for clean imports

### 2. New `unused/` Folder
Moved scripts that are not used in the active simulation:

- **`unused/plot_old_log.py`** - Historical utility for replaying old runs
- **`unused/simulator.py`** - Experimental simulator class (never used)
- **`unused/metrics.py`** - Evaluation functions (never called)
- **`unused/README.md`** - Documentation explaining what's in the unused folder

### 3. Updated `run_simulation.py`
- **Removed:** 314 lines of utility function definitions
- **Added:** Clean imports from `scripts` module
- **Result:** Reduced from 1,034 lines to ~720 lines (30% reduction)
- **Benefit:** Clearer focus on core simulation logic

### 4. Updated `backtest/__init__.py`
- Removed imports of unused `Simulator` and `evaluate` functions
- Now only exports `Portfolio` (the only used component)

## File Structure (New)

```
Penguin-Capitalist/
├── run_simulation.py           # Main simulation (cleaned up, now 720 lines)
├── scripts/                    # ✨ NEW: Utility modules
│   ├── __init__.py
│   ├── pricing.py              # Synthetic price generation
│   ├── plotting.py             # Visualization utilities
│   ├── validation.py           # Consistency checking
│   ├── archiving.py            # Run archiving
│   └── support_resistance.py   # S&R zone computation
├── unused/                     # ✨ NEW: Historical/unused code
│   ├── __init__.py
│   ├── README.md
│   ├── plot_old_log.py
│   ├── simulator.py
│   └── metrics.py
├── backtest/
│   ├── __init__.py             # Updated: removed unused exports
│   └── portfolio.py            # Still active
└── ... (other directories unchanged)
```

## Benefits

1. **Improved Readability**: `run_simulation.py` is now shorter and more focused
2. **Better Organization**: Utility functions are grouped by purpose
3. **Easier Maintenance**: Related code is in one place (e.g., all plotting in `plotting.py`)
4. **Clear Dependencies**: `scripts/__init__.py` shows exactly what utilities are available
5. **Cleaner Imports**: Instead of inline functions, clean imports from `scripts` module
6. **Archived Dead Code**: Unused code is now in `unused/` folder for easy reference and cleanup

## Code Organization

### Before
```python
# run_simulation.py (1,034 lines)
- Imports
- synthetic_price_bar()           # Function 1
- plot_capital_curves()           # Function 2
- create_final_report_pdf()       # Function 3
- check_consistency()             # Function 4
- save_run_results_to_archive()   # Function 5
- compute_and_log_support...()    # Inline code (150+ lines)
- run() function                  # Main logic
```

### After
```python
# run_simulation.py (720 lines)
- Imports (including from scripts)
- run() function                  # Main logic with import-based utilities

# scripts/pricing.py
- synthetic_price_bar()           # Isolated

# scripts/plotting.py
- plot_capital_curves()           # Isolated
- create_final_report_pdf()       # Isolated

# scripts/validation.py
- check_consistency()             # Isolated

# scripts/archiving.py
- save_run_results_to_archive()   # Isolated

# scripts/support_resistance.py
- compute_and_log_support...()    # Isolated
```

## Testing

All files have been syntax-checked:
- ✅ `run_simulation.py` - Valid Python syntax
- ✅ `scripts/pricing.py` - Valid Python syntax
- ✅ `scripts/plotting.py` - Valid Python syntax
- ✅ `scripts/validation.py` - Valid Python syntax
- ✅ `scripts/archiving.py` - Valid Python syntax
- ✅ `scripts/support_resistance.py` - Valid Python syntax

## Next Steps

1. Run a test simulation to verify everything works end-to-end
2. Consider further splitting if any module grows too large
3. Maybe create a `reports/` or `analysis/` module for helper functions related to result analysis
