"""Property + scenario tests for bayesian_advanced.py."""

from __future__ import annotations

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bayesian_advanced import (  # noqa: E402
    GRADE_GP,
    flag_outlier_reviews,
    outlier_probabilities,
    personal_grade_forecast,
    recency_vs_plain_delta,
    recency_weighted_counts,
)


# ─────────── 1. Personal grade forecast ───────────

PROF_EASY = {"A range": 70, "B range": 20, "C range": 8, "D/F": 2}
PROF_HARD = {"A range": 15, "B range": 35, "C range": 35, "D/F": 15}
PROF_FLAT = {"A range": 25, "B range": 25, "C range": 25, "D/F": 25}


def test_no_gpa_matches_base_rate():
    f = personal_grade_forecast(PROF_EASY, student_gpa=None)
    # With no student info, posterior == prior. A-range should dominate.
    assert abs(f.posterior_pct["A range"] - 70) < 1e-6


def test_strong_student_shifts_easy_prof_toward_A():
    f_strong = personal_grade_forecast(PROF_EASY, student_gpa=3.9)
    f_weak = personal_grade_forecast(PROF_EASY, student_gpa=2.0)
    # Strong student: P(A) should go up from 70%
    assert f_strong.posterior_pct["A range"] > 70
    # Weak student: P(A) should go down
    assert f_weak.posterior_pct["A range"] < 70


def test_weak_student_with_hard_prof_mostly_not_A():
    f = personal_grade_forecast(PROF_HARD, student_gpa=2.3)
    # With a hard prof and weak GPA, A-range should be rare
    assert f.posterior_pct["A range"] < 15
    # Most-likely grade shouldn't be A
    assert f.most_likely != "A range"


def test_expected_gpa_within_bounds():
    for gpa in [2.0, 3.0, 3.5, 3.9]:
        f = personal_grade_forecast(PROF_FLAT, student_gpa=gpa)
        assert 0.8 <= f.expected_gpa <= 4.0
        assert f.ci_lower <= f.expected_gpa <= f.ci_upper


def test_empty_grade_distribution_returns_graceful_default():
    f = personal_grade_forecast({}, student_gpa=3.5)
    # Should return a wide neutral forecast, not crash
    assert f.expected_gpa == 2.75
    assert sum(f.posterior_pct.values()) == 100.0  # uniform


def test_ci_widens_as_uncertainty_grows():
    # Flat prior → high variance → wide CI
    # Peaked prior → narrow CI
    f_flat = personal_grade_forecast(PROF_FLAT, student_gpa=None)
    f_easy = personal_grade_forecast(PROF_EASY, student_gpa=None)
    width_flat = f_flat.ci_upper - f_flat.ci_lower
    width_easy = f_easy.ci_upper - f_easy.ci_lower
    assert width_flat > width_easy


# ─────────── 2. Recency weighting ───────────

def test_recency_fresh_review_full_weight():
    now = datetime(2026, 1, 1)
    reviews = [{"date": "2026-01-01 00:00:00", "ok": True}]
    s, t = recency_weighted_counts(reviews, "ok", now=now)
    assert abs(s - 1.0) < 1e-9
    assert abs(t - 1.0) < 1e-9


def test_recency_old_review_low_weight():
    now = datetime(2026, 1, 1)
    reviews = [{"date": "2020-01-01 00:00:00", "ok": True}]  # ~6 years old
    s, t = recency_weighted_counts(reviews, "ok", half_life_days=365 * 3, now=now)
    # 2 half-lives old -> weight ~0.25
    assert 0.2 < s < 0.3
    assert 0.2 < t < 0.3


def test_recency_ignores_unparseable_dates():
    now = datetime(2026, 1, 1)
    reviews = [
        {"date": "",          "ok": True},
        {"date": "not a date", "ok": True},
        {"date": "2025-12-25 00:00:00", "ok": True},
    ]
    s, t = recency_weighted_counts(reviews, "ok", now=now)
    # Only the 1 valid review contributes
    assert abs(t - 1.0) < 0.05


def test_recency_custom_success_values():
    now = datetime(2026, 1, 1)
    reviews = [
        {"date": "2026-01-01 00:00:00", "take_again": 1},
        {"date": "2026-01-01 00:00:00", "take_again": 0},
        {"date": "2026-01-01 00:00:00", "take_again": -1},
    ]
    s, t = recency_weighted_counts(
        reviews, "take_again",
        success_values={1}, non_success_values={0},
        now=now,
    )
    # 1 success, 2 total (third is -1 = N/A, skipped)
    assert abs(s - 1.0) < 1e-6
    assert abs(t - 2.0) < 1e-6


def test_recency_vs_plain_delta():
    assert recency_vs_plain_delta(0.75, 0.75) is None
    assert "better" in recency_vs_plain_delta(0.90, 0.75)
    assert "worse" in recency_vs_plain_delta(0.60, 0.75)


# ─────────── 3. Outlier flagging ───────────

def test_single_troll_among_many_positives_flagged():
    ratings = [4.8, 4.7, 4.9, 4.6, 4.5, 4.8, 1.0]
    probs = outlier_probabilities(ratings)
    assert probs[-1] > 0.9
    # Others shouldn't be strongly flagged
    assert max(probs[:-1]) < 0.5


def test_consistent_ratings_none_flagged():
    ratings = [4.3, 4.5, 4.4, 4.5, 4.3, 4.4, 4.6]
    probs = outlier_probabilities(ratings)
    assert max(probs) < 0.5


def test_too_few_reviews_no_flags():
    # With < min_reviews there's no reference distribution — return all zeros
    assert outlier_probabilities([4.5, 1.0]) == [0.0, 0.0]
    assert outlier_probabilities([4.5, 1.0, 4.5]) == [0.0, 0.0, 0.0]


def test_flag_outlier_reviews_on_dicts():
    reviews = [
        {"clarity_rating": 5, "helpful_rating": 5},
        {"clarity_rating": 4, "helpful_rating": 5},
        {"clarity_rating": 5, "helpful_rating": 4},
        {"clarity_rating": 5, "helpful_rating": 5},
        {"clarity_rating": 1, "helpful_rating": 1},  # troll
    ]
    out = flag_outlier_reviews(reviews)
    assert out["n_flagged"] == 1
    assert 4 in out["flagged_indices"]
    # Returned per_review list must be same length as input (even with Nones)
    assert len(out["per_review"]) == len(reviews)


def test_flag_handles_missing_ratings():
    reviews = [
        {"clarity_rating": 5, "helpful_rating": 5},
        {"clarity_rating": None, "helpful_rating": None},  # no data
        {"clarity_rating": 4, "helpful_rating": 5},
        {"clarity_rating": 4, "helpful_rating": 4},
        {"clarity_rating": 5, "helpful_rating": 5},
    ]
    out = flag_outlier_reviews(reviews)
    # Shouldn't crash; missing one produces 0.0 for that index
    assert out["per_review"][1] == 0.0
