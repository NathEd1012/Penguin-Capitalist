"""Configuration for the in-simulation training step."""

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
TRAINING_ITERATIONS = 3

# Training subsets are intentionally small to keep optimization tractable.
TRAINING_SUBSET_MONTHS = 2
TRAINING_SUBSET_STOCKS = 30

# Match the training objective's per-buy cost penalty.
TRAINING_TRANSACTION_COST = 2.0

# Benchmark symbol used to score performance relative to SPY.
TRAINING_BENCHMARK_SYMBOL = "SPY"

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
    "TRAINING_STEP_ENABLED",
    "TRAINING_ITERATIONS",
    "TRAINING_SUBSET_MONTHS",
    "TRAINING_SUBSET_STOCKS",
    "TRAINING_TRANSACTION_COST",
    "TRAINING_BENCHMARK_SYMBOL",
    "TRAINING_RANDOM_SEED",
    "Manual",
    "TRAINING_PENGUINS",
    "TRAINING_MANUAL_PENGUINS",
    "TRAINING_RESULTS_FILENAME",
    "TRAINING_LOG_FILENAME",
    "TRAINING_PARAMETER_LOG_FILENAME",
    "TRAINING_PARAMETER_DELTA_FILENAME",
    "PLOT_PARETO",
    "TRAINING_PARETO_FILENAME",
]