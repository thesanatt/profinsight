"""
ProfInsight — Bayesian Calibration Primitives
==============================================

Pure-Python Bayesian utilities used to lift the existing Beta-Binomial pipeline
from "fixed Beta(2,2) prior everywhere" to a calibrated, decision-theoretic,
hypothesis-testing layer.

Nothing here depends on numpy/scipy. That is intentional: the existing pipeline
ships on Render's free tier without heavy deps, and we want to stay there.

Concept → citation map (paths in class_content/):
  * Beta-Binomial conjugate model, credible intervals ...... Lecture 2 pp. 2–4;
                                                             Lecture 3 pp. 1–5
  * Empirical-Bayes "pseudocounts" framing ................. Lecture 2 p. 3
  * Posterior hypothesis probability P(theta_A > theta_B) .. Lecture 3 pp. 1–2;
                                                             Lecture 4 p. 5
  * Bayesian decision theory (choice of point estimate) .... Lecture 4 pp. 1–4
  * Posterior predictive / moderation ...................... Lecture 7 p. 2;
                                                             Lecture 8 pp. 3–4

Every public function has doctests. Run `python -m doctest bayesian_calibration.py -v`
to check.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Iterable, Sequence


# ═════════════════════════════════════════════════════════════════════════════
# Regularized incomplete Beta function  (CDF of Beta distribution)
# ═════════════════════════════════════════════════════════════════════════════
#
# The Beta(a, b) CDF at x is I_x(a, b) = B(x; a, b) / B(a, b), the regularized
# incomplete Beta function. We implement it via the continued-fraction
# expansion from Numerical Recipes §6.4 (identical to scipy.special.betainc).
# This gives us exact-enough credible intervals without pulling in scipy.

def _log_beta(a: float, b: float) -> float:
    return math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)


def _betacf(a: float, b: float, x: float, max_iter: int = 200, eps: float = 3e-12) -> float:
    """Continued-fraction evaluation of the incomplete Beta; NR §6.4."""
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < 1e-30:
        d = 1e-30
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            return h
    return h  # degraded but usable


def beta_cdf(x: float, a: float, b: float) -> float:
    """
    CDF of Beta(a, b) at x.

    >>> round(beta_cdf(0.5, 1.0, 1.0), 6)
    0.5
    >>> round(beta_cdf(0.25, 2.0, 2.0), 6)
    0.15625
    >>> beta_cdf(0.0, 3.0, 5.0)
    0.0
    >>> beta_cdf(1.0, 3.0, 5.0)
    1.0
    """
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbt = (
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
        + a * math.log(x) + b * math.log1p(-x)
    )
    bt = math.exp(lbt)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def beta_ppf(p: float, a: float, b: float, tol: float = 1e-8) -> float:
    """
    Inverse CDF (quantile) of Beta(a, b). Bisection; robust but not the fastest.

    >>> round(beta_ppf(0.5, 1.0, 1.0), 6)
    0.5
    >>> q = beta_ppf(0.975, 2.0, 2.0)
    >>> 0.85 < q < 0.95
    True
    """
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if beta_cdf(mid, a, b) < p:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return 0.5 * (lo + hi)


# ═════════════════════════════════════════════════════════════════════════════
# Beta summaries (mean, mode, variance, equal-tailed credible interval)
# ═════════════════════════════════════════════════════════════════════════════

def beta_mean(a: float, b: float) -> float:
    """
    >>> beta_mean(2, 2)
    0.5
    >>> round(beta_mean(10, 90), 4)
    0.1
    """
    return a / (a + b)


def beta_variance(a: float, b: float) -> float:
    return (a * b) / ((a + b) ** 2 * (a + b + 1.0))


def beta_mode(a: float, b: float) -> float | None:
    """
    Mode of Beta(a, b) if it exists, else None (when both shape params <= 1).

    >>> beta_mode(5, 3)
    0.6666666666666666
    >>> beta_mode(0.5, 0.5) is None
    True
    """
    if a > 1.0 and b > 1.0:
        return (a - 1.0) / (a + b - 2.0)
    return None


def beta_credible_interval(a: float, b: float, level: float = 0.95) -> tuple[float, float]:
    """
    Equal-tailed credible interval for Beta(a, b). Exact via numerical CDF
    inversion — no normal approximation.

    >>> lo, hi = beta_credible_interval(2, 2, 0.95)
    >>> 0.09 < lo < 0.10 and 0.90 < hi < 0.91
    True
    """
    assert 0.0 < level < 1.0
    tail = (1.0 - level) / 2.0
    return beta_ppf(tail, a, b), beta_ppf(1.0 - tail, a, b)


# ═════════════════════════════════════════════════════════════════════════════
# Empirical-Bayes prior fitting (method of moments)
# ═════════════════════════════════════════════════════════════════════════════
#
# Given a set of (x_i, n_i) pairs — e.g. for each professor in a department,
# (successes, reviews) — we fit a common Beta(alpha, beta) such that the
# resulting Beta-Binomial mixture matches the observed mean and variance.
#
# This is the operationalization of the Lecture 2 p.3 "pseudocounts"
# framing: the fitted (alpha, beta) are exactly the strength of prior
# information we pool across professors.
#
# We also guard against degenerate inputs (all x/n equal, or near-zero variance)
# by falling back to a weakly-informative Beta(1, 1) in those cases.

DEFAULT_PRIOR_ALPHA = 2.0
DEFAULT_PRIOR_BETA = 2.0
MIN_CONCENTRATION = 2.0  # keep α+β ≥ 2 so the prior doesn't dominate big-n data


@dataclass
class BetaPrior:
    alpha: float
    beta: float
    source: str  # "empirical_bayes_mom" | "fallback_weak" | "fixed"

    @property
    def mean(self) -> float:
        return beta_mean(self.alpha, self.beta)

    @property
    def concentration(self) -> float:
        return self.alpha + self.beta

    def as_dict(self) -> dict:
        return {
            "alpha": round(self.alpha, 4),
            "beta": round(self.beta, 4),
            "mean": round(self.mean, 4),
            "concentration": round(self.concentration, 3),
            "source": self.source,
        }


def fit_empirical_bayes_beta(pairs: Iterable[tuple[int, int]]) -> BetaPrior:
    """
    Fit Beta(alpha, beta) by method of moments from (successes, total) pairs.

    The observed p_hat_i = x_i / n_i has mean mu and weighted variance v.
    For a Beta(alpha, beta) population, mu = alpha / (alpha + beta)
    and var = mu*(1-mu) / (alpha + beta + 1). Solve for (alpha, beta).

    Only groups with n_i >= 1 contribute. Groups with n_i = 0 are skipped.

    >>> p = fit_empirical_bayes_beta([(8, 10), (90, 100), (450, 500)])
    >>> p.source
    'empirical_bayes_mom'
    >>> 0.8 < p.mean < 0.95
    True

    >>> # Degenerate: all identical proportions -> fallback
    >>> p = fit_empirical_bayes_beta([(5, 10), (50, 100), (500, 1000)])
    >>> p.source
    'fallback_weak'
    """
    filtered = [(x, n) for (x, n) in pairs if n and n > 0 and 0 <= x <= n]
    if len(filtered) < 3:
        return BetaPrior(DEFAULT_PRIOR_ALPHA, DEFAULT_PRIOR_BETA, source="fallback_weak")

    phats = [x / n for (x, n) in filtered]
    mu = sum(phats) / len(phats)
    if mu <= 0.0 or mu >= 1.0:
        return BetaPrior(DEFAULT_PRIOR_ALPHA, DEFAULT_PRIOR_BETA, source="fallback_weak")

    var = sum((p - mu) ** 2 for p in phats) / len(phats)
    denom_term = mu * (1.0 - mu)
    if var <= 0.0 or var >= denom_term:
        # var too small (no spread) or too large (over-dispersed beyond Beta)
        return BetaPrior(DEFAULT_PRIOR_ALPHA, DEFAULT_PRIOR_BETA, source="fallback_weak")

    concentration = denom_term / var - 1.0  # alpha + beta
    if concentration < MIN_CONCENTRATION:
        concentration = MIN_CONCENTRATION
    alpha = concentration * mu
    beta = concentration * (1.0 - mu)
    return BetaPrior(alpha=alpha, beta=beta, source="empirical_bayes_mom")


# ═════════════════════════════════════════════════════════════════════════════
# Posterior for Beta-Binomial data given an arbitrary prior
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class BetaPosterior:
    alpha: float
    beta: float
    n: int
    successes: int
    prior: BetaPrior

    @property
    def mean(self) -> float:
        return beta_mean(self.alpha, self.beta)

    @property
    def variance(self) -> float:
        return beta_variance(self.alpha, self.beta)

    def credible_interval(self, level: float = 0.95) -> tuple[float, float]:
        return beta_credible_interval(self.alpha, self.beta, level)

    def shrinkage_toward_prior(self) -> float:
        """How far the posterior mean was pulled from the MLE toward the prior mean.
        0 = no shrinkage (posterior == MLE), 1 = full shrinkage (ignoring data).

        >>> pr = BetaPrior(10, 10, 'fixed')
        >>> # No data -> full shrinkage
        >>> post = posterior_from_counts(0, 0, pr)
        >>> post.shrinkage_toward_prior()
        1.0
        >>> # Lots of data -> shrinkage -> 0
        >>> post = posterior_from_counts(9000, 10000, pr)
        >>> post.shrinkage_toward_prior() < 0.01
        True
        """
        if self.n == 0:
            return 1.0
        mle = self.successes / self.n
        post_mean = self.mean
        prior_mean = self.prior.mean
        if mle == prior_mean:
            return 0.0
        return max(0.0, min(1.0, abs(post_mean - mle) / abs(prior_mean - mle)))

    def as_dict(self, level: float = 0.95) -> dict:
        lo, hi = self.credible_interval(level)
        return {
            "alpha": round(self.alpha, 4),
            "beta": round(self.beta, 4),
            "n": self.n,
            "successes": self.successes,
            "mean": round(self.mean, 4),
            "variance": round(self.variance, 6),
            "ci_lower": round(lo, 4),
            "ci_upper": round(hi, 4),
            "ci_level": level,
            "shrinkage": round(self.shrinkage_toward_prior(), 4),
            "prior": self.prior.as_dict(),
        }


def posterior_from_counts(successes: int, n: int, prior: BetaPrior) -> BetaPosterior:
    """
    >>> pr = BetaPrior(2, 2, 'fixed')
    >>> post = posterior_from_counts(8, 10, pr)
    >>> round(post.mean, 4)
    0.7143
    """
    successes = max(0, int(successes))
    n = max(0, int(n))
    failures = max(0, n - successes)
    return BetaPosterior(
        alpha=prior.alpha + successes,
        beta=prior.beta + failures,
        n=n,
        successes=successes,
        prior=prior,
    )


# ═════════════════════════════════════════════════════════════════════════════
# Posterior hypothesis test: P(theta_A > theta_B)
# ═════════════════════════════════════════════════════════════════════════════
#
# For two independent Beta posteriors, P(theta_A > theta_B) has a closed-form
# expression (Cook 2005, "Exact calculation of Beta inequalities") — but it
# requires a sum of log-Beta-function ratios that is only stable for small
# shape parameters. For professor reviews we routinely see alpha+beta in the
# hundreds, so we use a seeded Monte Carlo estimator. For small counts we
# also expose the closed-form version so tests can check consistency.

def prob_a_gt_b_mc(
    a1: float, b1: float,
    a2: float, b2: float,
    n_samples: int = 4000,
    seed: int = 42,
) -> float:
    """
    Monte Carlo estimate of P(X > Y), X ~ Beta(a1, b1), Y ~ Beta(a2, b2).

    >>> p = prob_a_gt_b_mc(100, 10, 10, 100, n_samples=4000)
    >>> p > 0.99
    True
    >>> p = prob_a_gt_b_mc(5, 5, 5, 5, n_samples=4000)
    >>> 0.45 < p < 0.55
    True
    """
    rng = random.Random(seed)
    wins = 0
    for _ in range(n_samples):
        x = rng.betavariate(a1, b1)
        y = rng.betavariate(a2, b2)
        if x > y:
            wins += 1
    return wins / n_samples


def prob_a_gt_b_closed(a1: int, b1: int, a2: int, b2: int) -> float:
    """
    Closed-form P(X > Y) for small *integer* Beta shape params.

    Evan Miller / Cook formulation: sum over the shape count of the *left*
    variable, with the *other* variable's parameters appearing in the B(·,·)
    ratio. Numerically stable for small shapes (say ≤ 200); for larger shapes
    prefer prob_a_gt_b_mc.

    >>> # Symmetry check
    >>> abs(prob_a_gt_b_closed(3, 3, 3, 3) - 0.5) < 1e-9
    True
    >>> # Known asymmetry
    >>> prob_a_gt_b_closed(8, 2, 3, 7) > 0.98
    True
    """
    a1, b1, a2, b2 = int(a1), int(b1), int(a2), int(b2)
    total = 0.0
    for i in range(a1):
        lnum = _log_beta(a2 + i, b2 + b1)
        ldenom = math.log(b1 + i) + _log_beta(1 + i, b1) + _log_beta(a2, b2)
        total += math.exp(lnum - ldenom)
    return total


# ═════════════════════════════════════════════════════════════════════════════
# Decision-theoretic point estimates  (Lecture 4)
# ═════════════════════════════════════════════════════════════════════════════
#
# Given a posterior, the "right" point estimate depends on your loss function.
# We expose several so the UI can offer a toggle ("Conservative" / "Expected" /
# "Optimistic"). See Lecture 4 pp. 1–4.

@dataclass
class DecisionSummary:
    conservative: float   # lower quartile of posterior; "what's the pessimistic case"
    expected: float       # posterior mean; Bayes estimator under squared loss
    typical: float        # posterior median; Bayes estimator under absolute loss
    most_likely: float | None  # posterior mode (when defined)
    optimistic: float     # upper quartile; "what's the optimistic case"

    def as_dict(self) -> dict:
        return {
            "conservative": round(self.conservative, 4),
            "expected": round(self.expected, 4),
            "typical": round(self.typical, 4),
            "most_likely": None if self.most_likely is None else round(self.most_likely, 4),
            "optimistic": round(self.optimistic, 4),
        }


def decision_summary(post: BetaPosterior) -> DecisionSummary:
    """
    >>> pr = BetaPrior(2, 2, 'fixed')
    >>> post = posterior_from_counts(50, 100, pr)
    >>> s = decision_summary(post)
    >>> abs(s.expected - 0.5) < 0.02
    True
    >>> s.conservative < s.expected < s.optimistic
    True
    """
    return DecisionSummary(
        conservative=beta_ppf(0.25, post.alpha, post.beta),
        expected=post.mean,
        typical=beta_ppf(0.5, post.alpha, post.beta),
        most_likely=beta_mode(post.alpha, post.beta),
        optimistic=beta_ppf(0.75, post.alpha, post.beta),
    )


# ═════════════════════════════════════════════════════════════════════════════
# Posterior predictive for a fit score  (Lecture 8 — moderation)
# ═════════════════════════════════════════════════════════════════════════════
#
# A student fit score is built from K independent binary "agreements" between
# student preferences and professor characteristics. For each dimension k, the
# professor has a Beta-posterior on the probability of "agreement." The
# student's fit score is the posterior predictive probability of a match.
#
# The predictive for a single Beta(alpha, beta) is just the posterior mean —
# so if we weight K matches by importance w_k, the expected match score is
# sum_k w_k * mean_k. For the credible band we propagate variance:
#   var(score) = sum_k w_k^2 * var(mean_k)    [independence assumption]
# giving a Gaussian-approximated credible band. This is deliberately simple
# and cheap: the lecture's moderation effect is captured because posteriors
# from small-n professors have high variance, so the band widens automatically.

@dataclass
class MatchScore:
    expected: float          # in [0, 1]
    ci_lower: float
    ci_upper: float
    components: list[dict]   # per-dimension contribution for explainability

    def as_dict(self) -> dict:
        return {
            "expected": round(self.expected, 4),
            "ci_lower": round(self.ci_lower, 4),
            "ci_upper": round(self.ci_upper, 4),
            "components": self.components,
        }


def posterior_predictive_match(
    components: Sequence[tuple[str, float, BetaPosterior]],
    level: float = 0.95,
) -> MatchScore:
    """
    Combine per-dimension Beta posteriors into a match score with a credible band.

    components: sequence of (label, weight, posterior). Weights are renormalized
    to sum to 1.

    >>> pr = BetaPrior(2, 2, 'fixed')
    >>> # Two well-observed dimensions, one high agreement, one medium
    >>> p1 = posterior_from_counts(90, 100, pr)
    >>> p2 = posterior_from_counts(50, 100, pr)
    >>> ms = posterior_predictive_match([('teaching', 1.0, p1), ('workload', 1.0, p2)])
    >>> 0.65 < ms.expected < 0.75
    True
    >>> ms.ci_lower < ms.expected < ms.ci_upper
    True
    """
    w_total = sum(max(0.0, w) for _, w, _ in components) or 1.0
    expected = 0.0
    var = 0.0
    rows = []
    z = _z_from_level(level)
    for label, w, post in components:
        w_norm = max(0.0, w) / w_total
        mu = post.mean
        v = post.variance
        expected += w_norm * mu
        var += (w_norm ** 2) * v
        rows.append({
            "label": label,
            "weight": round(w_norm, 4),
            "mean": round(mu, 4),
            "std": round(math.sqrt(v), 4),
            "n": post.n,
        })
    sd = math.sqrt(max(var, 0.0))
    return MatchScore(
        expected=expected,
        ci_lower=max(0.0, expected - z * sd),
        ci_upper=min(1.0, expected + z * sd),
        components=rows,
    )


def _z_from_level(level: float) -> float:
    """Two-sided Gaussian quantile for a confidence level. Small lookup, not scipy."""
    mapping = {0.50: 0.6745, 0.80: 1.2816, 0.90: 1.6449, 0.95: 1.96, 0.99: 2.5758}
    if level in mapping:
        return mapping[level]
    # Fallback to a rough approximation via rational function (Peter Acklam's inverse normal)
    p = (1.0 + level) / 2.0
    # Reasonable across 0.5..0.999
    a = [-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
         1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00]
    b = [-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
         6.680131188771972e01, -1.328068155288572e01]
    q = p - 0.5
    r = q * q
    num = ((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]
    den = (((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]
    return (q * num) / (den * r + 1.0)


# ═════════════════════════════════════════════════════════════════════════════
# Convenience wrappers used by bayesian_pipeline.py
# ═════════════════════════════════════════════════════════════════════════════

def build_take_again_pairs(professors: Iterable[dict]) -> list[tuple[int, int]]:
    """Extract (yes, yes+no) pairs from a school's raw professor list for EB fitting."""
    pairs = []
    for p in professors:
        yes = 0
        no = 0
        for r in p.get("reviews", []):
            v = r.get("would_take_again")
            if v == 1:
                yes += 1
            elif v == 0:
                no += 1
        if yes + no > 0:
            pairs.append((yes, yes + no))
    return pairs


def build_good_rating_pairs(professors: Iterable[dict], threshold: float = 3.5) -> list[tuple[int, int]]:
    """Extract (n_good, n_total) pairs from overall ratings."""
    pairs = []
    for p in professors:
        good = 0
        total = 0
        for r in p.get("reviews", []):
            c = r.get("clarity_rating")
            h = r.get("helpful_rating")
            if c is None or h is None:
                continue
            avg = (c + h) / 2
            if avg >= threshold:
                good += 1
            total += 1
        if total > 0:
            pairs.append((good, total))
    return pairs


def group_by_department(professors: Iterable[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for p in professors:
        dept = (p.get("department") or "Unknown").strip() or "Unknown"
        grouped.setdefault(dept, []).append(p)
    return grouped


if __name__ == "__main__":
    import doctest
    failures, total = doctest.testmod(verbose=True)
    print(f"\n{failures} failures in {total} tests")
