"""Parameter-search methods and ranges for trainable strategies."""
import inspect
import os

PARAMETER_SEARCH_METHODx = "bayesian_grid"  # Select: random, grid, bayesian, bayesian_grid, or rand_baysian.
_configured_search_method = os.getenv("PARAMETER_SEARCH_METHOD", PARAMETER_SEARCH_METHODx).strip().lower()
PARAMETER_SEARCH_METHOD = {
    "baysian": "bayesian",
    "baysian_grid": "bayesian_grid",
    "rand_bayesian": "rand_baysian",
}.get(_configured_search_method, _configured_search_method)

PARAMETER_SEARCH_BAYESIAN_SAMPLERx = "gp"
_configured_bayesian_sampler = os.getenv(
    "PARAMETER_SEARCH_BAYESIAN_SAMPLER",
    PARAMETER_SEARCH_BAYESIAN_SAMPLERx,
).strip().lower()
PARAMETER_SEARCH_BAYESIAN_SAMPLER = {
    "gaussian": "gp",
    "gaussian_process": "gp",
}.get(_configured_bayesian_sampler, _configured_bayesian_sampler)
if PARAMETER_SEARCH_BAYESIAN_SAMPLER not in {"gp", "tpe"}:
    raise ValueError(
        "Unsupported PARAMETER_SEARCH_BAYESIAN_SAMPLER: "
        f"{PARAMETER_SEARCH_BAYESIAN_SAMPLER}. Select 'gp' or 'tpe'."
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

# Each entry is (parameter name, type, minimum, maximum).
_RSI_PARAMETERS = (
    ("rsi_period", "int", 7, 40), #28->40
    ("buy_rsi", "float", 5.0, 42.0), #18->5.0
    ("sell_rsi", "float", 45.0, 88.0), #55->45
)

_BOLLINGER_PARAMETERS = (
    ("bb_period", "int", 10, 50), #40->50
    ("bb_stddev", "float", 1.0, 5), #3.5->5.0
)

_ADX_PARAMETERS = (
    ("adx_period", "int", 7, 35), #28->35
    ("adx_threshold", "float", 10.0, 60.0), #40->60.0
)

_RISK_PARAMETERS = (
    ("max_cash_fraction", "float", 0.02, 0.25), #0.20->0.25
    ("stop_loss_pct", "float", 0.01, 0.15), #0.10->0.15
    ("take_profit_pct", "float", 0.005, 0.20), #0.02->0.005
    ("cooldown_bars", "int", 0, 30),
)

_RELATIVE_STRENGTH_PARAMETERS = (
    ("relative_strength_period", "int", 7, 60), #40->60
    ("relative_strength_threshold", "float", -3.0, 1.0), # -1.0->-3.0
    ("rvol_period", "int", 3, 40), #7->3
    ("rvol_threshold", "float", 0.5, 6.0), #4.0->6.0
)

Trend_Method_parameters = (
    ("trend_reversal_threshold", "float", 0.0, 1.0),
    ("trend_negative_threshold", "float", 0.0, 1.0),
    ("trend_entry_threshold", "float", 0.0, 1.0),
)

_STRENGTH_CAP_PARAMETERS = (("strength_cap", "float", 1.0, 2.0),)

_RSI_ADX_PARAMETERS = _RSI_PARAMETERS + _ADX_PARAMETERS + _RISK_PARAMETERS
_BOLLINGER_ADX_PARAMETERS = _BOLLINGER_PARAMETERS + _ADX_PARAMETERS + _RISK_PARAMETERS
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
    if parameter_space is _PUFFIN_PARAMETERS:
        return _supported_parameters(strategy_class, parameter_space)
    return parameter_space


def strategy_parameter_space_by_name(strategy_name: str):
    """Return the configured search space for a strategy name."""
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
    "PARAMETER_SEARCH_METHOD",
    "PARAMETER_SEARCH_BAYESIAN_SAMPLER",
    "PARAMETER_SEARCH_BAYESIAN_ACQUISITION",
    "PARAMETER_SEARCH_BAYESIAN_UCB_KAPPA",
    "strategy_parameter_space",
    "strategy_parameter_space_by_name",
]