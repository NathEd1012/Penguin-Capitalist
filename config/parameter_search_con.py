"""Parameter-search methods, ranges, and strategy assignments."""
import inspect
import os


# Search modes:
#   gp_ei  - Gaussian Process with Expected Improvement
#   gp_ucb - Gaussian Process with Upper Confidence Bound
#   tpe    - Tree-structured Parzen Estimator
#   cmaes  - Covariance Matrix Adaptation Evolution Strategy
SEARCH_STRATEGIES = {
   "gp_ei": {"sampler": "gp", "acquisition": "ei"},
   "gp_ucb": {"sampler": "gp", "acquisition": "ucb"},
   "tpe": {"sampler": "tpe", "acquisition": "ei"},
   "cmaes": {"sampler": "cmaes", "acquisition": "ei"},
}

PARAMETER_SEARCH_METHOD = os.getenv(
   "PARAMETER_SEARCH_METHOD", "bayesian_rand"
).strip().lower()
PARAMETER_SEARCH_BAYESIAN_SAMPLER = os.getenv(
   "PARAMETER_SEARCH_BAYESIAN_SAMPLER", "gp"
).strip().lower()
PARAMETER_SEARCH_BAYESIAN_SAMPLER = {
   "gaussian": "gp",
   "gaussian_process": "gp",
   "cma": "cmaes",
   "cma_es": "cmaes",
   "cma-es": "cmaes",
}.get(PARAMETER_SEARCH_BAYESIAN_SAMPLER, PARAMETER_SEARCH_BAYESIAN_SAMPLER)
PARAMETER_SEARCH_BAYESIAN_ACQUISITION = os.getenv(
   "PARAMETER_SEARCH_BAYESIAN_ACQUISITION", "ei"
).strip().lower()

if PARAMETER_SEARCH_BAYESIAN_SAMPLER not in {"gp", "tpe", "cmaes"}:
    raise ValueError(
       f"Unsupported Bayesian sampler: {PARAMETER_SEARCH_BAYESIAN_SAMPLER}. "
       "Choose gp, tpe, or cmaes."
    )
if PARAMETER_SEARCH_BAYESIAN_ACQUISITION not in {"ei", "ucb"}:
   raise ValueError(
       f"Unsupported Bayesian acquisition: {PARAMETER_SEARCH_BAYESIAN_ACQUISITION}. "
       "Choose ei or ucb."
   )
if PARAMETER_SEARCH_BAYESIAN_ACQUISITION == "ucb" and PARAMETER_SEARCH_BAYESIAN_SAMPLER != "gp":
   raise ValueError("UCB acquisition requires the gp sampler.")

PARAMETER_SEARCH_BAYESIAN_UCB_KAPPA = float(
   os.getenv("PARAMETER_SEARCH_BAYESIAN_UCB_KAPPA", "2.0")
)
if PARAMETER_SEARCH_BAYESIAN_UCB_KAPPA <= 0:
   raise ValueError("PARAMETER_SEARCH_BAYESIAN_UCB_KAPPA must be positive.")

PARAMETER_SEARCH_WARMUP_TRIALS = int(os.getenv("PARAMETER_SEARCH_WARMUP_TRIALS", "4"))
PARAMETERS_EXECUTED = max(1, int(os.getenv("PARAMETERS_EXECUTED", "1")))
VALIDATION_CANDIDATES = max(1, int(os.getenv("VALIDATION_CANDIDATES", "10")))

PARAMETER_SEARCH_RANGE_SET = os.getenv(
   "PARAMETER_SEARCH_RANGE_SET", "broad"
).strip().lower()
if PARAMETER_SEARCH_RANGE_SET not in {"narrow", "broad"}:
    raise ValueError(
       f"Unsupported parameter range set: {PARAMETER_SEARCH_RANGE_SET}. "
       "Choose narrow or broad."
    )

PARAMETER_SEARCH_STRATEGY = next(
    (
       name
       for name, settings in SEARCH_STRATEGIES.items()
       if settings["sampler"] == PARAMETER_SEARCH_BAYESIAN_SAMPLER
       and settings["acquisition"] == PARAMETER_SEARCH_BAYESIAN_ACQUISITION
    ),
    "custom",
)

# Every supported parameter is defined once in each range set.
# Each entry is (parameter name, type, minimum, maximum).
NARROW_PARAMETER_RANGES = (
    ("rsi_period", "int", 5, 25),
    ("buy_rsi", "float", 10.0, 40.0),
    ("sell_rsi", "float", 60.0, 90.0),
    ("bb_period", "int", 10, 50),
    ("bb_stddev", "float", 1.0, 4.0),
    ("upper_band_buffer", "float", 0.0, 0.25),
    ("kaufman_efficiency_ratio_period", "int", 7, 30),
    ("kaufman_efficiency_ratio_threshold", "float", 20.0, 40.0),
    ("kaufman_efficiency_ratio_entry_threshold", "float", 20.0, 40.0),
    ("kaufman_efficiency_ratio_negative_threshold", "float", 10.0, 40.0),
    ("max_cash_fraction", "float", 0.05, 0.20),
    ("stop_loss_pct", "float", 0.02, 0.10),
    ("take_profit_pct", "float", 0.03, 0.10),
    ("cooldown_bars", "int", 0, 100),
    ("relative_performance_period", "int", 30, 100),
    ("relative_performance_threshold", "float", -1.0, 1.0),
    ("rvol_period", "int", 10, 60),
    ("rvol_threshold", "float", 1.5, 2.0),
    ("trend_reversal_threshold", "float", 0.0, 1.0),
    ("trend_negative_threshold", "float", 0.0, 1.0),
    ("trend_entry_threshold", "float", 1e-6, 1.0),
    ("sr_low_threshhold", "float", 0.0, 0.10),
    ("sr_high_threshhold", "float", 0.0, 0.10),
    ("sr_period", "int", 5, 100),
    ("strength_cap", "float", 1.0, 2.0),
)

BROAD_PARAMETER_RANGES = (
    ("rsi_period", "int", 2, 50),
    ("buy_rsi", "float", 5.0, 50.0),
    ("sell_rsi", "float", 50.0, 100.0),
    ("bb_period", "int", 2, 100),
    ("bb_stddev", "float", 0.5, 8.0),
    ("upper_band_buffer", "float", 0.0, 1.0),
    ("kaufman_efficiency_ratio_period", "int", 2, 50),
    ("kaufman_efficiency_ratio_threshold", "float", 10.0, 70.0),
    ("kaufman_efficiency_ratio_entry_threshold", "float", 10.0, 70.0),
    ("kaufman_efficiency_ratio_negative_threshold", "float", 10.0, 70.0),
    ("max_cash_fraction", "float", 0.01, 0.50),
    ("stop_loss_pct", "float", 0.01, 0.20),
    ("take_profit_pct", "float", 0.005, 0.30),
    ("cooldown_bars", "int", 0, 100),
    ("relative_performance_period", "int", 10, 360),
    ("relative_performance_threshold", "float", -5.0, 5.0),
    ("rvol_period", "int", 10, 120),
    ("rvol_threshold", "float", 0.5, 5.0),
    ("trend_reversal_threshold", "float", 0.0, 1.0),
    ("trend_negative_threshold", "float", 0.0, 1.0),
    ("trend_entry_threshold", "float", 1e-6, 1.0),
    ("sr_low_threshhold", "float", 0.0, 0.10),
    ("sr_high_threshhold", "float", 0.0, 0.10),
    ("sr_period", "int", 5, 200),
    ("strength_cap", "float", 1.0, 2.0),
)


def _range_lookup(parameter_ranges):
    return {parameter[0]: parameter for parameter in parameter_ranges}


_NARROW_RANGES = _range_lookup(NARROW_PARAMETER_RANGES)
_BROAD_RANGES = _range_lookup(BROAD_PARAMETER_RANGES)
_ACTIVE_RANGES = (
    _NARROW_RANGES
    if PARAMETER_SEARCH_RANGE_SET == "narrow"
    else _BROAD_RANGES
)


# Parameter assignment by strategy. Names are resolved against the active
# narrow or broad range list above.
STRATEGY_PARAMETER_NAMES = {
    "GentooPenguin": (
        "rsi_period", "buy_rsi", "sell_rsi",
        "kaufman_efficiency_ratio_period", "kaufman_efficiency_ratio_threshold", "kaufman_efficiency_ratio_entry_threshold",
        "kaufman_efficiency_ratio_negative_threshold", "max_cash_fraction", "stop_loss_pct",
        "take_profit_pct", "relative_performance_period",
        "relative_performance_threshold", "rvol_period", "rvol_threshold",
    ),
    "RockhopperPenguin": (
        "bb_period", "bb_stddev", "upper_band_buffer",
        "max_cash_fraction", "stop_loss_pct", "take_profit_pct",
        "relative_performance_period", "relative_performance_threshold",
        "rvol_period", "rvol_threshold", "trend_reversal_threshold",
        "trend_negative_threshold", "trend_entry_threshold",
    ),
    "EmperorPenguin": (
        "rsi_period", "buy_rsi", "sell_rsi", "bb_period", "bb_stddev",
        "upper_band_buffer", "kaufman_efficiency_ratio_period", "kaufman_efficiency_ratio_threshold",
        "trend_reversal_threshold", "trend_negative_threshold",
        "trend_entry_threshold", "max_cash_fraction", "stop_loss_pct",
        "take_profit_pct", "cooldown_bars", "relative_performance_period",
        "relative_performance_threshold", "rvol_period", "rvol_threshold",
    ),
    "KingPenguin": (
        "rsi_period", "buy_rsi", "sell_rsi", "bb_period", "bb_stddev",
        "upper_band_buffer", "kaufman_efficiency_ratio_period", "kaufman_efficiency_ratio_threshold",
        "trend_reversal_threshold", "trend_negative_threshold",
        "trend_entry_threshold", "max_cash_fraction", "stop_loss_pct",
        "take_profit_pct", "cooldown_bars", "relative_performance_period",
        "relative_performance_threshold", "rvol_period", "rvol_threshold",
        "sr_low_threshhold", "sr_high_threshhold", "sr_period",
    ),
}

_LEGACY_PARAMETER_NAMES = {
    "rsi_kaufman_efficiency_ratio": (
        "rsi_period", "buy_rsi", "sell_rsi", "kaufman_efficiency_ratio_period", "kaufman_efficiency_ratio_threshold",
        "max_cash_fraction", "stop_loss_pct", "take_profit_pct", "cooldown_bars",
    ),
    "bollinger_kaufman_efficiency_ratio": (
        "bb_period", "bb_stddev", "upper_band_buffer", "kaufman_efficiency_ratio_period",
        "kaufman_efficiency_ratio_threshold", "max_cash_fraction", "stop_loss_pct",
        "take_profit_pct", "cooldown_bars",
    ),
    "rsi_risk": (
        "rsi_period", "buy_rsi", "sell_rsi", "max_cash_fraction",
        "stop_loss_pct", "take_profit_pct", "cooldown_bars",
    ),
    "advanced_sell_all": (
        "rsi_period", "buy_rsi", "sell_rsi", "bb_period", "bb_stddev",
        "upper_band_buffer", "kaufman_efficiency_ratio_period", "kaufman_efficiency_ratio_threshold",
        "max_cash_fraction", "stop_loss_pct", "take_profit_pct",
        "cooldown_bars", "relative_performance_period",
        "relative_performance_threshold", "rvol_period", "rvol_threshold",
    ),
}


def _parameters(names):
    return tuple(_ACTIVE_RANGES[name] for name in names)


def _supported_parameters(strategy_class, parameter_space):
    signature = inspect.signature(strategy_class)
    if any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    ):
        return parameter_space

    accepted_parameters = set(signature.parameters)
    return tuple(
        parameter
        for parameter in parameter_space
        if parameter[0] in accepted_parameters
    )


def strategy_parameter_space(strategy_class):
    """Return the active configured search space for a strategy class."""
    return _supported_parameters(
        strategy_class,
        strategy_parameter_space_by_name(strategy_class.__name__),
    )


def has_parameter_search_space(strategy_class) -> bool:
    try:
        return bool(strategy_parameter_space(strategy_class))
    except ValueError:
        return False


def max_period_for_strategies(strategy_classes) -> int:
    """Return the largest period required by the supplied strategies.

    Instances use their sampled parameter values. Classes use the configured
    search-range maxima because their runtime parameters are not known yet.
    """
    max_period = 0
    for strategy in strategy_classes:
        strategy_class = strategy if inspect.isclass(strategy) else strategy.__class__
        try:
            period_parameters = strategy_parameter_space(strategy_class)
            if inspect.isclass(strategy) or not hasattr(strategy, "params"):
                period_maxima = (
                    maximum
                    for name, _parameter_type, _minimum, maximum in period_parameters
                    if name.endswith("_period")
                )
            else:
                period_maxima = (
                    int(getattr(strategy.params, name))
                    for name, _parameter_type, _minimum, _maximum in period_parameters
                    if name.endswith("_period") and hasattr(strategy.params, name)
                )
            max_period = max(max_period, *period_maxima)
        except ValueError:
            continue
    return max_period


def strategy_parameter_space_by_name(strategy_name: str):
    """Return the active configured search space for a strategy name."""
    if strategy_name in STRATEGY_PARAMETER_NAMES:
        return _parameters(STRATEGY_PARAMETER_NAMES[strategy_name])

    if strategy_name in {"Puffin1", "Puffin2", "Puffin3", "Puffin4"}:
        names = (
            STRATEGY_PARAMETER_NAMES["EmperorPenguin"]
            + ("relative_performance_period", "relative_performance_threshold",
               "rvol_period", "rvol_threshold")
        )
        return _parameters(names)

    if strategy_name == "Adv_SELL_ALL":
        return _parameters(
            _LEGACY_PARAMETER_NAMES["advanced_sell_all"]
        )

    if strategy_name.endswith((
        "Adv_SELL_TP1", "Adv_SELL_TP1_Manual",
        "ManualTuneAdvSELL_TP1", "ManualTuneAdvSELL_TP1_Manual",
    )):
        return _parameters(
            _LEGACY_PARAMETER_NAMES["rsi_kaufman_efficiency_ratio"]
            + ("relative_performance_period", "relative_performance_threshold",
               "rvol_period", "rvol_threshold")
        )

    if strategy_name.endswith((
        "Adv_SELL_TP2", "Adv_SELL_TP2_Manual", "Adv_SELL_TP3", "Adv_SELL_TP3_Manual",
        "ManualTuneAdvSELL_TP2", "ManualTuneAdvSELL_TP2_Manual",
        "ManualTuneAdvSELL_TP3", "ManualTuneAdvSELL_TP3_Manual",
    )):
        return _parameters(
            _LEGACY_PARAMETER_NAMES["bollinger_kaufman_efficiency_ratio"]
            + ("relative_performance_period", "relative_performance_threshold",
               "rvol_period", "rvol_threshold")
        )

    if strategy_name.endswith(("OG_TP4", "OG_TP4_Manual")):
        return _parameters(_LEGACY_PARAMETER_NAMES["rsi_risk"] + ("strength_cap",))

    if strategy_name.endswith((
        "Adv_SELL_TP4", "Adv_SELL_TP4_Manual",
        "ManualTuneAdvSELL_TP4", "ManualTuneAdvSELL_TP4_Manual",
    )):
        return _parameters(
            _LEGACY_PARAMETER_NAMES["rsi_risk"]
            + ("relative_performance_period", "relative_performance_threshold",
               "rvol_period", "rvol_threshold")
        )

    if strategy_name.endswith((
        "OG_TP1", "OG_TP1_Manual", "TrainablePenguin1", "TrainablePenguin1_Manual",
    )):
        return _parameters(_LEGACY_PARAMETER_NAMES["rsi_kaufman_efficiency_ratio"] + ("strength_cap",))

    if strategy_name.endswith((
        "OG_TP2", "OG_TP2_Manual", "TrainablePenguin2", "TrainablePenguin2_Manual",
        "OG_TP3", "OG_TP3_Manual", "TrainablePenguin3", "TrainablePenguin3_Manual",
    )):
        return _parameters(_LEGACY_PARAMETER_NAMES["bollinger_kaufman_efficiency_ratio"] + ("strength_cap",))

    raise ValueError(f"No parameter space is defined for {strategy_name}")


MAX_PERIOD = max(
    maximum
    for name, _parameter_type, _minimum, maximum in _ACTIVE_RANGES.values()
    if name.endswith("_period")
)

PARAMETER_RANGE_OVERVIEW = {
    "narrow": NARROW_PARAMETER_RANGES,
    "broad": BROAD_PARAMETER_RANGES,
}

STRATEGY_PARAMETER_REQUIREMENTS = {
    strategy: parameters
    for strategy, parameters in STRATEGY_PARAMETER_NAMES.items()
}


__all__ = [
    "PARAMETERS_EXECUTED",
    "VALIDATION_CANDIDATES",
    "MAX_PERIOD",
    "max_period_for_strategies",
    "PARAMETER_SEARCH_METHOD",
    "SEARCH_STRATEGIES",
    "PARAMETER_SEARCH_STRATEGY",
    "PARAMETER_SEARCH_BAYESIAN_SAMPLER",
    "PARAMETER_SEARCH_BAYESIAN_ACQUISITION",
    "PARAMETER_SEARCH_BAYESIAN_UCB_KAPPA",
    "PARAMETER_SEARCH_WARMUP_TRIALS",
    "PARAMETER_RANGE_OVERVIEW",
    "STRATEGY_PARAMETER_REQUIREMENTS",
    "strategy_parameter_space",
    "strategy_parameter_space_by_name",
    "has_parameter_search_space",
]
