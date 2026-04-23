"""Property + sanity tests for bayesian_calibration.py."""

from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bayesian_calibration import (  # noqa: E402
    BetaPrior,
    DEFAULT_PRIOR_ALPHA,
    DEFAULT_PRIOR_BETA,
    beta_cdf,
    beta_credible_interval,
    beta_mean,
    beta_mode,
    beta_ppf,
    beta_variance,
    build_good_rating_pairs,
    build_take_again_pairs,
    decision_summary,
    fit_empirical_bayes_beta,
    group_by_department,
    posterior_from_counts,
    posterior_predictive_match,
    prob_a_gt_b_closed,
    prob_a_gt_b_mc,
)


# ─────────────────────────── Beta CDF / PPF ───────────────────────────

def test_cdf_boundaries():
    assert beta_cdf(0.0, 3, 4) == 0.0
    assert beta_cdf(1.0, 3, 4) == 1.0


def test_cdf_uniform_is_identity():
    # Beta(1,1) is Uniform(0,1); CDF(x) == x
    for x in [0.1, 0.3, 0.7, 0.9]:
        assert abs(beta_cdf(x, 1, 1) - x) < 1e-6


def test_cdf_symmetric_beta_half_is_half():
    # CDF(0.5) = 0.5 for any Beta(a, a)
    for a in [1, 2, 5, 20, 100]:
        assert abs(beta_cdf(0.5, a, a) - 0.5) < 1e-4


def test_ppf_roundtrip():
    for a, b in [(2, 2), (10, 3), (1, 99), (50, 50), (0.5, 0.5)]:
        for q in [0.025, 0.1, 0.5, 0.9, 0.975]:
            x = beta_ppf(q, a, b)
            cdf = beta_cdf(x, a, b)
            assert abs(cdf - q) < 1e-5, (a, b, q, x, cdf)


def test_credible_interval_contains_mean():
    for a, b in [(2, 2), (20, 80), (1, 9), (500, 500)]:
        lo, hi = beta_credible_interval(a, b, 0.95)
        assert lo < beta_mean(a, b) < hi
        # 95% CI has to be narrower for big samples
    lo_small, hi_small = beta_credible_interval(2, 2, 0.95)
    lo_big, hi_big = beta_credible_interval(200, 200, 0.95)
    assert (hi_big - lo_big) < (hi_small - lo_small)


# ──────────────────── moments ────────────────────

def test_mean_mode_variance():
    assert beta_mean(2, 2) == 0.5
    assert beta_mode(5, 3) == (4 / 6)
    assert beta_mode(0.5, 0.5) is None
    # Known closed-form
    assert abs(beta_variance(2, 2) - (1 / 20.0)) < 1e-9


# ──────────────── Empirical Bayes ────────────────

def test_eb_recovers_known_beta():
    """Generate (x, n) from a Beta(8, 32) population and check moments recovered."""
    import random

    rng = random.Random(0)
    true_alpha, true_beta = 8.0, 32.0
    pairs = []
    for _ in range(300):
        p = rng.betavariate(true_alpha, true_beta)
        n = rng.randint(20, 200)
        x = sum(1 for _ in range(n) if rng.random() < p)
        pairs.append((x, n))
    prior = fit_empirical_bayes_beta(pairs)
    assert prior.source == "empirical_bayes_mom"
    # Method of moments gets the mean nearly exactly...
    assert abs(prior.mean - 0.2) < 0.03
    # ...and the concentration within ~40% of the true 40.
    assert 24 < prior.concentration < 60


def test_eb_fallback_on_degenerate_input():
    p = fit_empirical_bayes_beta([(5, 10), (50, 100), (500, 1000)])  # zero variance
    assert p.source == "fallback_weak"
    assert p.alpha == DEFAULT_PRIOR_ALPHA
    assert p.beta == DEFAULT_PRIOR_BETA


def test_eb_fallback_on_too_few_groups():
    p = fit_empirical_bayes_beta([(1, 2), (3, 4)])
    assert p.source == "fallback_weak"


# ────────────────── Posterior / Shrinkage ──────────────────

def test_posterior_math():
    pr = BetaPrior(2, 2, "fixed")
    post = posterior_from_counts(successes=8, n=10, prior=pr)
    assert post.alpha == 10 and post.beta == 4
    assert abs(post.mean - (10 / 14)) < 1e-9


def test_shrinkage_interpolates_between_prior_and_mle():
    pr = BetaPrior(10, 10, "fixed")  # prior mean 0.5, concentration 20
    # Lots of data -> posterior close to MLE, little shrinkage
    high_n = posterior_from_counts(900, 1000, pr)
    low_n = posterior_from_counts(9, 10, pr)
    assert high_n.shrinkage_toward_prior() < low_n.shrinkage_toward_prior()

    # No data -> full shrinkage
    zero = posterior_from_counts(0, 0, pr)
    assert zero.shrinkage_toward_prior() == 1.0


# ─────────────────── P(A > B) ───────────────────

def test_closed_form_symmetric_half():
    assert abs(prob_a_gt_b_closed(5, 5, 5, 5) - 0.5) < 1e-9
    assert abs(prob_a_gt_b_closed(3, 3, 3, 3) - 0.5) < 1e-9


def test_closed_form_matches_mc():
    """Closed-form exact check should match MC within MC tolerance."""
    exact = prob_a_gt_b_closed(8, 2, 3, 7)
    mc = prob_a_gt_b_mc(8.0, 2.0, 3.0, 7.0, n_samples=20000, seed=7)
    assert abs(exact - mc) < 0.02


def test_mc_extremes():
    # A clearly better than B
    assert prob_a_gt_b_mc(200, 10, 10, 200, n_samples=4000) > 0.99
    # A clearly worse
    assert prob_a_gt_b_mc(10, 200, 200, 10, n_samples=4000) < 0.01
    # Tie
    p = prob_a_gt_b_mc(50, 50, 50, 50, n_samples=10000, seed=1)
    assert 0.45 < p < 0.55


# ─────────────────── Decision summary ───────────────────

def test_decision_summary_ordered():
    pr = BetaPrior(2, 2, "fixed")
    for (x, n) in [(5, 10), (80, 100), (3, 50), (1, 2)]:
        ds = decision_summary(posterior_from_counts(x, n, pr))
        assert ds.conservative <= ds.typical <= ds.optimistic
        assert ds.conservative <= ds.expected <= ds.optimistic


# ─────────── Posterior predictive match (moderation effect) ───────────

def test_moderation_tiny_n_pulls_score_toward_prior_mean():
    """With almost no data a dimension should contribute close to its prior mean, not an extreme."""
    pr_weak = BetaPrior(2, 2, "fixed")
    pr_strong = BetaPrior(2, 2, "fixed")
    tiny_all_yes = posterior_from_counts(2, 2, pr_weak)   # MLE 1.0, but only 2 data points
    many_all_yes = posterior_from_counts(100, 100, pr_strong)  # MLE 1.0, abundant
    ms_tiny = posterior_predictive_match([("x", 1.0, tiny_all_yes)])
    ms_big = posterior_predictive_match([("x", 1.0, many_all_yes)])
    # Big sample stays close to 1; tiny one shrinks noticeably
    assert ms_big.expected > 0.98
    assert ms_tiny.expected < ms_big.expected


def test_match_ci_widens_with_posterior_variance():
    pr = BetaPrior(2, 2, "fixed")
    sparse = posterior_from_counts(3, 4, pr)
    dense = posterior_from_counts(750, 1000, pr)
    ms_sparse = posterior_predictive_match([("x", 1.0, sparse)])
    ms_dense = posterior_predictive_match([("x", 1.0, dense)])
    w_sparse = ms_sparse.ci_upper - ms_sparse.ci_lower
    w_dense = ms_dense.ci_upper - ms_dense.ci_lower
    assert w_sparse > w_dense


# ─────────── Convenience builders against stub data ───────────

def test_build_take_again_pairs():
    profs = [{
        "reviews": [
            {"would_take_again": 1},
            {"would_take_again": 0},
            {"would_take_again": -1},
            {"would_take_again": 1},
        ],
    }, {
        "reviews": [{"would_take_again": -1}],  # no usable answers
    }]
    assert build_take_again_pairs(profs) == [(2, 3)]


def test_build_good_rating_pairs():
    profs = [{
        "reviews": [
            {"clarity_rating": 4, "helpful_rating": 5},  # avg 4.5 ≥ 3.5 -> good
            {"clarity_rating": 2, "helpful_rating": 3},  # avg 2.5 < 3.5 -> not good
            {"clarity_rating": None, "helpful_rating": 5},  # skipped
        ],
    }]
    assert build_good_rating_pairs(profs, threshold=3.5) == [(1, 2)]


def test_group_by_department_normalizes_missing():
    profs = [{"department": "Math"}, {"department": " math "}, {"department": None}, {}]
    g = group_by_department(profs)
    assert "Math" in g and "math" in g  # case-sensitive; test documents that
    assert "Unknown" in g
    assert len(g["Unknown"]) == 2  # None + missing
