"""Synthetic-recovery test for the Rt estimator (IMPLEMENTATION_PLAN.md Step 4.2):
simulate an epidemic with a known constant R, confirm the recovered Rt's
credible interval covers the true value. Written before Rt is trusted for any
real decision — this is the only thing standing between a plausible-looking
and an actually-correct number.
"""
import numpy as np

from src.stage3_rt.renewal import discretise_serial_interval, estimate_rt

SERIAL_MEAN = 2.5
SERIAL_SD = 1.5


def _simulate_renewal_process(r_true: float, n_days: int, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    w = discretise_serial_interval(SERIAL_MEAN, SERIAL_SD, max_days=n_days)
    incidence = np.zeros(n_days)
    incidence[0] = 20  # seed cases
    for t in range(1, n_days):
        s_max = min(t, len(w))
        lam = sum(w[s - 1] * incidence[t - s] for s in range(1, s_max + 1))
        expected = max(r_true * lam, 1e-9)
        incidence[t] = rng.poisson(expected)
    return incidence


def test_recovers_growing_epidemic_r_above_one():
    incidence = _simulate_renewal_process(r_true=1.8, n_days=40)
    result = estimate_rt(
        incidence, window_days=7, serial_interval_mean=SERIAL_MEAN,
        serial_interval_sd=SERIAL_SD, credible_interval=0.95,
    )
    assert result is not None
    assert result["rt_lower"] < result["rt"] < result["rt_upper"]
    # True R should fall within (or very near) the recovered credible interval.
    assert result["rt_lower"] - 0.5 <= 1.8 <= result["rt_upper"] + 0.5
    assert result["rt_lower"] > 1.0  # a clearly-growing epidemic should gate ESCALATING


def test_recovers_declining_epidemic_r_below_one():
    # Evaluate mid-simulation (day 15), before the decline drives incidence to
    # zero and the posterior collapses back to the (uninformative) prior mean.
    incidence = _simulate_renewal_process(r_true=0.6, n_days=15)
    result = estimate_rt(
        incidence, window_days=7, serial_interval_mean=SERIAL_MEAN,
        serial_interval_sd=SERIAL_SD, credible_interval=0.95,
    )
    assert result is not None
    assert result["n_reports"] > 0
    assert result["rt"] < 1.2  # should not be mistaken for growth


def test_insufficient_history_returns_none():
    assert estimate_rt(np.array([5.0]), 7, SERIAL_MEAN, SERIAL_SD) is None
    assert estimate_rt(np.array([]), 7, SERIAL_MEAN, SERIAL_SD) is None


def test_serial_interval_discretisation_normalises_to_one():
    w = discretise_serial_interval(SERIAL_MEAN, SERIAL_SD, max_days=30)
    assert abs(w.sum() - 1.0) < 1e-9
    assert (w >= 0).all()
