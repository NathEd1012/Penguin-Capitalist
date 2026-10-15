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
UPPERLIMIT_TIME_PERIOD = max(1, int(os.getenv("UPPERLIMIT_TIME_PERIOD", "1")))

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
    ("rsi_period", "int", 5, 25),
    ("buy_rsi", "float", 10.0, 40.0),
    ("sell_rsi", "float", 60.0, 90.0),
)

_NARROW_BOLLINGER_PARAMETERS = (
    ("bb_period", "int", 10, 50),
    ("bb_stddev", "float", 1.0, 4.0),
    ("upper_band_buffer", "float", 0.0, 0.25),
)

_NARROW_ADX_PARAMETERS = (
    ("adx_period", "int", 7, 30),
    ("adx_threshold", "float", 20.0, 40.0),
)

_NARROW_RISK_PARAMETERS = (
    ("max_cash_fraction", "float", 0.05, 0.20),
    ("stop_loss_pct", "float", 0.02, 0.10),
    ("take_profit_pct", "float", 0.03, 0.10),
    ("cooldown_bars", "int", 0, 100),
)

_NARROW_GENTOO_RISK_PARAMETERS = tuple(
    parameter for parameter in _NARROW_RISK_PARAMETERS if parameter[0] != "cooldown_bars"
)

_NARROW_RELATIVE_STRENGTH_PARAMETERS = (
    ("relative_strength_period", "int", 30, 390),
    ("relative_strength_threshold", "float", -1.0, 1.0),
    ("rvol_period", "int", 10, 60),
    ("rvol_threshold", "float", 1.5, 2.0),
)

_TREND_METHOD_PARAMETERS = (
    ("trend_reversal_threshold", "float", 0.0, 1.0),
    ("trend_negative_threshold", "float", 0.0, 1.0),
    ("trend_entry_threshold", "float", 1e-6, 1.0),
)


# Each entry is (parameter name, type, minimum, maximum).
_BROAD_RSI_PARAMETERS = (
    ("rsi_period", "int", 2, 50),
    ("buy_rsi", "float", 5.0, 50.0),
    ("sell_rsi", "float", 50.0, 100.0),
)

_BROAD_BOLLINGER_PARAMETERS = (
    ("bb_period", "int", 2, 100),
    ("bb_stddev", "float", 0.5, 8.0),
    ("upper_band_buffer", "float", 0.0, 1.0),
)

_BROAD_ADX_PARAMETERS = (
    ("adx_period", "int", 2, 50),
    ("adx_threshold", "float", 10.0, 70.0),
)

_BROAD_GENTOO_ADX_PARAMETERS = (
    ("adx_period", "int", 2, 50),
    ("adx_threshold", "float", 10.0, 70.0),
    ("adx_entry_threshold", "float", 10.0, 70.0),
    ("adx_negative_threshold", "float", 10.0, 70.0),
)

_BROAD_RISK_PARAMETERS = (
    ("max_cash_fraction", "float", 0.01, 0.50),
    ("stop_loss_pct", "float", 0.01, 0.20),
    ("take_profit_pct", "float", 0.005, 0.30),
    ("cooldown_bars", "int", 0, 100),
)

_BROAD_GENTOO_RISK_PARAMETERS = tuple(
    parameter for parameter in _BROAD_RISK_PARAMETERS if parameter[0] != "cooldown_bars"
)

_BROAD_RELATIVE_STRENGTH_PARAMETERS = (
    ("relative_strength_period", "int", 10, 360),
    ("relative_strength_threshold", "float", -5.0, 5.0),
    ("rvol_period", "int", 10, 120),
    ("rvol_threshold", "float", 0.5, 5.0),
)

if PARAMETER_SEARCH_RANGE_SET == "narrow":
    _RSI_PARAMETERS = _NARROW_RSI_PARAMETERS
    _BOLLINGER_PARAMETERS = _NARROW_BOLLINGER_PARAMETERS
    _ADX_PARAMETERS = _NARROW_ADX_PARAMETERS
    _GENTOO_ADX_PARAMETERS = (
        ("adx_period", "int", 7, 30),
        ("adx_threshold", "float", 20.0, 40.0),
        ("adx_entry_threshold", "float", 20.0, 40.0),
        ("adx_negative_threshold", "float", 10.0, 40.0),
    )
    _RISK_PARAMETERS = _NARROW_RISK_PARAMETERS
    _GENTOO_RISK_PARAMETERS = _NARROW_GENTOO_RISK_PARAMETERS
    _RELATIVE_STRENGTH_PARAMETERS = _NARROW_RELATIVE_STRENGTH_PARAMETERS
else:
    _RSI_PARAMETERS = _BROAD_RSI_PARAMETERS
    _BOLLINGER_PARAMETERS = _BROAD_BOLLINGER_PARAMETERS
    _ADX_PARAMETERS = _BROAD_ADX_PARAMETERS
    _GENTOO_ADX_PARAMETERS = _BROAD_GENTOO_ADX_PARAMETERS
    _RISK_PARAMETERS = _BROAD_RISK_PARAMETERS
    _GENTOO_RISK_PARAMETERS = _BROAD_GENTOO_RISK_PARAMETERS
    _RELATIVE_STRENGTH_PARAMETERS = _BROAD_RELATIVE_STRENGTH_PARAMETERS

Trend_Method_parameters = _TREND_METHOD_PARAMETERS

_STRENGTH_CAP_PARAMETERS = (("strength_cap", "float", 1.0, 2.0),)

_RSI_ADX_PARAMETERS = _RSI_PARAMETERS + _ADX_PARAMETERS + _RISK_PARAMETERS
_BOLLINGER_ADX_PARAMETERS = _BOLLINGER_PARAMETERS + _ADX_PARAMETERS + _RISK_PARAMETERS
_GENTOO_PARAMETERS = (
    _RSI_PARAMETERS
    + _GENTOO_ADX_PARAMETERS
    + _GENTOO_RISK_PARAMETERS
    + _RELATIVE_STRENGTH_PARAMETERS
)
_ROCKHOPPER_PARAMETERS = (
    _BOLLINGER_PARAMETERS
    + _GENTOO_RISK_PARAMETERS
    + _RELATIVE_STRENGTH_PARAMETERS
    + Trend_Method_parameters
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
_KING_PARAMETERS = (
    _EMPEROR_PARAMETERS
    + (
        ("sr_low_threshhold", "float", 0.0, 0.10),
        ("sr_high_threshhold", "float", 0.0, 0.10),
        ("sr_period", "int", 5, 200),
    )
)

_ALL_PARAMETER_SPACES = (
    _GENTOO_PARAMETERS,
    _ROCKHOPPER_PARAMETERS,
    _PUFFIN_PARAMETERS,
    _ADV_SELL_ALL_PARAMETERS,
    _EMPEROR_PARAMETERS,
    _KING_PARAMETERS,
)
MAX_PERIOD = max(
    UPPERLIMIT_TIME_PERIOD,
    max(
        maximum
        for parameter_space in _ALL_PARAMETER_SPACES
        for name, _parameter_type, _minimum, maximum in parameter_space
        if name.endswith("_period")
    ),
)


def _supported_parameters(strategy_class, parameter_space):
    signature = inspect.signature(strategy_class)
    if any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values()):
        return parameter_space

    accepted_parameters = set(signature.parameters)
    return tuple(
        parameter
        for parameter in parameter_space
        if parameter[0] in accepted_parameters
    )


def _apply_time_period_upper_limit(parameter_space):
    return tuple(
        (name, parameter_type, minimum, max(maximum, UPPERLIMIT_TIME_PERIOD))
        if name.endswith("_period")
        else (name, parameter_type, minimum, maximum)
        for name, parameter_type, minimum, maximum in parameter_space
    )


def strategy_parameter_space(strategy_class):
    """Return the configured search space for a strategy class."""
    strategy_name = strategy_class.__name__
    parameter_space = strategy_parameter_space_by_name(strategy_name)
    return _apply_time_period_upper_limit(_supported_parameters(strategy_class, parameter_space))


def has_parameter_search_space(strategy_class) -> bool:
    try:
        return bool(strategy_parameter_space(strategy_class))
    except ValueError:
        return False


def strategy_parameter_space_by_name(strategy_name: str):
    """Return the configured search space for a strategy name."""
    if strategy_name == "GentooPenguin":
        return _apply_time_period_upper_limit(_GENTOO_PARAMETERS)
    if strategy_name == "RockhopperPenguin":
        return _apply_time_period_upper_limit(_ROCKHOPPER_PARAMETERS)
    if strategy_name in {"Puffin1", "Puffin2", "Puffin3", "Puffin4"}:
        return _apply_time_period_upper_limit(_PUFFIN_PARAMETERS)
    if strategy_name == "Adv_SELL_ALL":
        return _apply_time_period_upper_limit(_ADV_SELL_ALL_PARAMETERS)
    if strategy_name == "EmperorPenguin":
        return _apply_time_period_upper_limit(_EMPEROR_PARAMETERS)
    if strategy_name == "KingPenguin":
        return _apply_time_period_upper_limit(_KING_PARAMETERS)
    if strategy_name.endswith((
        "Adv_SELL_TP1", "Adv_SELL_TP1_Manual",
        "ManualTuneAdvSELL_TP1", "ManualTuneAdvSELL_TP1_Manual",
    )):
        return _apply_time_period_upper_limit(_RSI_ADX_PARAMETERS + _RELATIVE_STRENGTH_PARAMETERS)
    if strategy_name.endswith((
        "Adv_SELL_TP2", "Adv_SELL_TP2_Manual", "Adv_SELL_TP3", "Adv_SELL_TP3_Manual",
        "ManualTuneAdvSELL_TP2", "ManualTuneAdvSELL_TP2_Manual",
        "ManualTuneAdvSELL_TP3", "ManualTuneAdvSELL_TP3_Manual",
    )):
        return _apply_time_period_upper_limit(_BOLLINGER_ADX_PARAMETERS + _RELATIVE_STRENGTH_PARAMETERS)
    if strategy_name.endswith(("OG_TP4", "OG_TP4_Manual")):
        return _apply_time_period_upper_limit(_RSI_RISK_PARAMETERS + _STRENGTH_CAP_PARAMETERS)
    if strategy_name.endswith((
        "Adv_SELL_TP4", "Adv_SELL_TP4_Manual",
        "ManualTuneAdvSELL_TP4", "ManualTuneAdvSELL_TP4_Manual",
    )):
        return _apply_time_period_upper_limit(_RSI_RISK_PARAMETERS + _RELATIVE_STRENGTH_PARAMETERS)
    if strategy_name.endswith(("OG_TP1", "OG_TP1_Manual", "TrainablePenguin1", "TrainablePenguin1_Manual")):
        return _apply_time_period_upper_limit(_RSI_ADX_PARAMETERS + _STRENGTH_CAP_PARAMETERS)
    if strategy_name.endswith((
        "OG_TP2", "OG_TP2_Manual", "TrainablePenguin2", "TrainablePenguin2_Manual",
        "OG_TP3", "OG_TP3_Manual", "TrainablePenguin3", "TrainablePenguin3_Manual",
    )):
        return _apply_time_period_upper_limit(_BOLLINGER_ADX_PARAMETERS + _STRENGTH_CAP_PARAMETERS)
    raise ValueError(f"No parameter space is defined for {strategy_name}")


__all__ = [
    "PARAMETERS_EXECUTED",
    "VALIDATION_CANDIDATES",
    "UPPERLIMIT_TIME_PERIOD",
    "MAX_PERIOD",
    "PARAMETER_SEARCH_METHOD",
    "PARAMETER_SEARCH_BAYESIAN_SAMPLER",
    "PARAMETER_SEARCH_BAYESIAN_ACQUISITION",
    "PARAMETER_SEARCH_BAYESIAN_UCB_KAPPA",
    "strategy_parameter_space",
    "strategy_parameter_space_by_name",
    "has_parameter_search_space",
]