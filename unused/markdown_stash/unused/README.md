# Unused Scripts

This folder contains scripts and modules that are **not used** in the active simulation, even when all Penguins are activated. They are kept for historical/reference purposes.

## Contents

### `plot_old_log.py`
- **Purpose:** Utility to replay and replot capital curves from saved run data
- **Why Unused:** Not integrated into the active simulation pipeline
- **Usage:** Manual analysis tool for historical runs

### `simulator.py`
- **Purpose:** Experimental simulator class (never exposed to penguins)
- **Why Unused:** Replaced by the live trading approach in `run_simulation.py`

### `metrics.py`
- **Purpose:** Evaluation functions for portfolio analysis
- **Why Unused:** Never called by active code

## Re-enabling Scripts

If you want to use any of these scripts, move them back to the main directory and add appropriate imports to the codebase.
