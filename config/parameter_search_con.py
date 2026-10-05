"""Parameter-search methods and ranges for trainable strategies."""
import inspect
import os

PARAMETER_SEARCH_METHODx = "bayesian_rand"  # Select: random, grid, bayesian, bayesian_grid, or bayesian_rand.
_configured_search_method = os.getenv("PARAMETER_SEARCH_METHOD", PARAMETER_SEARCH_METHODx).strip().lower()
PARAMETER_SEARCH_METHOD = _configured_search_method

PARAMETER_SEARCH_BAYESIAN_SAMPLERx = "gp"
_configured_bayesian_sampler = os.getenv(
    "PARAMETER_SEARCH_BAYESIAN_SAMPLER",
    PARAMETER_SEARCH_BAYESIAN_SAMPLERx,
).strip().lower()
PARAMETER_SEARCH_BAYESIAN_SAMPLER = {
    "gaussian": "gp",
    "gaussian_process": "gp",
    "cma": "cmaes",
    "cma_es": "cmaes",
    "cma-es": "cmaes",
}.get(_configured_bayesian_sampler, _configured_bayesian_sampler)
if PARAMETER_SEARCH_BAYESIAN_SAMPLER not in {"gp", "tpe", "cmaes"}:
    raise ValueError(
        "Unsupported PARAMETER_SEARCH_BAYESIAN_SAMPLER: "
        f"{PARAMETER_SEARCH_BAYESIAN_SAMPLER}. Select 'gp', 'tpe', or 'cmaes'."
    )

PARAMETER_SEARCH_BAYESIAN_ACQUISITIONx = "ei"
PARAMETER_SEARCH_BAYESIAN_ACQUISITION = os.getenv(
    "PARAMETER_SEARCH_BAYESIAN_ACQUISITION",
    PARAMETER_SEARCH_BAYESIAN_ACQUISITIONx,
).strip().lower()
if PARAMETER_SEARCH_BAYESIAN_ACQUISITION not in {"ei", "ucb"}:
    raise ValueError(
        "Unsupported PARAMETER_SEARCH_BAYESIAN_ACQUISITION: "
        f"{PARAMETER_SEARCH_BAYESIAN_ACQUISITION}. Select 'ei' or 'ucb'."
    )
if PARAMETER_SEARCH_BAYESIAN_ACQUISITION == "ucb" and PARAMETER_SEARCH_BAYESIAN_SAMPLER != "gp":
    raise ValueError("UCB acquisition requires PARAMETER_SEARCH_BAYESIAN_SAMPLER=gp.")

PARAMETER_SEARCH_BAYESIAN_UCB_KAPPA = float(
    os.getenv("PARAMETER_SEARCH_BAYESIAN_UCB_KAPPA", "2.0")
)
if PARAMETER_SEARCH_BAYESIAN_UCB_KAPPA <= 0:
    raise ValueError("PARAMETER_SEARCH_BAYESIAN_UCB_KAPPA must be positive.")

PARAMETER_SEARCH_WARMUP_TRIALSx = 4
PARAMETER_SEARCH_WARMUP_TRIALS = int(os.getenv("PARAMETER_SEARCH_WARMUP_TRIALS", PARAMETER_SEARCH_WARMUP_TRIALSx))

PARAMETERS_EXECUTED = max(1, int(os.getenv("PARAMETERS_EXECUTED", "1")))
VALIDATION_CANDIDATES = max(1, int(os.getenv("VALIDATION_CANDIDATES", "10")))

PARAMETER_SEARCH_RANGE_SETx = "broad"
PARAMETER_SEARCH_RANGE_SET = os.getenv(
    "PARAMETER_SEARCH_RANGE_SET",
    PARAMETER_SEARCH_RANGE_SETx,
).strip().lower()
if PARAMETER_SEARCH_RANGE_SET not in {"narrow", "broad"}:
    raise ValueError(
        "Unsupported PARAMETER_SEARCH_RANGE_SET: "
        f"{PARAMETER_SEARCH_RANGE_SET}. Select 'narrow' or 'broad'."
    )

# Each entry is (parameter name, type, minimum, maximum).
_NARROW_RSI_PARAMETERS = (
    ("rsi_period", "int", 7, 40), #28->40
    ("buy_rsi", "float", 5.0, 42.0), #18->5.0
    ("sell_rsi", "float", 45.0, 88.0), #55->45
)

_NARROW_BOLLINGER_PARAMETERS = (
    ("bb_period", "int", 10, 50), #40->50
    ("bb_stddev", "float", 1.0, 5), #3.5->5.0
)

_NARROW_ADX_PARAMETERS = (
    ("adx_period", "int", 7, 35), #28->35
    ("adx_threshold", "float", 10.0, 60.0), #40->60.0
)

_NARROW_RISK_PARAMETERS = (
    ("max_cash_fraction", "float", 0.02, 0.25), #0.20->0.25
    ("stop_loss_pct", "float", 0.01, 0.15), #0.10->0.15
    ("take_profit_pct", "float", 0.005, 0.20), #0.02->0.005
    ("cooldown_bars", "int", 0, 30),
)

_NARROW_SIMPLER_RISK_PARAMETERS = tuple(
    parameter for parameter in _NARROW_RISK_PARAMETERS if parameter[0] != "cooldown_bars"
)

_NARROW_RELATIVE_STRENGTH_PARAMETERS = (
    ("relative_strength_period", "int", 7, 60), #40->60
    ("relative_strength_threshold", "float", -3.0, 1.0), # -1.0->-3.0
    ("rvol_period", "int", 3, 40), #7->3
    ("rvol_threshold", "float", 0.5, 6.0), #4.0->6.0
)

_TREND_METHOD_PARAMETERS = (
    ("trend_reversal_threshold", "float", 0.0, 1.0),
    ("trend_negative_threshold", "float", 0.0, 1.0),
    ("trend_entry_threshold", "float", 0.0, 1.0),
)


# Each entry is (parameter name, type, minimum, maximum).
_BROAD_RSI_PARAMETERS = (
    ("rsi_period", "int", 0, 50), #28->40
    ("buy_rsi", "float", 0.0, 50.0), #18->5.0
    ("sell_rsi", "float", 30.0, 100.0), #55->45
)

_BROAD_BOLLINGER_PARAMETERS = (
    ("bb_period", "int", 0, 80), #40->50
    ("bb_stddev", "float", 0.0, 10.0), #3.5->5.0
)

_BROAD_ADX_PARAMETERS = (
    ("adx_period", "int", 0, 50), #28->35
    ("adx_threshold", "float", 0.0, 80.0), #40->60.0
)

_BROAD_RISK_PARAMETERS = (
    ("max_cash_fraction", "float", 0.001, 0.5), #0.20->0.25
    ("stop_loss_pct", "float", 0.001, 0.5), #0.10->0.15
    ("take_profit_pct", "float", 0.001, 0.50), #0.02->0.005
    ("cooldown_bars", "int", 0, 100),
)

_BROAD_SIMPLER_RISK_PARAMETERS = tuple(
    parameter for parameter in _BROAD_RISK_PARAMETERS if parameter[0] != "cooldown_bars"
)

_BROAD_RELATIVE_STRENGTH_PARAMETERS = (
    ("relative_strength_period", "int", 0, 100), #40->60
    ("relative_strength_threshold", "float", -5.0, 5.0), # -1.0->-3.0
    ("rvol_period", "int", 0, 60), #7->3
    ("rvol_threshold", "float", 0.0, 10.0), #4.0->6.0
)

if PARAMETER_SEARCH_RANGE_SET == "narrow":
    _RSI_PARAMETERS = _NARROW_RSI_PARAMETERS
    _BOLLINGER_PARAMETERS = _NARROW_BOLLINGER_PARAMETERS
    _ADX_PARAMETERS = _NARROW_ADX_PARAMETERS
    _RISK_PARAMETERS = _NARROW_RISK_PARAMETERS
    _SIMPLER_RISK_PARAMETERS = _NARROW_SIMPLER_RISK_PARAMETERS
    _RELATIVE_STRENGTH_PARAMETERS = _NARROW_RELATIVE_STRENGTH_PARAMETERS
else:
    _RSI_PARAMETERS = _BROAD_RSI_PARAMETERS
    _BOLLINGER_PARAMETERS = _BROAD_BOLLINGER_PARAMETERS
    _ADX_PARAMETERS = _BROAD_ADX_PARAMETERS
    _RISK_PARAMETERS = _BROAD_RISK_PARAMETERS
    _SIMPLER_RISK_PARAMETERS = _BROAD_SIMPLER_RISK_PARAMETERS
    _RELATIVE_STRENGTH_PARAMETERS = _BROAD_RELATIVE_STRENGTH_PARAMETERS

Trend_Method_parameters = _TREND_METHOD_PARAMETERS

_STRENGTH_CAP_PARAMETERS = (("strength_cap", "float", 1.0, 2.0),)

_RSI_ADX_PARAMETERS = _RSI_PARAMETERS + _ADX_PARAMETERS + _RISK_PARAMETERS
_BOLLINGER_ADX_PARAMETERS = _BOLLINGER_PARAMETERS + _ADX_PARAMETERS + _RISK_PARAMETERS
_SIMPLER_PARAMETERS = (
    _BOLLINGER_PARAMETERS
    + _ADX_PARAMETERS
    + _SIMPLER_RISK_PARAMETERS
    + _RELATIVE_STRENGTH_PARAMETERS
    + (("trend_score_threshold", "float", 0.0, 1.0),)
)
_RSI_RISK_PARAMETERS = _RSI_PARAMETERS + _RISK_PARAMETERS
_PUFFIN_PARAMETERS = (
    _RSI_PARAMETERS
    + _BOLLINGER_PARAMETERS
    + Trend_Method_parameters
    + _ADX_PARAMETERS
    + _RISK_PARAMETERS
    + _RELATIVE_STRENGTH_PARAMETERS
)
_ADV_SELL_ALL_PARAMETERS = (
    _RSI_PARAMETERS
    + _BOLLINGER_PARAMETERS
    + _ADX_PARAMETERS
    + _RISK_PARAMETERS
    + _RELATIVE_STRENGTH_PARAMETERS
)
_EMPEROR_PARAMETERS = (
    _ADV_SELL_ALL_PARAMETERS
    + Trend_Method_parameters
)


def _supported_parameters(strategy_class, parameter_space):
    signature = inspect.signature(strategy_class)
    if any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values()):
        for parent_class in strategy_class.__mro__[1:]:
            parent_signature = inspect.signature(parent_class)
            if not any(
                parameter.kind is inspect.Parameter.VAR_KEYWORD
                for parameter in parent_signature.parameters.values()
            ):
                signature = parent_signature
                break
        else:
            return parameter_space

    accepted_parameters = set(signature.parameters)
    return tuple(
        parameter
        for parameter in parameter_space
        if parameter[0] in accepted_parameters
    )


def strategy_parameter_space(strategy_class):
    """Return the configured search space for a strategy class."""
    strategy_name = strategy_class.__name__
    parameter_space = strategy_parameter_space_by_name(strategy_name)
    return _supported_parameters(strategy_class, parameter_space)


def strategy_parameter_space_by_name(strategy_name: str):
    """Return the configured search space for a strategy name."""
    if strategy_name == "Simpler_Penguin":
        return _SIMPLER_PARAMETERS
    if strategy_name in {"Puffin1", "Puffin2", "Puffin3", "Puffin4"}:
        return _PUFFIN_PARAMETERS
    if strategy_name == "Adv_SELL_ALL":
        return _ADV_SELL_ALL_PARAMETERS
    if strategy_name == "Emperor_Penguin":
        return _EMPEROR_PARAMETERS
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
    "VALIDATION_CANDIDATES",
    "PARAMETER_SEARCH_METHOD",
    "PARAMETER_SEARCH_BAYESIAN_SAMPLER",
    "PARAMETER_SEARCH_BAYESIAN_ACQUISITION",
    "PARAMETER_SEARCH_BAYESIAN_UCB_KAPPA",
    "strategy_parameter_space",
    "strategy_parameter_space_by_name",
]