"""Renewal-equation (EpiEstim / Cori et al.) Rt estimator, own NumPy/SciPy
implementation (FR-3.1, DR-1). No external stats service — see docs.md §2/§6.

Method: discretise the serial-interval distribution from the configured
mean/SD; compute total infectiousness Lambda_t = sum_s I_{t-s} * w(s); with a
Gamma(prior_shape, prior_scale) prior on Rt, the posterior over a sliding
window is Gamma(prior_shape + sum(I), 1 / (1/prior_scale + sum(Lambda))).
Point estimate and credible interval are read off that posterior.

Write the synthetic-recovery test before anything else consumes this module
(IMPLEMENTATION_PLAN.md Step 4.2) — see tests/unit/test_renewal.py.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import gamma as gamma_dist

DEFAULT_PRIOR_SHAPE = 1.0
DEFAULT_PRIOR_SCALE = 5.0  # prior mean Rt = shape * scale = 5, weakly informative


def discretise_serial_interval(mean: float, sd: float, max_days: int) -> np.ndarray:
    """Discretised serial-interval PMF w[0..max_days-1] for s=1..max_days,
    via a Gamma distribution parameterised by (mean, sd), integer-day binned.
    """
    if max_days <= 0:
        return np.array([])
    variance = sd ** 2
    shape = (mean ** 2) / variance
    scale = variance / mean
    days = np.arange(1, max_days + 1)
    cdf_hi = gamma_dist.cdf(days + 0.5, a=shape, scale=scale)
    cdf_lo = gamma_dist.cdf(days - 0.5, a=shape, scale=scale)
    w = cdf_hi - cdf_lo
    total = w.sum()
    if total <= 0:
        # Degenerate fallback: all mass on day 1.
        w = np.zeros(max_days)
        w[0] = 1.0
        return w
    return w / total


def total_infectiousness(incidence: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Lambda_t for t = 1..n-1 (t=0 has no prior days). Returns array of length n-1."""
    n = len(incidence)
    lambdas = np.zeros(max(n - 1, 0))
    for t in range(1, n):
        s_max = min(t, len(w))
        lam = 0.0
        for s in range(1, s_max + 1):
            lam += w[s - 1] * incidence[t - s]
        lambdas[t - 1] = lam
    return lambdas


def estimate_rt(
    incidence: np.ndarray,
    window_days: int,
    serial_interval_mean: float,
    serial_interval_sd: float,
    credible_interval: float = 0.95,
    prior_shape: float = DEFAULT_PRIOR_SHAPE,
    prior_scale: float = DEFAULT_PRIOR_SCALE,
) -> dict | None:
    """`incidence` is a 1D array of daily (weighted) report counts, oldest
    first, ending at the day the estimate is "as of". Returns None if there
    isn't enough history to form a window (need >= 2 days).

    Returns {"rt": float, "rt_lower": float, "rt_upper": float, "n_reports": float}
    where rt_* describe the posterior over the *last* `window_days`.
    """
    n = len(incidence)
    if n < 2:
        return None

    w = discretise_serial_interval(serial_interval_mean, serial_interval_sd, max_days=n - 1)
    lambdas = total_infectiousness(incidence, w)  # length n-1, corresponds to t=1..n-1
    if len(lambdas) == 0:
        return None

    window = min(window_days, len(lambdas))
    lambda_window = lambdas[-window:]
    incidence_window = incidence[n - window:n]  # t values n-window..n-1

    sum_lambda = float(lambda_window.sum())
    sum_incidence = float(incidence_window.sum())

    posterior_shape = prior_shape + sum_incidence
    posterior_rate = (1.0 / prior_scale) + sum_lambda
    if posterior_rate <= 0:
        return None
    posterior_scale = 1.0 / posterior_rate

    mean_rt = posterior_shape * posterior_scale
    alpha = (1.0 - credible_interval) / 2.0
    lower = float(gamma_dist.ppf(alpha, a=posterior_shape, scale=posterior_scale))
    upper = float(gamma_dist.ppf(1.0 - alpha, a=posterior_shape, scale=posterior_scale))

    return {
        "rt": mean_rt,
        "rt_lower": lower,
        "rt_upper": upper,
        "n_reports": sum_incidence,
    }
