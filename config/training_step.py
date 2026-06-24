"""Configuration for the in-simulation training step."""

from penguins import TrainablePenguin1, TrainablePenguin2

# Toggle the training pass that runs after strategy initialization.
TRAINING_STEP_ENABLED = True

# Number of optimization rounds per trainable strategy.
TRAINING_ITERATIONS = 2

# Training subsets are intentionally small to keep optimization tractable.
TRAINING_SUBSET_MONTHS = 2
TRAINING_SUBSET_STOCKS = 30

# Match the training objective's per-buy cost penalty.
TRAINING_TRANSACTION_COST = 1.0

# Benchmark symbol used to score performance relative to SPY.
TRAINING_BENCHMARK_SYMBOL = "SPY"

# Keep the search reproducible unless the user changes the seed.
TRAINING_RANDOM_SEED = 42

# The trainable strategies that participate in the optimization pass.
TRAINABLE_PENGUINS = [
    TrainablePenguin1,
    TrainablePenguin2,
]

# Saved alongside the run artifacts.
TRAINING_RESULTS_FILENAME = "trainable_penguin_training.json"
TRAINING_LOG_FILENAME = "trainable_penguin_training.log"
TRAINING_PARAMETER_LOG_FILENAME = "trainable_penguin_parameter_log.json"

__all__ = [
    "TRAINING_STEP_ENABLED",
    "TRAINING_ITERATIONS",
    "TRAINING_SUBSET_MONTHS",
    "TRAINING_SUBSET_STOCKS",
    "TRAINING_TRANSACTION_COST",
    "TRAINING_BENCHMARK_SYMBOL",
    "TRAINING_RANDOM_SEED",
    "TRAINABLE_PENGUINS",
    "TRAINING_RESULTS_FILENAME",
    "TRAINING_LOG_FILENAME",
    "TRAINING_PARAMETER_LOG_FILENAME",
]