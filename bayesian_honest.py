"""
ProfInsight — Honest Signals layer
===================================

Two primitives that directly address the strongest signals from the student
research audit (docs/USER_RESEARCH.md):

1. `fit_grade_inflation_beta(...)` + `grade_adjusted_quality(...)`
   The "rating ↔ easiness" confound is documented with correlation -0.63 to
   -0.89 in peer-reviewed studies. Students pick profs because they're easy,
   not because they're good. We fit a pooled fixed-effects regression
   `rating_i = α_prof + β · grade_gp_i + ε` by within-professor OLS across
   every review in a school's dataset (no prior on β; it is a point estimate
   with tens of thousands of observations), then report each prof's rating
   at a fixed grade level separately from their raw rating.

2. `extract_teaching_attributes(...)`
   Student research finding #9: "What I like to use RateMyProfessor for is
   finding teachers that use powerpoints, and post their lectures online."
   This scans review text for concrete attributes (slides posted, mandatory
   attendance, MC exams, curved grading, group projects, recorded lectures,
   etc.) and returns a Beta-posterior confidence per attribute. Lecture 2
   Beta-Binomial with a weak zero-inflated prior.

All pure Python, inline doctests.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable, Optional


# ═════════════════════════════════════════════════════════════════════════════
# 1. Grade-inflation correction
# ═════════════════════════════════════════════════════════════════════════════

# Grade -> GPA. Anchored to typical US 4-point scale. We collapse +/− to
# their letter's GP so a handful of A-/B+ reviews don't dominate the regression.
_GP_MAP = {
    "A+": 4.0, "A": 4.0, "A-": 3.7,
    "B+": 3.3, "B": 3.0, "B-": 2.7,
    "C+": 2.3, "C": 2.0, "C-": 1.7,
    "D+": 1.3, "D": 1.0, "D-": 0.7,
    "F": 0.0,
}

# Baseline at which we report the adjusted rating — a "typical B student"
# benchmark, so the adjusted rating is directly comparable across profs with
# different grade distributions.
ADJUSTMENT_BASELINE_GP = 3.0


def _grade_gp(grade_str: Optional[str]) -> Optional[float]:
    """Map a reported grade string to a GPA value. None for unusable grades."""
    if not grade_str:
        return None
    g = grade_str.strip().upper()
    # Strip whitespace and trailing junk
    g = re.sub(r"\s+", "", g)
    if g in _GP_MAP:
        return _GP_MAP[g]
    # "Rather not say", "Audit", "Withdrawal", etc. → unusable
    return None


def _rating_from_review(r: dict) -> Optional[float]:
    """Derive a 1–5 overall-rating score from a review dict."""
    c = r.get("clarity_rating")
    h = r.get("helpful_rating")
    vals = [v for v in (c, h) if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def fit_grade_inflation_beta(professors: Iterable[dict]) -> float:
    """
    Fit a single global β coefficient in `rating = α_prof + β · grade_gp + ε`
    by OLS on ALL (rating, grade) pairs in the dataset, sweeping each prof's
    α as a fixed effect.

    Technique: for each prof, subtract that prof's mean rating and mean grade,
    then OLS on the centered pairs. This is the fixed-effects estimator — β
    captures within-professor variation between a student's grade and rating,
    not between-professor differences.

    A positive β means students who got higher grades rated the prof higher
    (the classic "easy-class-inflation" effect).

    >>> # Synthetic data where every prof has β=0.3 effect
    >>> import random
    >>> rng = random.Random(0)
    >>> profs = []
    >>> for p in range(15):
    ...     alpha = 2 + rng.random() * 2  # prof quality in [2, 4]
    ...     reviews = []
    ...     for _ in range(25):
    ...         gp = rng.choice([4.0, 3.0, 2.0, 1.0])
    ...         rating = alpha + 0.3 * gp + rng.gauss(0, 0.3)
    ...         rating = max(1, min(5, rating))
    ...         reviews.append({"clarity_rating": rating, "helpful_rating": rating,
    ...                         "grade": {4.0:"A",3.0:"B",2.0:"C",1.0:"D"}[gp]})
    ...     profs.append({"reviews": reviews})
    >>> beta = fit_grade_inflation_beta(profs)
    >>> 0.2 < beta < 0.4
    True
    """
    # Stream every valid (rating - prof_mean_rating, gp - prof_mean_gp) pair.
    xs_centered = []
    ys_centered = []
    for prof in professors:
        pair_r, pair_g = [], []
        for r in prof.get("reviews", []):
            rating = _rating_from_review(r)
            gp = _grade_gp(r.get("grade"))
            if rating is None or gp is None:
                continue
            pair_r.append(rating)
            pair_g.append(gp)
        if len(pair_r) < 3:
            # Need at least 3 reviews with both fields to estimate a prof's α.
            continue
        mean_r = sum(pair_r) / len(pair_r)
        mean_g = sum(pair_g) / len(pair_g)
        # Must have some variance in grade within this prof to contribute
        g_var = sum((g - mean_g) ** 2 for g in pair_g)
        if g_var < 1e-6:
            continue
        for r_i, g_i in zip(pair_r, pair_g):
            xs_centered.append(g_i - mean_g)
            ys_centered.append(r_i - mean_r)

    if not xs_centered:
        return 0.0

    # OLS on centered data
    num = sum(x * y for x, y in zip(xs_centered, ys_centered))
    den = sum(x * x for x in xs_centered)
    if den < 1e-9:
        return 0.0
    return num / den


@dataclass
class AdjustedQuality:
    raw_mean: float                  # avg rating over the reviews that report a letter grade
    adjusted_rating: float           # rating an average B student would give them
    grade_inflation_effect: float    # raw_mean - adjusted_rating; how much grade-inflation inflated the raw
    n_reviews_used: int
    beta_used: float                 # the pooled β we applied

    def as_dict(self) -> dict:
        return {
            "raw_mean": round(self.raw_mean, 3),
            "adjusted_rating": round(self.adjusted_rating, 3),
            "grade_inflation_effect": round(self.grade_inflation_effect, 3),
            "n_reviews_used": self.n_reviews_used,
            "beta_used": round(self.beta_used, 4),
        }


def grade_adjusted_quality(professor: dict, beta: float) -> Optional[AdjustedQuality]:
    """
    Compute this prof's quality adjusted for grade inflation using the pooled β.

    adjusted_rating = mean_rating - β · (mean_grade_gp - ADJUSTMENT_BASELINE_GP)

    Interpretation: "what would this prof's rating be if students got a B on
    average instead of their actual grade distribution?"

    >>> # A prof whose students all got A's and rated 4.8
    >>> prof = {"reviews": [
    ...     {"clarity_rating": 4.8, "helpful_rating": 4.8, "grade": "A"}
    ...     for _ in range(10)
    ... ]}
    >>> q = grade_adjusted_quality(prof, beta=0.3)
    >>> # mean_grade_gp = 4.0, baseline 3.0, effect = 0.3 * 1 = 0.3
    >>> # raw 4.8 -> adjusted 4.5
    >>> round(q.adjusted_rating, 2)
    4.5
    >>> # A prof whose students got mixed grades (no correction needed)
    >>> prof = {"reviews": [
    ...     {"clarity_rating": 4.0, "helpful_rating": 4.0, "grade": g}
    ...     for g in ["A", "B", "B", "C"]
    ... ]}
    >>> q = grade_adjusted_quality(prof, beta=0.3)
    >>> # mean grade_gp = (4+3+3+2)/4 = 3.0 (at baseline), no adjustment
    >>> round(q.adjusted_rating, 2)
    4.0
    """
    ratings, gps = [], []
    for r in professor.get("reviews", []):
        rating = _rating_from_review(r)
        gp = _grade_gp(r.get("grade"))
        if rating is None or gp is None:
            continue
        ratings.append(rating)
        gps.append(gp)

    if len(ratings) < 3:
        return None

    mean_r = sum(ratings) / len(ratings)
    mean_g = sum(gps) / len(gps)
    adjusted = mean_r - beta * (mean_g - ADJUSTMENT_BASELINE_GP)
    # Clip to the 1–5 scale
    adjusted = max(1.0, min(5.0, adjusted))
    return AdjustedQuality(
        raw_mean=mean_r,
        adjusted_rating=adjusted,
        grade_inflation_effect=mean_r - adjusted,
        n_reviews_used=len(ratings),
        beta_used=beta,
    )


# ═════════════════════════════════════════════════════════════════════════════
# 2. Teaching-style attribute extraction
# ═════════════════════════════════════════════════════════════════════════════
#
# For each concrete teaching-style attribute students actually ask about, we
# maintain a keyword/regex list of phrases. We count reviews that mention any
# of the phrases ("hits"), divide by total reviews with comments, apply a weak
# Beta(1, 9) prior (a priori most attributes are absent from most classes),
# and report the posterior mean + a one-sided confidence tag.
#
# Each attribute's entry also carries a polarity hint: is detection of this
# attribute generally good for the student, bad, or neutral? Used by the UI
# to color-code without us having to duplicate the decision there.

# --- attribute name -> list of (regex, context_radius) ---
# All regexes are case-insensitive; \b word boundaries are important so
# "curve" doesn't match "curved" in the wrong context... actually we want
# "curved" too, so allow substring but be careful.

ATTRIBUTES = {
    "slides_online": {
        "label": "Slides / recordings available",
        "polarity": "good",
        "patterns": [
            r"\bposts?\s+(?:the\s+|his\s+|her\s+|their\s+)?(?:lecture|slide|notes?|recording)",
            r"\b(?:slides?|notes?|lectures?)\s+(?:are|were)\s+(?:online|posted|available|recorded|uploaded)",
            r"\b(?:slides?|notes?|lectures?)\s+(?:online|posted|available\s+online|recorded|uploaded)",
            r"\brecords?\s+(?:the\s+|his\s+|her\s+|their\s+|every\s+|all\s+)?lectures?\b",
            r"\blecture\s+(?:recordings?|videos?)\b",
            r"\brecorded\s+lectures?\b",
            r"\bpanopto\b",
            r"\bzoom recording\b",
        ],
    },
    # Attendance uses the structured RMP field on each review
    # (attendance_mandatory: 'mandatory' / 'non mandatory' / 'Y' / 'N'); the
    # regexes are only a fallback when no review carries the field.
    "attendance_mandatory": {
        "label": "Attendance mandatory",
        "polarity": "neutral",
        "structured": lambda r: {"mandatory": True, "y": True, "non mandatory": False, "n": False}.get(
            str(r.get("attendance_mandatory") or "").strip().lower()),
        "patterns": [
            r"\battendance\s+(?:is\s+)?(?:mandatory|required|matters|counts|graded)",
            r"\btakes\s+attendance\b",
            r"\bmust\s+(?:attend|be\s+there)",
            r"\battendance\s+policy\b",
            r"\bgraded\s+on\s+attendance\b",
        ],
    },
    "attendance_optional": {
        "label": "Attendance optional",
        "polarity": "good",
        "structured": lambda r: {"mandatory": False, "y": False, "non mandatory": True, "n": True}.get(
            str(r.get("attendance_mandatory") or "").strip().lower()),
        "patterns": [
            r"\b(?:didn'?t|don'?t|never)\s+(?:have\s+to\s+|need\s+to\s+)?(?:go\s+to\s+(?:class|lecture)|attend|show\s+up)",
            r"\bskip(?:ped|ping)?\s+(?:lecture|class)",
            r"\battendance\s+(?:is\s+|was\s+)?(?:not\s+required|optional|not\s+taken|not\s+mandatory)",
            r"\bno\s+attendance\b",
        ],
    },
    "multiple_choice": {
        "label": "Multiple-choice exams",
        "polarity": "good",
        "patterns": [
            r"\bmultiple[\s-]?choice\b",
            r"\bmc\s+(?:exam|test|quiz)",
            r"\bscantron\b",
        ],
    },
    "essay_exams": {
        "label": "Essay/free-response exams",
        "polarity": "neutral",
        "patterns": [
            r"\bessay\s+(?:exam|test|question|format|style)",
            r"\bfree[\s-]?response\b",
            r"\bshort[\s-]?answer\b",
            r"\bwriting[\s-]?intensive\b",
        ],
    },
    "open_book": {
        "label": "Open-note / take-home exams",
        "polarity": "good",
        "patterns": [
            r"\bopen\s+(?:book|note|notes)",
            r"\btake[\s-]?home\s+(?:exam|test|final|midterm)",
            r"\bcheat\s+sheet\b",
            r"\bformula\s+sheet\b",
        ],
    },
    "graded_on_curve": {
        "label": "Graded on a curve",
        "polarity": "good",
        # Negations ("no curve", "doesn't curve") are rejected by _negated().
        "patterns": [
            r"\bcurve[ds]?\b(?!\s*ball)",
            r"\bcurving\b",
            r"\bon\s+a\s+curve\b",
            r"\bgraded?\s+generously\b",
        ],
    },
    "group_projects": {
        "label": "Group projects / work",
        "polarity": "neutral",
        "patterns": [
            r"\bgroup\s+(?:project|work|assignment)",
            r"\bteam\s+(?:project|work|assignment)",
            r"\bpaired?\s+(?:project|assignment|work)",
        ],
    },
    "heavy_reading": {
        "label": "Heavy reading load",
        "polarity": "neutral",
        "patterns": [
            r"\blots?\s+of\s+reading",
            r"\ba\s+lot\s+of\s+reading",
            r"\breadings?\s+(?:are|is)\s+(?:heavy|long|dense)",
            r"\bheavy\s+readings?\b",
            r"\b\d{2,4}\s+pages?\s+(?:of\s+reading|(?:a|per|each|every)\s+(?:week|night|class))",
        ],
    },
    "problem_sets": {
        "label": "Regular problem sets",
        "polarity": "neutral",
        "patterns": [
            r"\bproblem\s+sets?\b",
            r"\bpset[s]?\b",
            r"\bweekly\s+homeworks?\b",
            r"\bproblem\s+solving\b",
        ],
    },
    "responsive_office_hours": {
        "label": "Responsive / office hours helpful",
        "polarity": "good",
        "patterns": [
            r"\b(?:quick|quickly|prompt|fast)\s+(?:respond|response|reply|replies)",
            r"\bresponds?\s+(?:quickly|promptly|to\s+emails?)",
            r"\bavailable\s+(?:in|during)\s+office\s+hours?",
            r"\boffice\s+hours?\s+(?:are\s+)?(?:helpful|great|useful|amazing)",
            r"\bvery\s+available\b",
        ],
    },
    "participation_graded": {
        "label": "Participation counts",
        "polarity": "neutral",
        "patterns": [
            r"\bparticipation\s+(?:is\s+|was\s+)?(?:graded|required|counts|matters|expected)",
            r"\bcold[\s-]?call(?:s|ed|ing)?\b",
            r"\bcalled\s+on\s+(?:in|during)\s+class\b",
            r"\bforced\s+to\s+(?:speak|participate)",
        ],
    },
}


# Precompile for speed
_COMPILED = {
    name: [re.compile(p, re.IGNORECASE) for p in spec["patterns"]]
    for name, spec in ATTRIBUTES.items()
}


@dataclass
class AttributeSignal:
    name: str
    label: str
    polarity: str
    hits: int
    n_reviews: int
    posterior_mean: float
    confidence: str   # "likely" | "probably" | "maybe" | "unsupported"

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "polarity": self.polarity,
            "hits": self.hits,
            "n_reviews": self.n_reviews,
            "posterior_mean": round(self.posterior_mean, 3),
            "confidence": self.confidence,
        }


# Beta(1, 9) prior: a priori most attributes are absent from most classes.
# Concentration 10 ≈ "we'd want to see a clear pattern before declaring the
# attribute present". This shrinks small-n signals toward 0.1 rather than 1.0.
_ATTR_PRIOR_ALPHA = 1.0
_ATTR_PRIOR_BETA = 9.0

_NEGATION = re.compile(
    r"\b(?:no|not|never|without|isn'?t|wasn'?t|doesn'?t|didn'?t|don'?t|won'?t|hardly|rarely)\b[^.!?]{0,20}$",
    re.IGNORECASE,
)


def _negated(text: str, start: int) -> bool:
    """True if a negation word appears within ~20 characters before `start`
    with no sentence boundary in between ("there is no curve", "doesn't curve").

    >>> _negated("there is no curve in this class", 12)
    True
    >>> _negated("he curves the final", 3)
    False
    """
    window = text[max(0, start - 30):start]
    return bool(_NEGATION.search(window))


def _pattern_hit(name: str, comment: str) -> bool:
    for p in _COMPILED[name]:
        m = p.search(comment)
        if m and not _negated(comment, m.start()):
            return True
    return False


def extract_teaching_attributes(reviews: list) -> list[AttributeSignal]:
    """
    For each attribute, count reviews that show it. Attributes with a
    `structured` extractor (attendance) read the review's structured RMP field
    when any review carries it; everything else scans the comment text with
    the attribute's regex list, rejecting negated mentions. One AttributeSignal
    per attribute with at least one hit.

    >>> reviews = [
    ...     {"comment": "Posts slides online and records lectures. Super helpful."},
    ...     {"comment": "Attendance is mandatory — she takes it every class."},
    ...     {"comment": "The exams are multiple choice which is nice."},
    ...     {"comment": "Great professor. Cares about students."},
    ... ]
    >>> sigs = extract_teaching_attributes(reviews)
    >>> names = {s.name for s in sigs}
    >>> "slides_online" in names
    True
    >>> "attendance_mandatory" in names
    True
    >>> "multiple_choice" in names
    True
    >>> # All three found; none for "group_projects" since we didn't mention it.
    >>> "group_projects" in names
    False
    >>> # Negations and near-misses do not count
    >>> sigs = extract_teaching_attributes([
    ...     {"comment": "There is no curve. The lectures are boring. He throws curve balls."},
    ...     {"comment": "Final paper of 10 pages. I didn't go over the notes much."},
    ... ])
    >>> {s.name for s in sigs} & {"graded_on_curve", "slides_online", "heavy_reading", "attendance_optional"}
    set()
    >>> # Structured attendance field wins over text
    >>> sigs = extract_teaching_attributes([
    ...     {"comment": "fine", "attendance_mandatory": "mandatory"},
    ...     {"comment": "fine", "attendance_mandatory": "mandatory"},
    ...     {"comment": "fine", "attendance_mandatory": "non mandatory"},
    ... ])
    >>> {s.name: s.hits for s in sigs}
    {'attendance_mandatory': 2, 'attendance_optional': 1}
    """
    # Gather just the comment strings, one per review (skip empty).
    comments = [(r.get("comment") or "") for r in reviews]
    comments = [c for c in comments if c.strip()]
    n_comments = len(comments)

    results = []
    for name, spec in ATTRIBUTES.items():
        hit_count = 0
        n = n_comments
        structured = spec.get("structured")
        if structured is not None:
            flags = [structured(r) for r in reviews]
            flags = [f for f in flags if f is not None]
            if flags:
                n = len(flags)
                hit_count = sum(1 for f in flags if f)
            elif n_comments:
                hit_count = sum(1 for c in comments if _pattern_hit(name, c))
        elif n_comments:
            hit_count = sum(1 for c in comments if _pattern_hit(name, c))
        if hit_count == 0 or n == 0:
            continue

        alpha = _ATTR_PRIOR_ALPHA + hit_count
        beta  = _ATTR_PRIOR_BETA + (n - hit_count)
        mean  = alpha / (alpha + beta)

        # Plain-English confidence tag: the posterior mean carries the
        # evidence; a floor on raw hits stops one mention from reading as
        # "likely" in a tiny sample.
        if (mean >= 0.4 and hit_count >= 2) or (hit_count >= 6 and mean >= 0.15):
            conf = "likely"
        elif (mean >= 0.2 and hit_count >= 2) or (hit_count >= 3 and mean >= 0.08):
            conf = "probably"
        else:
            conf = "maybe"

        results.append(AttributeSignal(
            name=name,
            label=spec["label"],
            polarity=spec["polarity"],
            hits=hit_count,
            n_reviews=n,
            posterior_mean=mean,
            confidence=conf,
        ))

    results.sort(key=lambda s: (-s.posterior_mean, -s.hits))
    return results


if __name__ == "__main__":
    import doctest
    failures, total = doctest.testmod(verbose=True)
    print(f"\n{failures} failures in {total} tests")
