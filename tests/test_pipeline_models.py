"""Tests for the model classes in bayesian_pipeline.py (GP, Naive Bayes, trend labels)."""

from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bayesian_pipeline import (  # noqa: E402
    GaussianProcessRegression,
    NaiveBayesClassifier,
    summarize_trend,
)


# ─────────────────────────── Gaussian process ───────────────────────────

def _reviews(pairs):
    """(months_offset, rating) -> review dicts with RMP-style dates."""
    out = []
    for months, rating in pairs:
        year = 2018 + months // 12
        month = 1 + months % 12
        out.append({"date": f"{year:04d}-{month:02d}-15 12:00:00 +0000 UTC",
                    "clarity_rating": rating, "helpful_rating": rating})
    return out


def test_gp_is_centered_on_the_data_mean():
    gp = GaussianProcessRegression(length_scale=6.0, signal_variance=1.0, noise_variance=0.8)
    x = [0.0, 1.0, 2.0, 3.0]
    y = [4.5, 4.5, 4.5, 4.5]
    # Far outside the data a zero-mean GP would revert to 0; a centered one holds the mean.
    pred = gp.predict(x, y, [1.5, 60.0, 240.0])
    for m in pred["mean"]:
        assert abs(m - 4.5) < 1e-6


def test_gp_no_longer_dips_below_floor_in_gaps():
    gp = GaussianProcessRegression(length_scale=6.0, signal_variance=1.0, noise_variance=0.8)
    # Two clusters of 5-star reviews separated by a four-year gap.
    reviews = _reviews([(0, 5), (1, 5), (2, 5), (50, 5), (51, 5), (52, 5)])
    trend = gp.fit_professor_trend(reviews)
    assert not trend["insufficient_data"]
    assert min(trend["pred_mean"]) >= 4.0
    assert trend["length_scale_months"] in GaussianProcessRegression.LENGTH_SCALE_GRID
    assert trend["log_marginal_likelihood"] is not None


def test_gp_marginal_likelihood_prefers_long_scale_for_flat_data():
    gp = GaussianProcessRegression(length_scale=6.0, signal_variance=1.0, noise_variance=0.8)
    x = [float(i) for i in range(0, 60, 3)]
    flat = [4.0 + (0.05 if i % 2 else -0.05) for i in range(len(x))]
    ls_flat, ll_flat = gp.select_length_scale(x, flat)
    assert ls_flat >= 12.0
    assert ll_flat > float("-inf")
    # A strong step change halfway should prefer a shorter scale than flat data.
    step = [3.0] * (len(x) // 2) + [5.0] * (len(x) - len(x) // 2)
    ls_step, _ = gp.select_length_scale(x, step)
    assert ls_step <= ls_flat


def test_gp_predictions_stay_in_rating_range():
    gp = GaussianProcessRegression(length_scale=6.0, signal_variance=1.0, noise_variance=0.8)
    reviews = _reviews([(0, 1), (1, 1), (2, 5), (3, 5), (30, 1), (31, 5)])
    trend = gp.fit_professor_trend(reviews)
    assert all(1.0 <= m <= 5.0 for m in trend["pred_mean"])
    assert all(lo <= m <= hi for lo, m, hi in
               zip(trend["pred_ci_lower"], trend["pred_mean"], trend["pred_ci_upper"]))


# ─────────────────────────── Naive Bayes ───────────────────────────

TOY = [
    ("the exams were brutal and the midterm covered everything", "exams"),
    ("final exam was tricky, study the practice tests", "exams"),
    ("so much homework every week, the workload is heavy", "workload"),
    ("readings pile up, expect hours of assignments", "workload"),
    ("lectures are clear and engaging with great slides", "lectures"),
    ("explains concepts well, lecture is never boring", "lectures"),
    ("very approachable, office hours were helpful and kind", "approachability"),
    ("responds to email quickly and really cares", "approachability"),
    ("tough grader but the rubric is clear", "grading"),
    ("harsh grading with no partial credit", "grading"),
]


def test_nb_fit_learns_obvious_categories():
    nb = NaiveBayesClassifier()
    nb.fit([t for t, _ in TOY], [c for _, c in TOY])
    assert nb.n_training_docs == len(TOY)
    top = lambda s: max(nb.classify(s).items(), key=lambda kv: kv[1])[0]  # noqa: E731
    assert top("the midterm and final exam were hard") == "exams"
    assert top("homework and assignments every week") == "workload"
    assert top("office hours were helpful, very kind") == "approachability"


def test_nb_save_load_roundtrip():
    nb = NaiveBayesClassifier()
    nb.fit([t for t, _ in TOY], [c for _, c in TOY])
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "m.json")
        nb.save(path)
        loaded = NaiveBayesClassifier.load(path)
        with open(path) as f:
            assert json.load(f)["version"] == 1
    for text, _ in TOY:
        assert nb.classify(text) == loaded.classify(text)
    assert loaded.n_training_docs == len(TOY)
    assert loaded.category_total_words == nb.category_total_words


def test_nb_uniform_prior_option():
    nb = NaiveBayesClassifier()
    nb.fit([t for t, _ in TOY] + ["extra grading text"] * 5,
           [c for _, c in TOY] + ["grading"] * 5, uniform_prior=True)
    assert all(abs(p - 0.2) < 1e-9 for p in nb.category_prior.values())


def test_nb_seed_fallback_still_classifies():
    nb = NaiveBayesClassifier()
    probs = nb.classify("the exam was hard")
    assert abs(sum(probs.values()) - 1.0) < 1e-6
    assert max(probs, key=probs.get) == "exams"


# ─────────────────────────── Trend labels ───────────────────────────

def test_summarize_trend_labels():
    assert summarize_trend([]) == "Not enough data"
    assert summarize_trend([4.5] * 20) == "Consistently highly rated"
    assert summarize_trend([3.2] * 20) == "Stable, middle-of-the-road ratings"
    assert summarize_trend([2.0] * 20) == "Consistently low rated"
    assert summarize_trend([3.0] * 10 + [4.0] * 10) == "Significantly improving over time"
    assert summarize_trend([4.0] * 10 + [3.0] * 10) == "Declining over time"
    assert summarize_trend([3.0] * 10 + [3.4] * 10) == "Trending upward recently"
    assert summarize_trend([3.4] * 10 + [3.0] * 10) == "Trending downward recently"
