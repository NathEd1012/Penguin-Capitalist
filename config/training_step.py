"""Configuration for the in-simulation training step."""
import os
from .symbols import SYMBOLS as TRAINING_SYMBOLS
from penguins import (
    TrainablePenguin1,
    TrainablePenguin1_Manual,
    TrainablePenguin2,
    TrainablePenguin2_Manual,
    TrainablePenguin3,
    TrainablePenguin3_Manual,
    TrainablePenguin4,
    TrainablePenguin4_Manual,
)

# Toggle the training pass that runs after strategy initialization.
TRAINING_STEP_ENABLED = True

# Number of optimization rounds per trainable strategy.
TRAINING_ITERATIONSX = 100
TRAINING_ITERATIONS = int(os.getenv("FIXED_TS", TRAINING_ITERATIONSX))

# Training subsets are intentionally small to keep optimization tractable.
TRAINING_SUBSET_MONTHSX = 2
TRAINING_SUBSET_MONTHS = int(os.getenv("FIXED_MONTH", TRAINING_SUBSET_MONTHSX))

TRAINING_SUBSET_STOCKSX = 30
TRAINING_SUBSET_STOCKS = int(os.getenv("FIXED_SYMB", TRAINING_SUBSET_STOCKSX))


# Match the training objective's per-buy cost penalty.
TRAINING_TRANSACTION_COST = 2.0

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

# These are the only strategies that participate in parameter search.
# The matching manual variants are executed separately with their starting
# parameters so the final report can compare baseline vs trained behavior.
TRAINING_PENGUINS = [
    TrainablePenguin1,
    TrainablePenguin2,
    TrainablePenguin3,
    TrainablePenguin4,
]

TRAINING_MANUAL_PENGUINS = [
    TrainablePenguin1_Manual,
    TrainablePenguin2_Manual,
    TrainablePenguin3_Manual,
    TrainablePenguin4_Manual,
]

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