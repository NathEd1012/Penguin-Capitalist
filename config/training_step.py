"""Configuration for the in-simulation training step."""
import os
from .backtest import START_DATE as EXECUTION_START_DATE, STOP_DATE as EXECUTION_STOP_DATE
from .symbols import SYMBOLS as TRAINING_SYMBOLS
from penguins import (
    Adv_SELL_TP1,
    Adv_SELL_TP1_Manual,
    Adv_SELL_TP2,
    Adv_SELL_TP2_Manual,
    Adv_SELL_TP3,
    Adv_SELL_TP3_Manual,
    Adv_SELL_TP4,
    Adv_SELL_TP4_Manual,
    OG_TP1,
    OG_TP1_Manual,
    OG_TP2,
    OG_TP2_Manual,
    OG_TP3,
    OG_TP3_Manual,
    OG_TP4,
    OG_TP4_Manual,
)

# Toggle the training pass that runs after strategy initialization.
TRAINING_STEP_ENABLED = True

# Number of optimization rounds per trainable strategy.
TRAINING_ITERATIONSx = 3
TRAINING_ITERATIONS = int(os.getenv("FIXED_TS", TRAINING_ITERATIONSx))

# Training subsets are intentionally small to keep optimization tractable.
TRAINING_SUBSET_MONTHSx = 2
TRAINING_SUBSET_MONTHS = int(os.getenv("FIXED_MONTH", TRAINING_SUBSET_MONTHSx))

TRAINING_SUBSET_STOCKSx = 30
TRAINING_SUBSET_STOCKS = int(os.getenv("FIXED_SYMB", TRAINING_SUBSET_STOCKSx))

# Match the training objective's per-buy cost penalty.
TRAINING_TRANSACTION_COSTx = 2.0
TRAINING_TRANSACTION_COST = float(os.getenv("FIXED_TRAIN_TC", TRAINING_TRANSACTION_COSTx))

# Train on a different date window from the live execution window when requested.
TRAINING_START_DATE = os.getenv("FIXED_TRAIN_START", EXECUTION_START_DATE)
TRAINING_STOP_DATE = os.getenv("FIXED_TRAIN_STOP", EXECUTION_STOP_DATE)

def _parse_training_relative_to(raw_value):
    value = str(raw_value).strip().upper()
    if value in {"", "SPY"}:
        return "SPY"
    if value == "0":
        return 0
    raise ValueError("FIXED_REL must be 0 or SPY")


# Set to 0 for absolute profit or SPY for relative profit.
TRAINING_RELATIVE_TO = _parse_training_relative_to(os.getenv("FIXED_REL", "SPY"))

# Keep the search reproducible unless the user changes the seed.
TRAINING_RANDOM_SEED = 42

# When True, the trainer executes the manual strategies as baseline runs.
# They are not optimized; only the trainable strategies below are sampled.
Manual = True

# These strategy groups are derived from the class-level TRAINABLE flag so the
# optimizer and reporting logic do not need to match class names.
_ALL_TRAINING_PENGUINS = [
    OG_TP1,
    OG_TP2,
    OG_TP3,
    OG_TP4,
    Adv_SELL_TP1,
    Adv_SELL_TP2,
    Adv_SELL_TP3,
    Adv_SELL_TP4,
    OG_TP1_Manual,
    OG_TP2_Manual,
    OG_TP3_Manual,
    OG_TP4_Manual,
    Adv_SELL_TP1_Manual,
    Adv_SELL_TP2_Manual,
    Adv_SELL_TP3_Manual,
    Adv_SELL_TP4_Manual,
]

TRAINING_PENGUINS = [strategy for strategy in _ALL_TRAINING_PENGUINS if getattr(strategy, "TRAINABLE", False)]
TRAINING_MANUAL_PENGUINS = [strategy for strategy in _ALL_TRAINING_PENGUINS if not getattr(strategy, "TRAINABLE", False)]

# Saved alongside the run artifacts.
TRAINING_RESULTS_FILENAME = "trainable_penguin_training.json"
TRAINING_LOG_FILENAME = "trainable_penguin_training.log"
TRAINING_PARAMETER_LOG_FILENAME = "trainable_penguin_parameter_log.json"
TRAINING_PARAMETER_DELTA_FILENAME = "trainable_penguin_parameter_delta.txt"

# When enabled, save a Pareto-front PDF for the trainable strategies.
PLOT_PARETO = True
TRAINING_PARETO_FILENAME = "trainable_penguin_pareto_front.pdf"

__all__ = [
	"TRAINING_SYMBOLS",
	"TRAINING_STEP_ENABLED",
	"TRAINING_ITERATIONS",
	"TRAINING_SUBSET_MONTHS",
	"TRAINING_SUBSET_STOCKS",
	"TRAINING_RELATIVE_TO",
	"TRAINING_RANDOM_SEED",
    "TRAINING_START_DATE",
    "TRAINING_STOP_DATE",
	"Manual",
	"TRAINING_PENGUINS",
	"TRAINING_MANUAL_PENGUINS",
	"TRAINING_PARAMETER_DELTA_FILENAME",
	"TRAINING_RESULTS_FILENAME",
	"TRAINING_LOG_FILENAME",
	"TRAINING_PARAMETER_LOG_FILENAME",
	"PLOT_PARETO",
	"TRAINING_PARETO_FILENAME",
]