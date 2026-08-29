"""
ProfInsight — Bayesian "essentials" layer
==========================================

Three user-facing primitives built on top of `bayesian_calibration.py`:

1. personal_grade_forecast(...)     — "given YOUR GPA, here's your probable grade"
2. recency_weighted_counts(...)     — old reviews count less, smoothly
3. outlier_probabilities(...)       — Bayesian mixture over reviews to flag trolls

Everything is pure Python. No scipy/numpy. Each primitive has inline doctests
and stays under 100 lines so the math is auditable at a glance.

Concept-to-lecture mapping (files in class_content/):
  * Personal grade forecast        → Lecture 6 pp. 1–3 (linear/regression),
                                     Lecture 7 pp. 1–3 (Bayesian posterior predictive)
  * Recency-weighted Beta update   → Lecture 2 pp. 2–4 (pseudocounts reinterpretation
                                     of weighted evidence — each observation
                                     contributes fractional alpha/beta mass)
  * Mixture-based outlier flag     → Lecture 4 pp. 1–4 (posterior over latent
                                     discrete assignments; same 0–1 loss framing
                                     used for decision)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional


# ═════════════════════════════════════════════════════════════════════════════
# 1. Personal grade forecast
# ═════════════════════════════════════════════════════════════════════════════
#
# The prof's historical grade distribution tells us the base rate — P(grade).
# The student's own GPA is evidence about the student's academic signal, which
# we model as a Gaussian likelihood centered on each letter-grade's GPA value.
# Combining via Bayes gives a posterior over letter grades for THIS student in
# THIS class. The credible interval on expected GPA is computed directly from
# the posterior's variance.
#
# We deliberately don't pull in a more complex hierarchical model here: the
# simple form is explainable to students ("you're a 3.8 student, and this
# class's grade distribution is skewed toward Bs, so your probable GPA here
# is 3.4"), and the posterior captures the right qualitative behavior.

# Grade bucket → GPA value. Anchored to Michigan/typical US scale.
GRADE_GP = {
    "A range": 3.8,
    "B range": 3.0,
    "C range": 2.0,
    "D/F":     0.8,
}

# How loosely a student's cumulative GPA predicts a single-class grade.
# Small values = GPA strongly constrains grade; large = GPA barely informs it.
# 0.7 is ~"students usually fluctuate ~0.7 points around their average."
DEFAULT_GPA_SPREAD = 0.7


@dataclass
class GradeForecast:
    posterior_pct: dict      # grade bucket -> probability (in %)
    expected_gpa: float
    ci_lower: float          # lower 95% credible bound on expected GPA
    ci_upper: float
    most_likely: str
    n_reviews_used: int      # sample size backing the prof's base rate
    used_student_gpa: Optional[float]

    def as_dict(self) -> dict:
        return {
            "posterior_pct": self.posterior_pct,
            "expected_gpa": round(self.expected_gpa, 2),
            "ci_lower": round(self.ci_lower, 2),
            "ci_upper": round(self.ci_upper, 2),
            "most_likely": self.most_likely,
            "n_reviews_used": self.n_reviews_used,
            "used_student_gpa": self.used_student_gpa,
        }


def personal_grade_forecast(
    prof_grade_distribution: dict,
    student_gpa: Optional[float] = None,
    *,
    n_reviews: int = 0,
    gpa_spread: float = DEFAULT_GPA_SPREAD,
) -> GradeForecast:
    """
    Forecast a student's grade with a given professor, as a full posterior
    over letter-grade buckets plus a credible interval on expected GPA.

    `prof_grade_distribution` is percent-valued (e.g. `{"A range": 50, ...}`);
    we treat it as the prior P(grade). `student_gpa` is the Gaussian-likelihood
    observation; if None the posterior collapses to the prior.

    >>> f = personal_grade_forecast({"A range": 50, "B range": 30, "C range": 15, "D/F": 5}, student_gpa=3.8, n_reviews=120)
    >>> f.most_likely
    'A range'
    >>> f.expected_gpa > 3.4
    True
    >>> # Without GPA, just returns base rate
    >>> g = personal_grade_forecast({"A range": 50, "B range": 50}, student_gpa=None)
    >>> abs(g.posterior_pct['A range'] - 50) < 1e-6
    True
    """
    # Normalize prior; drop buckets with zero mass.
    prior = {g: pct / 100.0 for g, pct in prof_grade_distribution.items() if pct and pct > 0}
    if not prior:
        # No historical grade data — return a flat, very wide forecast.
        return GradeForecast(
            posterior_pct={g: round(100.0 / len(GRADE_GP), 1) for g in GRADE_GP},
            expected_gpa=2.75,
            ci_lower=0.8,
            ci_upper=4.0,
            most_likely="B range",
            n_reviews_used=0,
            used_student_gpa=student_gpa,
        )
    Z = sum(prior.values())
    prior = {g: p / Z for g, p in prior.items()}

    if student_gpa is None:
        posterior = prior
    else:
        unnorm = {}
        for g, p in prior.items():
            gp = GRADE_GP.get(g, 2.5)
            # Gaussian likelihood of observing this GPA given grade g in-class.
            likelihood = math.exp(-0.5 * ((student_gpa - gp) / gpa_spread) ** 2)
            unnorm[g] = p * likelihood
        Z2 = sum(unnorm.values()) or 1.0
        posterior = {g: v / Z2 for g, v in unnorm.items()}

    expected = sum(GRADE_GP.get(g, 2.5) * p for g, p in posterior.items())
    variance = sum((GRADE_GP.get(g, 2.5) - expected) ** 2 * p for g, p in posterior.items())
    sd = math.sqrt(max(variance, 0.0))
    most_likely = max(posterior, key=posterior.get)

    return GradeForecast(
        posterior_pct={g: round(p * 100, 1) for g, p in posterior.items()},
        expected_gpa=expected,
        ci_lower=max(0.0, expected - 1.96 * sd),
        ci_upper=min(4.0, expected + 1.96 * sd),
        most_likely=most_likely,
        n_reviews_used=n_reviews,
        used_student_gpa=student_gpa,
    )


# ═════════════════════════════════════════════════════════════════════════════
# 2. Recency-weighted review counts  (for any binary outcome)
# ═════════════════════════════════════════════════════════════════════════════
#
# A review from 2020 shouldn't count as much as one from last month when we
# estimate CURRENT professor quality. We re-use the Beta-Binomial framework
# by multiplying each observation's contribution by an exponential decay
# weight based on its age. The Beta posterior is then Beta(α + Σw_i·x_i,
# β + Σw_i·(1 - x_i)) — a fractional-counts form that's still conjugate.
#
# half_life_days controls the decay: a review that old counts as half of
# a brand-new review. Default 3 years ≈ one undergrad generation.

def recency_weighted_counts(
    reviews: Iterable[dict],
    success_key: str,
    *,
    half_life_days: float = 3.0 * 365.25,
    now: Optional[datetime] = None,
    success_values: Optional[set] = None,
    non_success_values: Optional[set] = None,
) -> tuple[float, float]:
    """
    Walk a list of reviews; return (weighted_successes, weighted_total).

    success_key is the field inspected on each review. success_values /
    non_success_values allow custom matching (e.g., take-again is 1/0/-1).

    >>> from datetime import datetime, timedelta
    >>> now = datetime(2026, 1, 1)
    >>> reviews = [
    ...   {"date": "2026-01-01 00:00:00", "ok": True},    # age 0 -> w=1
    ...   {"date": "2023-01-01 00:00:00", "ok": True},    # age ~3y -> w=0.5
    ...   {"date": "2020-01-01 00:00:00", "ok": False},   # age ~6y -> w=0.25
    ... ]
    >>> s, t = recency_weighted_counts(reviews, "ok", now=now)
    >>> round(s, 2)  # 1 + 0.5
    1.5
    >>> round(t, 2)  # 1 + 0.5 + 0.25
    1.75
    """
    if now is None:
        now = datetime.now()
    decay = math.log(2.0) / float(half_life_days)
    total_w = 0.0
    success_w = 0.0
    for r in reviews:
        date_str = r.get("date", "") or ""
        try:
            dt = datetime.strptime(date_str[:19], "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            try:
                dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
            except (ValueError, TypeError):
                continue
        age_days = max(0.0, (now - dt).total_seconds() / 86400.0)
        w = math.exp(-decay * age_days)

        v = r.get(success_key)
        if success_values is not None:
            if v in success_values:
                success_w += w
                total_w += w
            elif non_success_values is None or v in non_success_values:
                total_w += w
            # else: skip (treat as N/A)
        else:
            # Default: treat any truthy value as success
            total_w += w
            if v:
                success_w += w
    return success_w, total_w


def recency_vs_plain_delta(recency_mean: float, plain_mean: float) -> Optional[str]:
    """Plain-English description of how much recency weighting shifted the number.

    Returns None if the shift is negligible.

    >>> recency_vs_plain_delta(0.72, 0.85)
    'Recent reviews are noticeably worse than older ones.'
    >>> recency_vs_plain_delta(0.90, 0.82)
    'Recent reviews are noticeably better than older ones.'
    >>> recency_vs_plain_delta(0.80, 0.81) is None
    True
    """
    diff = recency_mean - plain_mean
    if abs(diff) < 0.04:
        return None
    if diff >= 0.04:
        return "Recent reviews are noticeably better than older ones."
    return "Recent reviews are noticeably worse than older ones."


# ═════════════════════════════════════════════════════════════════════════════
# 3. Bayesian outlier flagging on reviews
# ═════════════════════════════════════════════════════════════════════════════
#
# Mixture model: each review was drawn either from the prof's "genuine"
# rating distribution (assumed Gaussian around the prof-level mean with
# prof-level std) OR from an "outlier" distribution (uniform over [1, 5]).
# The prior P(outlier) is small (default 10%). Applying Bayes to each review
# gives P(outlier | rating_i).
#
# We compute the mean/std from the OTHER reviews (leave-one-out) so a single
# rogue review can't drag the "genuine" distribution toward itself.

UNIFORM_RATING_DENSITY = 1.0 / 4.0  # 1..5 uniform


def outlier_probabilities(
    ratings: list,
    *,
    prior_outlier: float = 0.10,
    min_std: float = 0.75,
    min_reviews: int = 4,
) -> list[float]:
    """
    Per-review P(outlier | rating). Returned in the same order as `ratings`.

    With fewer than `min_reviews` reviews we don't flag anything — there isn't
    enough of a reference distribution to detect "outliers" yet.

    >>> # one clear outlier
    >>> probs = outlier_probabilities([4.5, 4.8, 4.6, 4.7, 1.0], prior_outlier=0.1)
    >>> probs[-1] > 0.9
    True
    >>> # consistent ratings -> nothing flagged
    >>> probs = outlier_probabilities([4.5, 4.6, 4.4, 4.5, 4.6])
    >>> max(probs) < 0.5
    True
    >>> # too few reviews -> all zero
    >>> outlier_probabilities([4.5, 3.0])
    [0.0, 0.0]
    """
    n = len(ratings)
    if n < min_reviews:
        return [0.0] * n

    results = []
    for i, r in enumerate(ratings):
        others = ratings[:i] + ratings[i + 1:]
        m = sum(others) / len(others)
        if len(others) > 1:
            var = sum((x - m) ** 2 for x in others) / len(others)
        else:
            var = 1.0
        sd = max(min_std, math.sqrt(max(var, 0.0)))

        # P(r | genuine) — Gaussian
        p_genuine = math.exp(-0.5 * ((r - m) / sd) ** 2) / (sd * math.sqrt(2 * math.pi))
        # P(r | outlier) — uniform over the rating range
        p_outlier = UNIFORM_RATING_DENSITY

        num = prior_outlier * p_outlier
        den = num + (1 - prior_outlier) * p_genuine
        if den <= 0:
            results.append(0.0)
        else:
            results.append(num / den)
    return results


def flag_outlier_reviews(reviews: list, rating_key: str = "overall") -> dict:
    """
    Apply outlier_probabilities to a list of review dicts. Returns a dict:

        {
          "per_review": [p_outlier, p_outlier, ...],  # same order as input
          "n_flagged":  int,                          # how many crossed 0.5
          "flagged_indices": [i, j, ...],
        }

    When called with rating_key="overall" we derive the score from
    (clarity + helpful) / 2 if present.

    >>> reviews = [
    ...   {"clarity_rating": 5, "helpful_rating": 5},
    ...   {"clarity_rating": 5, "helpful_rating": 5},
    ...   {"clarity_rating": 4, "helpful_rating": 5},
    ...   {"clarity_rating": 5, "helpful_rating": 4},
    ...   {"clarity_rating": 1, "helpful_rating": 1},  # troll
    ... ]
    >>> out = flag_outlier_reviews(reviews)
    >>> out["n_flagged"] == 1
    True
    >>> 4 in out["flagged_indices"]
    True
    """
    ratings = []
    valid_idx = []
    for i, r in enumerate(reviews):
        if rating_key == "overall":
            c = r.get("clarity_rating")
            h = r.get("helpful_rating")
            vals = [v for v in (c, h) if v is not None]
            if not vals:
                ratings.append(None)
                continue
            ratings.append(sum(vals) / len(vals))
        else:
            ratings.append(r.get(rating_key))
        if ratings[-1] is not None:
            valid_idx.append(i)

    # Only run detector on the valid ratings
    valid_values = [ratings[i] for i in valid_idx]
    probs_valid = outlier_probabilities(valid_values)

    per_review = [0.0] * len(reviews)
    for idx_in_valid, orig_i in enumerate(valid_idx):
        per_review[orig_i] = probs_valid[idx_in_valid]

    flagged_indices = [i for i, p in enumerate(per_review) if p > 0.5]
    return {
        "per_review": [round(p, 3) for p in per_review],
        "n_flagged": len(flagged_indices),
        "flagged_indices": flagged_indices,
    }


if __name__ == "__main__":
    import doctest
    failures, total = doctest.testmod(verbose=True)
    print(f"\n{failures} failures in {total} tests")
