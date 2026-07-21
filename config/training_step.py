"""Configuration for the in-simulation training step."""
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
	TrainablePenguin5,
	TrainablePenguin5_Manual,
)

# Toggle the training pass that runs after strategy initialization.
TRAINING_STEP_ENABLED = True

# Number of optimization rounds per trainable strategy.
TRAINING_ITERATIONS = 100

# Training subsets are intentionally small to keep optimization tractable.
TRAINING_SUBSET_MONTHS = 2
TRAINING_SUBSET_STOCKS = 30

# Set to 0 for absolute profit or to a benchmark symbol like SPY for relative profit.
TRAINING_RELATIVE_TO = "SPY"

# Keep the search reproducible unless the user changes the seed.
TRAINING_RANDOM_SEED = 42

# When True, training loads its own time window instead of reusing the execution window.
# Separate training time window used when DIFFERENT_TRAINING_TIME is enabled.
DIFFERENT_TRAINING_TIME = False
TRAINING_START_DATE = "2024-01-01 0:00:00"
TRAINING_STOP_DATE = "2026-07-01 0:00:00"

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
	TrainablePenguin5,
]

TRAINING_MANUAL_PENGUINS = [
    TrainablePenguin1_Manual,
    TrainablePenguin2_Manual,
    TrainablePenguin3_Manual,
    TrainablePenguin4_Manual,
	TrainablePenguin5_Manual,
]

# Saved alongside the run artifacts.
TRAINING_RESULTS_FILENAME = "trainable_penguin_training.json"
TRAINING_LOG_FILENAME = "trainable_penguin_training.log"
TRAINING_PARAMETER_LOG_FILENAME = "trainable_penguin_parameter_log.json"
TRAINING_PARAMETER_DELTA_FILENAME = "trainable_penguin_parameter_delta.txt"

# Transaction cost used only by the training objective and training reports.
TRAINING_TRANSACTION_COST = 2.0

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
	"DIFFERENT_TRAINING_TIME",
	"TRAINING_START_DATE",
	"TRAINING_STOP_DATE",
	"Manual",
	"TRAINING_PENGUINS",
	"TRAINING_MANUAL_PENGUINS",
	"TRAINING_PARAMETER_DELTA_FILENAME",
	"TRAINING_RESULTS_FILENAME",
	"TRAINING_LOG_FILENAME",
	"TRAINING_PARAMETER_LOG_FILENAME",
	"TRAINING_TRANSACTION_COST",
	"PLOT_PARETO",
	"TRAINING_PARETO_FILENAME",
]