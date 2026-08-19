"""Unit tests for the experiments stats engine (`services/experiments.py`).

This module had zero test coverage before this file: the two-proportion
z-test, Welch's t-test, power analysis, and the mSPRT sequential test are all
hand-implemented (no scipy dependency), which is exactly the kind of code
where a sign flip or an off-by-one in a formula produces a number that looks
plausible and is wrong. Wrong statistics here do not crash anything -- they
silently tell an operator a losing variant is a winner. The tests below check
against known reference values and structural properties (symmetry,
monotonicity) rather than only smoke-testing that the functions run.
"""

from __future__ import annotations

import math
from itertools import pairwise

from truegrit_api.services.experiments import (
    _achieved_power_binary,
    _norm_cdf,
    _norm_ppf,
    assign_variant,
    msprt_z,
    power_analysis_binary,
    power_analysis_continuous,
    two_proportion_z_test,
    welch_t_test,
)

VARIANTS = [{"key": "control", "name": "Control"}, {"key": "treatment", "name": "Treatment"}]


# --- Normal distribution helpers --------------------------------------------


def test_norm_cdf_matches_known_values():
    assert math.isclose(_norm_cdf(0.0), 0.5, abs_tol=1e-9)
    # 1.96 is the standard "two-sided 5%" landmark.
    assert math.isclose(_norm_cdf(1.959964), 0.975, abs_tol=1e-4)
    assert math.isclose(_norm_cdf(-1.959964), 0.025, abs_tol=1e-4)


def test_norm_ppf_is_the_inverse_of_norm_cdf():
    for p in (0.01, 0.1, 0.5, 0.9, 0.99):
        assert math.isclose(_norm_cdf(_norm_ppf(p)), p, abs_tol=1e-3)


def test_norm_ppf_of_975_is_the_z_1_96_landmark():
    # The single most load-bearing constant in frequentist A/B testing.
    assert math.isclose(_norm_ppf(0.975), 1.959964, abs_tol=5e-4)


# --- Two-proportion z-test ---------------------------------------------------


def test_z_test_finds_no_effect_when_rates_are_identical():
    z, p, ci_lo, ci_hi = two_proportion_z_test(100, 1000, 100, 1000)
    assert z == 0.0
    assert p == 1.0
    assert ci_lo < 0 < ci_hi


def test_z_test_is_antisymmetric_under_swapping_control_and_treatment():
    """Swapping which group is "control" must flip the sign of the effect
    and leave the p-value and |z| unchanged -- the test must not have a
    hidden directional assumption baked in."""
    z_ct, p_ct, _, _ = two_proportion_z_test(80, 1000, 120, 1000)
    z_tc, p_tc, _, _ = two_proportion_z_test(120, 1000, 80, 1000)
    assert math.isclose(z_ct, -z_tc, rel_tol=1e-9)
    assert math.isclose(p_ct, p_tc, rel_tol=1e-9)


def test_z_test_detects_a_large_obvious_lift_as_significant():
    # 5% -> 10% conversion at n=2000/arm is an unmissable effect. diff =
    # p_treatment - p_control, so a treatment that outperforms control is
    # positive under this function's sign convention.
    z, p, ci_lo, ci_hi = two_proportion_z_test(100, 2000, 200, 2000)
    assert z > 3
    assert p < 0.01
    assert ci_lo < ci_hi


def test_z_test_finds_no_significance_in_pure_noise_at_a_tiny_sample():
    _, p, _, _ = two_proportion_z_test(1, 10, 2, 10)
    assert p > 0.05


def test_z_test_handles_zero_totals_without_dividing_by_zero():
    assert two_proportion_z_test(0, 0, 5, 10) == (0.0, 1.0, 0.0, 0.0)
    assert two_proportion_z_test(5, 10, 0, 0) == (0.0, 1.0, 0.0, 0.0)


def test_z_test_confidence_interval_brackets_the_point_estimate():
    _, _, ci_lo, ci_hi = two_proportion_z_test(100, 1000, 130, 1000)
    point_estimate = 130 / 1000 - 100 / 1000
    assert ci_lo <= point_estimate <= ci_hi


# --- Welch's t-test -----------------------------------------------------------


def test_welch_t_test_finds_no_effect_for_identical_distributions():
    values = [10.0, 12.0, 11.0, 9.0, 13.0, 10.5, 11.5]
    t, p, _, _ = welch_t_test(values, list(values))
    assert t == 0.0
    assert p == 1.0


def test_welch_t_test_is_antisymmetric():
    control = [10.0, 12.0, 11.0, 9.0, 13.0, 10.0, 11.0, 12.0]
    treatment = [15.0, 17.0, 16.0, 14.0, 18.0, 15.5, 16.5, 17.5]
    t_ct, p_ct, _, _ = welch_t_test(control, treatment)
    t_tc, p_tc, _, _ = welch_t_test(treatment, control)
    assert math.isclose(t_ct, -t_tc, rel_tol=1e-9)
    assert math.isclose(p_ct, p_tc, rel_tol=1e-9)


def test_welch_t_test_detects_a_large_obvious_difference():
    control = [10.0] * 40
    treatment = [20.0] * 40
    # Zero variance inside each arm is the degenerate case the SE-guard
    # exists for; add a whisker of noise so the test exercises the real path.
    control = [x + (i % 3) * 0.01 for i, x in enumerate(control)]
    treatment = [x + (i % 3) * 0.01 for i, x in enumerate(treatment)]
    # t = (mean_treatment - mean_control) / se, so treatment scoring higher
    # than control is positive under this function's sign convention.
    t, p, _, _ = welch_t_test(control, treatment)
    assert t > 10
    assert p < 0.001


def test_welch_t_test_requires_at_least_two_points_per_arm():
    assert welch_t_test([1.0], [1.0, 2.0]) == (0.0, 1.0, 0.0, 0.0)
    assert welch_t_test([], []) == (0.0, 1.0, 0.0, 0.0)


def test_welch_t_test_handles_zero_variance_without_dividing_by_zero():
    t, p, ci_lo, ci_hi = welch_t_test([5.0, 5.0, 5.0], [5.0, 5.0, 5.0])
    assert t == 0.0
    assert p == 1.0
    assert ci_lo == ci_hi == 0.0


# --- Power analysis ------------------------------------------------------------


def test_power_analysis_binary_matches_the_textbook_formula_by_hand():
    # 5% baseline, detect a 2-point absolute lift to 7%, alpha=0.05, power=0.8.
    # Worked by hand from the standard two-proportion sample-size formula
    # (Fleiss): p_bar=0.06, z_alpha/2=1.9600, z_beta=0.8416 ->
    #   n = (1.96*sqrt(2*0.06*0.94) + 0.8416*sqrt(0.05*0.95+0.07*0.93))^2 / 0.02^2
    #     = (0.6584 + 0.2824)^2 / 0.0004 ~= 2212.7 -> ceil 2213.
    # This also matches the common rule-of-thumb approximation
    # n ~= 16*p_bar*(1-p_bar)/mde^2 ~= 2256, in the same neighbourhood.
    n = power_analysis_binary(baseline_rate=0.05, mde=0.02)
    assert n == 2213


def test_power_analysis_binary_needs_fewer_samples_for_a_bigger_effect():
    small_effect = power_analysis_binary(baseline_rate=0.05, mde=0.01)
    large_effect = power_analysis_binary(baseline_rate=0.05, mde=0.05)
    assert large_effect < small_effect


def test_power_analysis_binary_needs_more_samples_for_higher_power():
    standard = power_analysis_binary(baseline_rate=0.05, mde=0.02, power=0.80)
    higher = power_analysis_binary(baseline_rate=0.05, mde=0.02, power=0.95)
    assert higher > standard


def test_power_analysis_binary_rejects_degenerate_inputs():
    assert power_analysis_binary(baseline_rate=0.0, mde=0.02) == 0
    assert power_analysis_binary(baseline_rate=0.05, mde=0.0) == 0
    assert power_analysis_binary(baseline_rate=1.0, mde=0.02) == 0


def test_power_analysis_continuous_needs_fewer_samples_for_a_bigger_effect():
    small = power_analysis_continuous(baseline_std=10.0, mde=1.0)
    large = power_analysis_continuous(baseline_std=10.0, mde=5.0)
    assert large < small


def test_achieved_power_is_low_for_a_tiny_sample_and_high_for_a_huge_one():
    tiny = _achieved_power_binary(0.05, 0.07, n=20)
    huge = _achieved_power_binary(0.05, 0.07, n=50_000)
    assert tiny < 0.5
    assert huge > 0.99


def test_achieved_power_with_no_effect_equals_alpha():
    # No true difference: the "power" to detect nothing is exactly the false
    # positive rate, by definition.
    assert _achieved_power_binary(0.05, 0.05, n=1000) == 0.05


# --- mSPRT sequential test ---------------------------------------------------


def test_msprt_p_value_is_never_more_extreme_than_it_should_be():
    """The always-valid p-value must stay in [0, 1] across a wide range of
    inputs -- a value escaping that range would silently corrupt the
    "statistically significant" flag the dashboard reads."""
    for z in (-5.0, -1.0, 0.0, 1.0, 3.0, 8.0):
        for n in (1, 50, 5000):
            _, p = msprt_z(z, n)
            assert 0.0 <= p <= 1.0


def test_msprt_p_value_shrinks_along_a_realistic_accumulation_of_evidence():
    """A *fixed* z-statistic at a larger n is not "more evidence" -- for a
    z-statistic that scales like sqrt(n), a constant z at larger n implies a
    *smaller* true effect (z = effect * sqrt(n) / sigma), so the mixture test
    is correctly more skeptical of it (verified by hand: with the default
    theta=0.1, d(log Lambda)/dV changes sign at V = z^2 - 1, so a held-fixed
    z=3 is already past its own peak significance by n=100). What mSPRT is
    actually meant to guarantee is monotone significance along a genuine
    accumulation of data under a persistent true effect, where z grows with
    sqrt(n) -- that is what this test drives instead.
    """
    true_effect_z_per_sqrt_n = 0.3  # a small, persistent per-observation signal
    p_values = [
        msprt_z(z_stat=true_effect_z_per_sqrt_n * math.sqrt(n), n_total=n)[1]
        for n in (50, 500, 5000, 50_000)
    ]
    assert all(later <= earlier for earlier, later in pairwise(p_values))
    assert p_values[-1] < 0.01


def test_msprt_at_zero_evidence_is_not_significant():
    _, p = msprt_z(z_stat=0.0, n_total=1000)
    assert p == 1.0


def test_msprt_handles_zero_sample_size():
    assert msprt_z(z_stat=2.0, n_total=0) == (0.0, 1.0)


def test_msprt_extreme_z_does_not_overflow():
    """The log-likelihood ratio is exponentiated; an extreme early z-stat
    (a fluke on the first handful of users) must not raise OverflowError."""
    lambda_stat, p = msprt_z(z_stat=50.0, n_total=10)
    assert math.isfinite(lambda_stat)
    assert 0.0 <= p <= 1.0


# --- Variant assignment -------------------------------------------------------


def test_assignment_is_deterministic_for_the_same_user_and_experiment():
    first = assign_variant("usr_riya", "checkout_free_ship_msg", VARIANTS, 100)
    second = assign_variant("usr_riya", "checkout_free_ship_msg", VARIANTS, 100)
    assert first == second
    assert first in {"control", "treatment"}


def test_assignment_differs_across_experiments_for_the_same_user():
    """A hash collision here would mean every experiment a user is in shows
    them the same variant letter, which defeats independent randomisation."""
    assignments = {assign_variant("usr_riya", f"experiment_{i}", VARIANTS, 100) for i in range(20)}
    assert len(assignments) > 1


def test_zero_allocation_excludes_everyone():
    for user_id in ("usr_a", "usr_b", "usr_c", "usr_d", "usr_e"):
        assert assign_variant(user_id, "some_experiment", VARIANTS, 0) is None


def test_full_allocation_excludes_no_one():
    for user_id in ("usr_a", "usr_b", "usr_c", "usr_d", "usr_e"):
        assert assign_variant(user_id, "some_experiment", VARIANTS, 100) is not None


def test_allocation_roughly_splits_users_at_the_configured_percentage():
    """Not a statistical proof, just a sanity band: 50% allocation over a
    few hundred synthetic users should land nowhere near 10% or 90%."""
    included = sum(
        1
        for i in range(500)
        if assign_variant(f"usr_synthetic_{i}", "half_alloc_experiment", VARIANTS, 50) is not None
    )
    assert 150 < included < 350


def test_variants_split_roughly_evenly_among_included_users():
    counts = {"control": 0, "treatment": 0}
    for i in range(500):
        variant = assign_variant(f"usr_synthetic_{i}", "even_split_experiment", VARIANTS, 100)
        assert variant is not None
        counts[variant] += 1
    # Loose band -- this is a hash function, not a coin flip generator, and
    # the test only needs to catch a badly broken split (e.g. always control).
    assert 150 < counts["control"] < 350
    assert 150 < counts["treatment"] < 350
