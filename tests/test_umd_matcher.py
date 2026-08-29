"""Tests for the Testudo instructor -> RMP professor matcher in umd_scheduler.py."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from umd_scheduler import _normalize_name, match_instructor_to_prof  # noqa: E402


def _index(profs):
    idx = {}
    for p in profs:
        idx.setdefault(_normalize_name(p["name"]), []).append(p)
    return idx


PROFS = [
    {"professor_id": "lee-fin", "name": "Seokwoo Lee", "department": "Finance"},
    {"professor_id": "lee-eng", "name": "Sung Lee", "department": "Engineering"},
    {"professor_id": "zur", "name": "Emanuel Zur", "department": "Accounting"},
    {"professor_id": "lyons-hist", "name": "Clare Lyons", "department": "History"},
    {"professor_id": "lyons-eng", "name": "Clare Lyons", "department": "English"},
]
INDEX = _index(PROFS)


def test_honorific_is_stripped_with_its_period():
    assert _normalize_name("Dr. John Smith") == "john smith"
    assert _normalize_name("Prof. Jane Doe") == "jane doe"


def test_initial_only_match_does_not_cross_departments():
    # "S. Lee" style matches were attributing aerospace sections to a Finance
    # professor; with a strict gate and no exact name, this must be None.
    assert match_instructor_to_prof("Seong-Ho Lee", INDEX, PROFS,
                                    expected_department="Engineering, Aerospace") is None


def test_exact_name_survives_department_label_mismatch():
    # RMP says "Accounting"; Testudo subject is "Business and Management".
    # Exact full-name matches use a relaxed gate.
    m = match_instructor_to_prof("Emanuel Zur", INDEX, PROFS, expected_department="Accounting and Information Assurance")
    assert m and m["professor_id"] == "zur"


def test_duplicate_names_resolved_by_department():
    hist = match_instructor_to_prof("Clare Lyons", INDEX, PROFS, expected_department="History")
    eng = match_instructor_to_prof("Clare Lyons", INDEX, PROFS, expected_department="English")
    assert hist["professor_id"] == "lyons-hist"
    assert eng["professor_id"] == "lyons-eng"


def test_initial_or_prefix_first_name_matches_within_department():
    m = match_instructor_to_prof("S. Lee", INDEX, PROFS, expected_department="Engineering")
    assert m and m["professor_id"] == "lee-eng"
    # Ambiguous initial across departments with no department signal: no match.
    assert match_instructor_to_prof("S. Lee", INDEX, PROFS) is None


def test_exact_name_in_matching_department():
    m = match_instructor_to_prof("Sung Lee", INDEX, PROFS, expected_department="Engineering")
    assert m and m["professor_id"] == "lee-eng"
