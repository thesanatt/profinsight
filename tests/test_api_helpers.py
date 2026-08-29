"""Tests for pure helpers in api.py and the grade/tag helpers in bayesian_pipeline.py."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api import _course_key, _course_matches  # noqa: E402
from bayesian_pipeline import derive_top_tags, letter_grade  # noqa: E402


def test_course_key_normalizes_spacing_and_case():
    assert _course_key("eecs 281") == "EECS281"
    assert _course_key("EECS-281") == "EECS281"
    assert _course_key("  Eecs281 ") == "EECS281"


def test_course_matches_is_exact_after_normalization():
    assert _course_matches("EECS281", "eecs 281")
    assert _course_matches("MATH 215", "MATH215")
    # The old substring rule matched these; they are different courses.
    assert not _course_matches("CS101", "CS1010")
    assert not _course_matches("MATH2", "MATH215")
    assert not _course_matches("", "MATH215")


def test_letter_grade_whitelist():
    assert letter_grade("A") == "A"
    assert letter_grade(" b- ") == "B-"
    assert letter_grade("Not sure yet") is None
    assert letter_grade("Not_Sure_Yet") is None
    assert letter_grade("Rather_Not_Say") is None
    assert letter_grade("Pass") is None
    assert letter_grade("Drop/Withdrawal") is None
    assert letter_grade("") is None
    assert letter_grade(None) is None


def test_derive_top_tags_counts_and_orders():
    reviews = [
        {"rating_tags": "Caring--Tough grader--Amazing lectures"},
        {"rating_tags": "Caring--Tough grader"},
        {"rating_tags": "Caring"},
        {"rating_tags": ""},
        {},
    ]
    tags = derive_top_tags(reviews)
    assert tags[0] == {"tag": "Caring", "count": 3}
    assert tags[1] == {"tag": "Tough grader", "count": 2}
    assert tags[2] == {"tag": "Amazing lectures", "count": 1}
    assert derive_top_tags([]) == []


def test_headline_good_prefers_calibrated_posterior():
    from api import _headline_good
    prof = {
        "calibrated_analysis": {"good_rating": {"mean": 0.81, "ci_lower": 0.6, "ci_upper": 0.95}},
        "bayesian_analysis": {"rating_posteriors": {"good": {"mean": 0.7, "ci_lower": 0.5, "ci_upper": 0.9}}},
    }
    assert _headline_good(prof) == {"mean": 0.81, "ci_lower": 0.6, "ci_upper": 0.95}
    legacy = {"bayesian_analysis": {"rating_posteriors": {"good": {"mean": 0.7, "ci_lower": 0.5, "ci_upper": 0.9}}}}
    assert _headline_good(legacy)["mean"] == 0.7
    assert _headline_good({})["mean"] is None


def test_optimizer_treats_zero_would_take_again_as_zero():
    """A 0% would-take-again professor must score below a missing value, not equal to 50%."""
    import api

    def prof(pid, wta, a_range):
        return {
            "professor_id": pid, "name": pid, "department": "Testing",
            "summary": {"avg_rating": 4.0, "avg_difficulty": 3.0, "num_ratings": 20, "would_take_again_pct": wta},
            "calibrated_analysis": {"good_rating": {"mean": 0.7, "ci_lower": 0.5, "ci_upper": 0.9}},
            "grade_probabilities": {"A range": a_range, "B range": 100 - a_range, "C range": 0, "D/F": 0},
            "class_breakdown": [{"class_name": "TEST101", "num_reviews": 20, "avg_rating": 4.0, "grades": {}}],
            "verdict": "", "verdict_emoji": "",
        }

    data = {"analysis": [prof("zero_wta", 0.0, 50), prof("missing_wta", -1, 50), prof("no_grades", 80.0, 0)]}
    real_load = api.load_school
    api.load_school = lambda slug: data
    try:
        out = api.optimize_semester("synthetic", courses="TEST101", preference="balanced")
        rec = out["recommended"]["TEST101"]
        scores = {rec["id"]: rec["optimizer_score"]}
        scores.update({a["id"]: a["optimizer_score"] for a in out["alternatives"].get("TEST101", [])})
        assert scores["zero_wta"] < scores["missing_wta"]
        # A real 0% A-range must not be replaced by the 30% placeholder either.
        sched = api.schedule_helper("synthetic", courses="TEST101")
        assert len(sched["results"]["TEST101"]) == 3
    finally:
        api.load_school = real_load
