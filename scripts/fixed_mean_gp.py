"""Optuna GP sampling with a constant prior mean in original objective units."""

import math
from types import FunctionType

import numpy as np
from optuna._gp import gp
from optuna.samplers import GPSampler
from optuna.samplers._gp import sampler as gp_sampler
from optuna.study import StudyDirection


class FixedMeanGPSampler(GPSampler):
    def __init__(self, *, mean_value: float = 0.0, **kwargs):
        super().__init__(**kwargs)
        self.mean_value = float(mean_value)
        if not math.isfinite(self.mean_value):
            raise ValueError("GP mean_value must be finite.")

    def _sample_relative_impl(self, study, *args, **kwargs):
        def standardize(values):
            values = gp.warn_and_convert_inf(values)
            stds = np.std(values, axis=0)
            # A constant history has no natural scale; avoid dividing residuals by epsilon.
            stds = np.where(stds > gp_sampler.EPS, stds, 1.0)
            signs = np.array([
                -1.0 if direction == StudyDirection.MINIMIZE else 1.0
                for direction in study.directions
            ])
            means = signs * self.mean_value
            return (values - means) / stds, means, stds

        implementation = GPSampler._sample_relative_impl
        if "_standardize_values" not in implementation.__code__.co_names:
            raise RuntimeError("Fixed GP means require Optuna's _standardize_values hook.")
        # Reuse Optuna's sampling code with a private globals copy. Only objective
        # centering changes; other samplers and constraint centering stay untouched.
        # GP and EI both use (y - mean_value) / std, so no offset is needed in UCB.
        sample = FunctionType(
            implementation.__code__,
            dict(implementation.__globals__, _standardize_values=standardize),
            implementation.__name__,
            implementation.__defaults__,
            implementation.__closure__,
        )
        return sample(self, study, *args, **kwargs)
