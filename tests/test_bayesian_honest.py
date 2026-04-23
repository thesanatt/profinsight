"""Property + scenario tests for bayesian_honest.py."""

from __future__ import annotations

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bayesian_honest import (  # noqa: E402
    ATTRIBUTES,
    extract_teaching_attributes,
    fit_grade_inflation_beta,
    grade_adjusted_quality,
)


# ─────────── 1. Grade-inflation correction ───────────

def _synth_profs(n_profs, n_reviews_each, alpha_range, true_beta, noise_sd, seed=0):
    rng = random.Random(seed)
    profs = []
    for _ in range(n_profs):
        a = alpha_range[0] + rng.random() * (alpha_range[1] - alpha_range[0])
        reviews = []
        for _ in range(n_reviews_each):
            gp = rng.choice([4.0, 3.0, 2.0, 1.0])
            r = a + true_beta * gp + rng.gauss(0, noise_sd)
            r = max(1, min(5, r))
            reviews.append({
                "clarity_rating": r,
                "helpful_rating": r,
                "grade": {4.0: "A", 3.0: "B", 2.0: "C", 1.0: "D"}[gp],
            })
        profs.append({"reviews": reviews})
    return profs


def test_beta_recovery_from_synthetic():
    """With β=0.3 in the data-generating process, we should recover ≈0.3."""
    profs = _synth_profs(30, 40, (2.0, 4.0), true_beta=0.3, noise_sd=0.2, seed=1)
    est = fit_grade_inflation_beta(profs)
    assert 0.2 < est < 0.4, f"expected β≈0.3, got {est}"


def test_beta_zero_when_no_grade_effect():
    """With β=0 in data-gen, estimator should be close to 0."""
    profs = _synth_profs(30, 30, (2.0, 4.0), true_beta=0.0, noise_sd=0.3, seed=2)
    est = fit_grade_inflation_beta(profs)
    assert abs(est) < 0.12


def test_beta_empty_input():
    assert fit_grade_inflation_beta([]) == 0.0
    # Profs without enough reviews should be skipped
    tiny = [{"reviews": [{"clarity_rating": 4, "helpful_rating": 4, "grade": "A"}]}]
    assert fit_grade_inflation_beta(tiny) == 0.0


def test_grade_adjusted_quality_shrinks_toward_B_student():
    """Prof with all A students rating 4.8 → adjusted rating should be lower."""
    prof = {"reviews": [
        {"clarity_rating": 4.8, "helpful_rating": 4.8, "grade": "A"}
        for _ in range(15)
    ]}
    q = grade_adjusted_quality(prof, beta=0.3)
    # mean_grade_gp = 4.0; baseline 3.0; adjustment = 0.3 * (4-3) = 0.3
    # adjusted = 4.8 - 0.3 = 4.5
    assert abs(q.adjusted_rating - 4.5) < 0.01
    assert q.grade_inflation_effect > 0  # raw was higher than adjusted


def test_grade_adjusted_quality_no_shift_when_at_baseline():
    """Prof whose students got mixed grades averaging B → no adjustment."""
    prof = {"reviews": [
        {"clarity_rating": 4.0, "helpful_rating": 4.0, "grade": g}
        for g in ["A", "B", "B", "C"]  # mean 3.0
    ]}
    q = grade_adjusted_quality(prof, beta=0.3)
    assert abs(q.adjusted_rating - 4.0) < 0.01
    assert abs(q.grade_inflation_effect) < 0.01


def test_grade_adjusted_quality_clips_to_scale():
    """Don't return > 5 or < 1 even on edge-case input."""
    # Prof with all failing students who somehow still rated 4.8
    prof = {"reviews": [
        {"clarity_rating": 4.8, "helpful_rating": 4.8, "grade": "F"}
        for _ in range(10)
    ]}
    q = grade_adjusted_quality(prof, beta=0.3)
    # adjusted = 4.8 - 0.3 * (0 - 3) = 4.8 + 0.9 = 5.7 → clipped to 5.0
    assert q.adjusted_rating == 5.0


def test_grade_adjusted_quality_none_without_enough_data():
    prof = {"reviews": [
        {"clarity_rating": 4, "helpful_rating": 4, "grade": "A"},  # only 1
    ]}
    assert grade_adjusted_quality(prof, beta=0.3) is None


# ─────────── 2. Teaching-style attribute extraction ───────────

def test_attribute_detection_simple_hits():
    reviews = [
        {"comment": "Records all lectures and posts slides online."},
        {"comment": "The slides are great, easy to follow."},
        {"comment": "Great prof!"},
        {"comment": "Multiple choice exams make it easier."},
    ]
    sigs = extract_teaching_attributes(reviews)
    names = {s.name for s in sigs}
    assert "slides_online" in names
    assert "multiple_choice" in names


def test_attribute_omits_zero_hit_attributes():
    reviews = [{"comment": "Great prof!"}] * 20
    sigs = extract_teaching_attributes(reviews)
    # Nothing specific mentioned → no signals returned
    assert sigs == []


def test_attribute_confidence_scales_with_hits():
    many_hits = [{"comment": "Records lectures and posts slides."}] * 15
    sigs_many = extract_teaching_attributes(many_hits)
    one_hit = [{"comment": "Records lectures and posts slides."}] + [{"comment": "generic"}] * 14
    sigs_one = extract_teaching_attributes(one_hit)

    many = next(s for s in sigs_many if s.name == "slides_online")
    one = next(s for s in sigs_one if s.name == "slides_online")
    assert many.posterior_mean > one.posterior_mean
    # "likely" > "probably" > "maybe" confidence tiers
    tier = {"likely": 3, "probably": 2, "maybe": 1, "unsupported": 0}
    assert tier[many.confidence] >= tier[one.confidence]


def test_attribute_handles_empty_and_no_comments():
    assert extract_teaching_attributes([]) == []
    # Reviews with only empty/missing comments → no comments to scan → empty
    assert extract_teaching_attributes([{"comment": ""}, {}, {"comment": "   "}]) == []


def test_attribute_returns_signal_dicts():
    """Every AttributeSignal serializes cleanly to a dict."""
    reviews = [{"comment": "Takes attendance every class."}] * 5
    sigs = extract_teaching_attributes(reviews)
    for s in sigs:
        d = s.as_dict()
        for k in ("name", "label", "polarity", "hits", "n_reviews",
                  "posterior_mean", "confidence"):
            assert k in d


def test_all_known_attributes_are_detectable():
    """Every attribute in ATTRIBUTES should fire on at least one canonical phrase."""
    canon = {
        "slides_online": "Posts slides online.",
        "attendance_mandatory": "Attendance is mandatory.",
        "attendance_optional": "Didn't go to lecture and was fine.",
        "multiple_choice": "Multiple choice exam.",
        "essay_exams": "Essay exam format.",
        "open_book": "Open note final.",
        "graded_on_curve": "Graded on a curve.",
        "group_projects": "Lots of group projects.",
        "heavy_reading": "Lots of reading every week.",
        "problem_sets": "Weekly problem sets.",
        "responsive_office_hours": "Responds to emails quickly.",
        "participation_graded": "Participation is graded.",
    }
    # Sanity: we have a canonical phrase for every declared attribute.
    assert set(canon.keys()) == set(ATTRIBUTES.keys())
    for name, phrase in canon.items():
        sigs = extract_teaching_attributes([{"comment": phrase}] * 3)
        found = {s.name for s in sigs}
        assert name in found, f"{name} didn't fire on canonical phrase {phrase!r}"
