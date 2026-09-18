"""Parameter-search methods and ranges for trainable strategies."""
import os

PARAMETER_SEARCH_METHODx = "bayesian_grid"  # Select: random, grid, bayesian, bayesian_grid, or rand_baysian.
_configured_search_method = os.getenv("PARAMETER_SEARCH_METHOD", PARAMETER_SEARCH_METHODx).strip().lower()
PARAMETER_SEARCH_METHOD = {
    "baysian": "bayesian",
    "baysian_grid": "bayesian_grid",
    "rand_bayesian": "rand_baysian",
}.get(_configured_search_method, _configured_search_method)

PARAMETER_SEARCH_WARMUP_TRIALSx = 4
PARAMETER_SEARCH_WARMUP_TRIALS = int(os.getenv("PARAMETER_SEARCH_WARMUP_TRIALS", PARAMETER_SEARCH_WARMUP_TRIALSx))

# Number of initial proposals before Bayesian search takes over.

# Bayesian-search controls.
PARAMETER_SEARCH_BAYESIAN_MIN_WARMUP_TRIALS = 4
PARAMETER_SEARCH_BAYESIAN_CANDIDATE_POOL_SIZE = 64
PARAMETER_SEARCH_BAYESIAN_LOCAL_CANDIDATE_COUNT = 32
PARAMETER_SEARCH_BAYESIAN_LOCAL_JITTER = 0.08
PARAMETER_SEARCH_BAYESIAN_LENGTH_SCALE = 0.35
PARAMETER_SEARCH_BAYESIAN_OBSERVATION_NOISE = 0.15

PARAMETERS_EXECUTED = max(1, int(os.getenv("PARAMETERS_EXECUTED", "1")))

# Each entry is (parameter name, type, minimum, maximum).
_RSI_PARAMETERS = (
    ("rsi_period", "int", 7, 30), #28->30
    ("buy_rsi", "float", 18.0, 42.0),
    ("sell_rsi", "float", 55.0, 88.0),
)

_BOLLINGER_PARAMETERS = (
    ("bb_period", "int", 10, 50), #40->50
    ("bb_stddev", "float", 1.0, 3.5),
)

_ADX_PARAMETERS = (
    ("adx_period", "int", 7, 28),
    ("adx_threshold", "float", 10.0, 40.0),
)

_RISK_PARAMETERS = (
    ("max_cash_fraction", "float", 0.02, 0.25), #0.20->0.25
    ("stop_loss_pct", "float", 0.01, 0.10),
    ("take_profit_pct", "float", 0.02, 0.20),
    ("cooldown_bars", "int", 0, 30),
)

_RELATIVE_STRENGTH_PARAMETERS = (
    ("relative_strength_period", "int", 7, 50), #40->50
    ("relative_strength_threshold", "float", -1.5, 1.0), # -1.0->-1.5
    ("rvol_period", "int", 7, 40),
    ("rvol_threshold", "float", 0.5, 6.0), #4.0->6.0
)

_STRENGTH_CAP_PARAMETERS = (("strength_cap", "float", 1.0, 2.0),)

_RSI_ADX_PARAMETERS = _RSI_PARAMETERS + _ADX_PARAMETERS + _RISK_PARAMETERS
_BOLLINGER_ADX_PARAMETERS = _BOLLINGER_PARAMETERS + _ADX_PARAMETERS + _RISK_PARAMETERS
_RSI_RISK_PARAMETERS = _RSI_PARAMETERS + _RISK_PARAMETERS
_ADV_SELL_ALL_PARAMETERS = (
    _RSI_PARAMETERS
    + _BOLLINGER_PARAMETERS
    + _ADX_PARAMETERS
    + _RISK_PARAMETERS
    + _RELATIVE_STRENGTH_PARAMETERS
)


def strategy_parameter_space(strategy_class):
    """Return the configured search space for a strategy class."""
    strategy_name = strategy_class.__name__
    if strategy_name == "Adv_SELL_ALL":
        return _ADV_SELL_ALL_PARAMETERS
    if strategy_name.endswith((
        "Adv_SELL_TP1", "Adv_SELL_TP1_Manual",
        "ManualTuneAdvSELL_TP1", "ManualTuneAdvSELL_TP1_Manual",
    )):
        return _RSI_ADX_PARAMETERS + _RELATIVE_STRENGTH_PARAMETERS
    if strategy_name.endswith((
        "Adv_SELL_TP2", "Adv_SELL_TP2_Manual", "Adv_SELL_TP3", "Adv_SELL_TP3_Manual",
        "ManualTuneAdvSELL_TP2", "ManualTuneAdvSELL_TP2_Manual",
        "ManualTuneAdvSELL_TP3", "ManualTuneAdvSELL_TP3_Manual",
    )):
        return _BOLLINGER_ADX_PARAMETERS + _RELATIVE_STRENGTH_PARAMETERS
    if strategy_name.endswith(("OG_TP4", "OG_TP4_Manual")):
        return _RSI_RISK_PARAMETERS + _STRENGTH_CAP_PARAMETERS
    if strategy_name.endswith((
        "Adv_SELL_TP4", "Adv_SELL_TP4_Manual",
        "ManualTuneAdvSELL_TP4", "ManualTuneAdvSELL_TP4_Manual",
    )):
        return _RSI_RISK_PARAMETERS + _RELATIVE_STRENGTH_PARAMETERS
    if strategy_name.endswith(("OG_TP1", "OG_TP1_Manual", "TrainablePenguin1", "TrainablePenguin1_Manual")):
        return _RSI_ADX_PARAMETERS + _STRENGTH_CAP_PARAMETERS
    if strategy_name.endswith((
        "OG_TP2", "OG_TP2_Manual", "TrainablePenguin2", "TrainablePenguin2_Manual",
        "OG_TP3", "OG_TP3_Manual", "TrainablePenguin3", "TrainablePenguin3_Manual",
    )):
        return _BOLLINGER_ADX_PARAMETERS + _STRENGTH_CAP_PARAMETERS
    raise ValueError(f"No parameter space is defined for {strategy_name}")


__all__ = [
    "PARAMETERS_EXECUTED",
    "PARAMETER_SEARCH_METHOD",
    "PARAMETER_SEARCH_GRID_POINTS",
    "PARAMETER_SEARCH_BAYESIAN_MIN_WARMUP_TRIALS",
    "PARAMETER_SEARCH_BAYESIAN_CANDIDATE_POOL_SIZE",
    "PARAMETER_SEARCH_BAYESIAN_LOCAL_CANDIDATE_COUNT",
    "PARAMETER_SEARCH_BAYESIAN_LOCAL_JITTER",
    "PARAMETER_SEARCH_BAYESIAN_LENGTH_SCALE",
    "PARAMETER_SEARCH_BAYESIAN_OBSERVATION_NOISE",
    "strategy_parameter_space",
]