"""
ProfInsight - FastAPI Backend (V2)
===================================
Multi-school REST API serving Bayesian ML analysis results.

Usage:
    uvicorn api:app --reload --port 8000
"""

import json
import os
import glob
import threading
import time as _time
import requests as _requests
from collections import defaultdict
from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional

from bayesian_calibration import (
    BetaPrior,
    posterior_from_counts,
    posterior_predictive_match,
    prob_a_gt_b_mc,
)
from bayesian_advanced import personal_grade_forecast
from datafiles import analyzed_path, list_analyzed, load_json, read_metadata, slug_from_analyzed

app = FastAPI(title="ProfInsight API", version="0.4.0")


# ─── Schedule index (current-term schedules by school) ──────────────────────
# Loaded at startup; refreshed when the file on disk changes (mtime check).
# Only schools with a scraped data/{slug}_schedule.json get a schedule; everything
# else returns an empty/None schedule payload, and the UI just doesn't render the
# "Teaching now" badge.
_SCHEDULE_CACHE: dict = {}
_SCHEDULE_MTIME: dict = {}


def _load_schedule(slug: str) -> Optional[dict]:
    path = os.path.join(DATA_DIR, f"{slug}_schedule.json")
    if not os.path.exists(path):
        return None
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None
    if _SCHEDULE_MTIME.get(slug) != mtime:
        with open(path) as f:
            _SCHEDULE_CACHE[slug] = json.load(f)
        _SCHEDULE_MTIME[slug] = mtime
    return _SCHEDULE_CACHE.get(slug)

# Self-ping to prevent Render free tier sleep
def _keep_alive():
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if not url:
        return
    while True:
        _time.sleep(600)
        try:
            _requests.get(f"{url}/api/health", timeout=10)
        except Exception:
            pass

_keep_alive_thread = threading.Thread(target=_keep_alive, daemon=True)
_keep_alive_thread.start()

# Rate Limiting
# Simple in-memory rate limiter: 60 requests per minute per IP

_rate_limits = {}
_rate_lock = threading.Lock()
RATE_LIMIT = 60
RATE_WINDOW = 60  # seconds

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Skip rate limiting for health checks
    if request.url.path in ("/api/health", "/"):
        return await call_next(request)

    # Behind Render/Cloudflare every request arrives from the proxy, so key on
    # the first X-Forwarded-For hop when present.
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() if forwarded else ((request.client.host if request.client else None) or "unknown")
    now = _time.time()

    with _rate_lock:
        if ip not in _rate_limits:
            _rate_limits[ip] = []
        # Clean old entries
        _rate_limits[ip] = [t for t in _rate_limits[ip] if now - t < RATE_WINDOW]
        if len(_rate_limits[ip]) >= RATE_LIMIT:
            return JSONResponse(
                status_code=429,
                content={"error": "Too many requests. Try again in a minute."}
            )
        _rate_limits[ip].append(now)
        # Drop idle clients so the table does not grow forever.
        if len(_rate_limits) > 5000:
            for stale in [k for k, v in _rate_limits.items() if not v or now - v[-1] > RATE_WINDOW]:
                del _rate_limits[stale]

    response = await call_next(request)

    # Add cache headers for browser/CDN caching
    if request.method == "GET" and response.status_code == 200:
        # Cache school list for 5 min, professor data for 1 hour
        if "/professors/" in request.url.path:
            response.headers["Cache-Control"] = "public, max-age=3600"
        elif "/schools" in request.url.path:
            response.headers["Cache-Control"] = "public, max-age=300"
        else:
            response.headers["Cache-Control"] = "public, max-age=600"

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Multi-School Data Loading

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_cache = {}
_schools_cache = None
_schools_cache_time = 0
SCHOOLS_CACHE_TTL = 300  # refresh school list every 5 min
# The largest analyzed files (BYU, UC Davis, UGA) are 15-20 MB on disk and
# several times that as Python objects; four resident schools fits the
# 512 MB Render free tier with room for request handling.
MAX_CACHED_SCHOOLS = int(os.environ.get("MAX_CACHED_SCHOOLS", "4"))
_cache_lock = threading.Lock()


def discover_schools() -> list:
    """Find all analyzed files (plain or gzipped). Cached for 5 minutes."""
    global _schools_cache, _schools_cache_time
    now = _time.time()
    if _schools_cache and (now - _schools_cache_time) < SCHOOLS_CACHE_TTL:
        return _schools_cache

    schools = []
    for filepath in list_analyzed(DATA_DIR):
        slug = slug_from_analyzed(filepath)
        try:
            meta = read_metadata(filepath)  # header only, not the whole file
            schools.append({
                "slug": slug,
                "name": meta.get("school_name", slug),
                "professors": meta.get("total_professors", 0),
                "reviews": meta.get("total_reviews", 0),
            })
        except Exception:
            # Fallback: just list the file
            schools.append({"slug": slug, "name": slug, "professors": 0, "reviews": 0})

    _schools_cache = schools
    _schools_cache_time = now
    return schools


def load_school(slug: str) -> dict:
    """Load a school's analyzed data. LRU cache with eviction; reloads when
    the file on disk changes (nightly refresh)."""
    filepath = analyzed_path(DATA_DIR, slug)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"School '{slug}' not found")
    mtime = os.path.getmtime(filepath)

    with _cache_lock:
        entry = _cache.get(slug)
        if entry is not None and entry[0] == mtime:
            # Move to front (most recently used)
            _cache[slug] = _cache.pop(slug)
            return entry[1]

    data = load_json(filepath)

    with _cache_lock:
        _cache.pop(slug, None)
        # Evict oldest if cache is full
        while len(_cache) >= MAX_CACHED_SCHOOLS:
            del _cache[next(iter(_cache))]
        _cache[slug] = (mtime, data)
    return data


def _headline_good(prof: dict) -> dict:
    """The one posterior every surface should agree on: the calibrated
    (empirical-Bayes) good-rating posterior, with the fixed Beta(2,2) block as
    a fallback for JSON produced before the calibration layer existed."""
    cal = prof.get("calibrated_analysis") or {}
    gr = cal.get("good_rating") if isinstance(cal, dict) else None
    if gr and gr.get("mean") is not None:
        return {"mean": gr.get("mean"), "ci_lower": gr.get("ci_lower"), "ci_upper": gr.get("ci_upper")}
    legacy = (prof.get("bayesian_analysis") or {}).get("rating_posteriors", {}).get("good", {}) or {}
    return {"mean": legacy.get("mean"), "ci_lower": legacy.get("ci_lower"), "ci_upper": legacy.get("ci_upper")}


def _course_key(name: str) -> str:
    """Normalize a course code for matching: 'EECS 281', 'eecs-281' -> 'EECS281'."""
    return "".join(ch for ch in (name or "").upper() if ch.isalnum())


def _course_matches(query: str, class_name: str) -> bool:
    """Exact match on normalized course codes. Substring containment produced
    cross-course hits (CS101 vs CS1010, MATH2 vs MATH215); reviewers write
    'ENG125' and 'ENGLISH125' for the same course, so a department-alias miss
    is accepted over a false positive."""
    q, c = _course_key(query), _course_key(class_name)
    return bool(q) and q == c


def get_default_slug() -> str:
    """Get the first available school slug."""
    schools = discover_schools()
    return schools[0]["slug"] if schools else "umich"


# Endpoints

@app.get("/")
def root():
    schools = discover_schools()
    return {"service": "ProfInsight API v2", "schools": len(schools)}


@app.get("/api/health")
def health():
    """Health check endpoint for keep-alive pings."""
    return {"status": "ok"}


@app.get("/api/schools")
def list_schools():
    """List all available schools."""
    return {"schools": discover_schools()}


@app.get("/api/{school}/professors")
def list_professors(
    school: str,
    department: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("rating"),
    limit: int = Query(200, ge=1, le=500),
):
    """List professors with student-friendly summary data."""
    data = load_school(school)
    profs = data.get("analysis", [])

    if department:
        d = department.lower()
        profs = [p for p in profs if d in p.get("department", "").lower()]

    if search:
        s = search.lower()
        profs = [p for p in profs if s in p.get("name", "").lower() or s in p.get("department", "").lower()]

    sort_keys = {
        "rating": lambda p: p.get("summary", {}).get("avg_rating") or 0,
        "difficulty": lambda p: p.get("summary", {}).get("avg_difficulty") or 0,
        "num_ratings": lambda p: p.get("summary", {}).get("num_ratings") or 0,
        "name": lambda p: p.get("name", ""),
    }
    sort_fn = sort_keys.get(sort_by, sort_keys["rating"])
    profs = sorted(profs, key=sort_fn, reverse=(sort_by != "name"))

    results = []
    for p in profs[:limit]:
        good_post = _headline_good(p)
        results.append({
            "id": p.get("professor_id"),
            "legacy_id": p.get("legacy_id"),
            "name": p.get("name"),
            "department": p.get("department"),
            "avg_rating": p.get("summary", {}).get("avg_rating"),
            "avg_difficulty": p.get("summary", {}).get("avg_difficulty"),
            "num_ratings": p.get("summary", {}).get("num_ratings"),
            "would_take_again_pct": p.get("summary", {}).get("would_take_again_pct"),
            "verdict": p.get("verdict", ""),
            "verdict_emoji": p.get("verdict_emoji", ""),
            "confidence_level": p.get("confidence_level", ""),
            "trend_summary": p.get("trend_summary", ""),
            "grade_probabilities": p.get("grade_probabilities", {}),
            "bayesian_good_prob": good_post.get("mean"),
            "bayesian_ci_lower": good_post.get("ci_lower"),
            "bayesian_ci_upper": good_post.get("ci_upper"),
            "top_tags": p.get("top_tags", [])[:5],
        })

    return {"count": len(results), "professors": results}


@app.get("/api/{school}/professors/{professor_id}")
def get_professor(school: str, professor_id: str):
    """Full analysis for a single professor, enriched with schedule data
    when this school has a scraped current-term schedule."""
    data = load_school(school)
    for p in data.get("analysis", []):
        if p.get("professor_id") == professor_id:
            # Attach schedule data if available for this school.
            sched = _load_schedule(school)
            if sched:
                teaching_map = sched.get("teaching_now_by_prof", {}) or {}
                courses = teaching_map.get(professor_id, [])
                p = {**p, "teaching_now": {
                    "term": sched.get("term"),
                    "term_label": sched.get("term_label"),
                    "courses": courses,
                    "n_courses": len(courses),
                }}
            return p
    raise HTTPException(status_code=404, detail="Professor not found")


@app.get("/api/{school}/teaching_now/{course_code}")
def teaching_now(school: str, course_code: str):
    """Given a course code (e.g. 'HIST200'), return the professors teaching it
    this term *with their ratings joined in*. The binding-agent endpoint that
    turns ProfInsight from a lookup into a registration-time decision tool."""
    sched = _load_schedule(school)
    if not sched:
        raise HTTPException(status_code=404,
                            detail=f"No schedule available for {school} yet.")
    course_code = course_code.strip().upper()
    sections = sched.get("courses", {}).get(course_code, [])
    if not sections:
        raise HTTPException(status_code=404,
                            detail=f"No sections found for {course_code} in {sched.get('term_label')}.")

    profs_list = load_school(school).get("analysis", [])
    prof_by_id = {p.get("professor_id"): p for p in profs_list}

    per_prof: dict = {}
    tba_sections = 0
    for s in sections:
        pids = s.get("matched_professor_ids") or []
        if not pids and not s.get("instructors"):
            tba_sections += 1
        # Instructors without an RMP record are listed by name, including
        # co-instructors of sections that also have a matched professor.
        unmatched_names = s.get("unmatched_instructors")
        if unmatched_names is None:  # schedule JSON from before this field existed
            unmatched_names = [] if pids else (s.get("instructors") or [])
        for name in unmatched_names:
            per_prof.setdefault(("unmatched", name), {
                "matched": False,
                "instructor_name": name,
                "sections": [],
            })["sections"].append(s)
        for pid in pids:
            key = ("matched", pid)
            if key not in per_prof:
                prof = prof_by_id.get(pid) or {}
                per_prof[key] = {
                    "matched": True,
                    "professor_id": pid,
                    "name": prof.get("name"),
                    "department": prof.get("department"),
                    "avg_rating": prof.get("summary", {}).get("avg_rating"),
                    "avg_difficulty": prof.get("summary", {}).get("avg_difficulty"),
                    "num_ratings": prof.get("summary", {}).get("num_ratings"),
                    "verdict": prof.get("verdict"),
                    "bayesian_good_prob": _headline_good(prof).get("mean"),
                    "sections": [],
                }
            per_prof[key]["sections"].append(s)

    # Sort matched first (by rating desc), then unmatched
    matched = [v for k, v in per_prof.items() if k[0] == "matched"]
    unmatched = [v for k, v in per_prof.items() if k[0] == "unmatched"]
    matched.sort(key=lambda v: -(v.get("avg_rating") or 0))

    return {
        "school": school,
        "course_code": course_code,
        "term": sched.get("term"),
        "term_label": sched.get("term_label"),
        "n_sections": len(sections),
        "n_sections_tba": tba_sections,
        "matched": matched,
        "unmatched": unmatched,
    }


@app.get("/api/{school}/schedule_status")
def schedule_status(school: str):
    """Whether this school has scraped schedule data, and how much coverage."""
    sched = _load_schedule(school)
    if not sched:
        return {"school": school, "available": False}
    stats = sched.get("match_stats", {})
    return {
        "school": school,
        "available": True,
        "term": sched.get("term"),
        "term_label": sched.get("term_label"),
        "scraped_at": sched.get("scraped_at"),
        "n_courses": sched.get("n_courses"),
        "n_sections": sched.get("n_sections"),
        # Units differ on purpose: assignments are per section-instructor pair,
        # the unmatched figure counts distinct instructor names.
        "matched_instructor_assignments": stats.get("matched_instructor_assignments", 0),
        "distinct_profs_teaching": stats.get("distinct_profs_teaching", 0),
        "n_unmatched_instructor_names": stats.get("n_unmatched_total", 0),
    }


@app.get("/api/{school}/departments")
def list_departments(school: str):
    """List departments with counts."""
    profs = load_school(school).get("analysis", [])
    dept_counts = {}
    for p in profs:
        dept = p.get("department", "Unknown")
        if dept not in dept_counts:
            dept_counts[dept] = {"name": dept, "count": 0, "ratings": []}
        dept_counts[dept]["count"] += 1
        r = p.get("summary", {}).get("avg_rating")
        if r:
            dept_counts[dept]["ratings"].append(r)

    results = []
    for dept, info in dept_counts.items():
        results.append({
            "name": info["name"],
            "professor_count": info["count"],
            "avg_rating": round(sum(info["ratings"]) / len(info["ratings"]), 2) if info["ratings"] else None,
        })
    results.sort(key=lambda x: x["professor_count"], reverse=True)
    return {"departments": results}


@app.get("/api/{school}/stats")
def global_stats(school: str):
    """School-wide statistics."""
    data = load_school(school)
    profs = data.get("analysis", [])
    meta = data.get("metadata", {})

    all_ratings = [p["summary"]["avg_rating"] for p in profs if p.get("summary", {}).get("avg_rating")]
    all_diff = [p["summary"]["avg_difficulty"] for p in profs if p.get("summary", {}).get("avg_difficulty")]

    return {
        "school": meta.get("school_name"),
        "total_professors": len(profs),
        "total_reviews": meta.get("total_reviews", 0),
        "avg_rating": round(sum(all_ratings) / len(all_ratings), 2) if all_ratings else None,
        "avg_difficulty": round(sum(all_diff) / len(all_diff), 2) if all_diff else None,
        "departments": len(set(p.get("department") for p in profs)),
    }


@app.get("/api/{school}/compare")
def compare_professors(school: str, ids: str = Query(...)):
    """Compare professors side by side."""
    id_list = [i.strip() for i in ids.split(",")]
    profs = load_school(school).get("analysis", [])
    results = [p for p in profs if p.get("professor_id") in id_list]
    if not results:
        raise HTTPException(status_code=404, detail="No professors found")
    return {"professors": results}


def _calibrated_good_params(prof: dict) -> Optional[tuple[float, float]]:
    """Pull (alpha, beta) out of the calibrated_analysis block, with a fallback
    to the legacy bayesian_analysis Beta posterior for pre-calibration JSON."""
    cal = prof.get("calibrated_analysis") or {}
    gr = cal.get("good_rating") if isinstance(cal, dict) else None
    if gr and gr.get("alpha") is not None and gr.get("beta") is not None:
        return float(gr["alpha"]), float(gr["beta"])
    # Legacy fallback
    good = (prof.get("bayesian_analysis") or {}).get("rating_posteriors", {}).get("good", {})
    if good.get("alpha") is not None and good.get("beta") is not None:
        return float(good["alpha"]), float(good["beta"])
    return None


def _calibrated_wta_params(prof: dict) -> Optional[tuple[float, float]]:
    cal = prof.get("calibrated_analysis") or {}
    wta = cal.get("take_again") if isinstance(cal, dict) else None
    if wta and wta.get("alpha") is not None and wta.get("beta") is not None:
        return float(wta["alpha"]), float(wta["beta"])
    legacy = (prof.get("bayesian_analysis") or {}).get("would_take_again_posterior")
    if legacy and legacy.get("alpha") is not None and legacy.get("beta") is not None:
        return float(legacy["alpha"]), float(legacy["beta"])
    return None


@app.get("/api/{school}/head_to_head")
def head_to_head(school: str, a: str = Query(...), b: str = Query(...)):
    """
    Bayesian head-to-head comparison of two professors.

    Returns P(A > B) on each comparable posterior (overall "good" rating,
    "would take again") computed by Monte Carlo from the Beta posteriors
    stored in `calibrated_analysis`. This reframes CompareMode from
    "here are two averages, squint and decide" to a direct probability
    statement (e.g. "83% chance Prof A is rated more highly"), which
    collapses sample-size asymmetries automatically — two profs with the
    same mean but 10× different review counts won't tie.
    """
    profs = load_school(school).get("analysis", [])
    prof_a = next((p for p in profs if p.get("professor_id") == a), None)
    prof_b = next((p for p in profs if p.get("professor_id") == b), None)
    if prof_a is None or prof_b is None:
        raise HTTPException(status_code=404, detail="One or both professors not found")

    comparisons: dict = {}

    pg_a, pg_b = _calibrated_good_params(prof_a), _calibrated_good_params(prof_b)
    if pg_a and pg_b:
        p = prob_a_gt_b_mc(pg_a[0], pg_a[1], pg_b[0], pg_b[1], n_samples=6000, seed=42)
        comparisons["overall_good_rating"] = {
            "p_a_gt_b": round(p, 4),
            "a_posterior": {"alpha": pg_a[0], "beta": pg_a[1]},
            "b_posterior": {"alpha": pg_b[0], "beta": pg_b[1]},
            "verdict": _verdict_from_p(p, prof_a.get("name"), prof_b.get("name"), "overall rating"),
        }

    pw_a, pw_b = _calibrated_wta_params(prof_a), _calibrated_wta_params(prof_b)
    if pw_a and pw_b:
        p = prob_a_gt_b_mc(pw_a[0], pw_a[1], pw_b[0], pw_b[1], n_samples=6000, seed=43)
        comparisons["would_take_again"] = {
            "p_a_gt_b": round(p, 4),
            "a_posterior": {"alpha": pw_a[0], "beta": pw_a[1]},
            "b_posterior": {"alpha": pw_b[0], "beta": pw_b[1]},
            "verdict": _verdict_from_p(p, prof_a.get("name"), prof_b.get("name"), "would-take-again"),
        }

    if not comparisons:
        raise HTTPException(
            status_code=409,
            detail="Calibrated posteriors unavailable for these professors. Re-run the pipeline.",
        )

    return {
        "a": {"id": prof_a.get("professor_id"), "name": prof_a.get("name"),
              "department": prof_a.get("department")},
        "b": {"id": prof_b.get("professor_id"), "name": prof_b.get("name"),
              "department": prof_b.get("department")},
        "comparisons": comparisons,
    }


@app.get("/api/{school}/forecast/{professor_id}")
def personalized_forecast(
    school: str,
    professor_id: str,
    gpa: Optional[float] = Query(None, ge=0.0, le=4.0,
                                 description="Your cumulative GPA, 0–4. Omit for the base-rate forecast."),
):
    """
    Personal grade forecast.

    Takes the professor's historical grade distribution as the prior and updates
    with the student's GPA via a Gaussian likelihood, returning a posterior over
    letter-grade buckets plus an expected GPA with a 95% credible interval.
    Without a `gpa` param the response is the base-rate forecast.
    """
    profs = load_school(school).get("analysis", [])
    prof = next((p for p in profs if p.get("professor_id") == professor_id), None)
    if prof is None:
        raise HTTPException(status_code=404, detail="Professor not found")

    grade_probs = prof.get("grade_probabilities") or {}
    if not grade_probs or not any(grade_probs.values()):
        raise HTTPException(
            status_code=409,
            detail="This professor doesn't have enough self-reported grade data for a forecast.",
        )

    n_reviews = int(sum(prof.get("grade_distribution", {}).values()))
    forecast = personal_grade_forecast(grade_probs, student_gpa=gpa, n_reviews=n_reviews)
    return {
        "professor": {"id": prof.get("professor_id"), "name": prof.get("name"),
                      "department": prof.get("department")},
        "forecast": forecast.as_dict(),
        "explanation": _forecast_explanation(forecast, prof.get("name"), gpa),
    }


def _forecast_explanation(forecast, prof_name: str, gpa: Optional[float]) -> str:
    """One-sentence explanation the UI shows verbatim."""
    eg = forecast.expected_gpa
    grade = forecast.most_likely.replace(" range", "")
    if gpa is None:
        return (f"Looking at {prof_name}'s past grades, the most common outcome is "
                f"around a {grade} (average GPA {eg:.2f}).")
    pct = forecast.posterior_pct.get(forecast.most_likely, 0)
    return (f"With a {gpa:.2f} GPA, you're most likely to land in the {grade} range "
            f"with {prof_name} (about {pct:.0f}% probability). Expected GPA in this "
            f"class: {eg:.2f} (usually {forecast.ci_lower:.2f}–{forecast.ci_upper:.2f}).")


def _verdict_from_p(p: float, a_name: str, b_name: str, what: str) -> str:
    """Human-readable head-to-head sentence for a win probability `p = P(A > B)`."""
    if p >= 0.95:
        return f"Students clearly rate {a_name} higher on {what}."
    if p >= 0.80:
        return f"{a_name} usually comes out ahead on {what}."
    if p >= 0.60:
        return f"{a_name} has a slight edge on {what}."
    if p >= 0.40:
        return f"Pretty much a toss-up on {what}."
    if p >= 0.20:
        return f"{b_name} has a slight edge on {what}."
    if p >= 0.05:
        return f"{b_name} usually comes out ahead on {what}."
    return f"Students clearly rate {b_name} higher on {what}."


@app.get("/api/{school}/fit")
def fit_quiz(
    school: str,
    difficulty: int = Query(3, ge=1, le=5, description="1=easy, 5=bring it on"),
    grading: int = Query(3, ge=1, le=5, description="1=lenient please, 5=fair is fine"),
    lectures: int = Query(3, ge=1, le=5, description="1=don't care, 5=must be great"),
    approachability: int = Query(3, ge=1, le=5, description="1=don't need, 5=very important"),
    workload: int = Query(3, ge=1, le=5, description="1=light, 5=heavy is fine"),
    department: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Student fit quiz - rank professors by how well they match preferences.

    The fit score is computed as a weighted match between student preferences
    and the professor's Bayesian-analyzed profile:

    - difficulty pref vs actual difficulty rating
    - grading pref vs grading sentiment
    - lectures pref vs lecture sentiment
    - approachability pref vs approachability sentiment
    - workload pref vs workload sentiment

    Returns professors sorted by fit score (0-100).
    """
    data = load_school(school)
    profs = data.get("analysis", [])

    if department:
        d = department.lower()
        profs = [p for p in profs if d in p.get("department", "").lower()]

    scored = []
    for p in profs:
        summary = p.get("summary", {})
        sentiment = p.get("category_sentiment", {})
        num_ratings = summary.get("num_ratings", 0)
        if num_ratings < 3:
            continue

        # --- Compute fit score ---
        score = 0
        weights_total = 0

        # 1. Difficulty match
        #    Student pref 1 = wants easy (low diff), 5 = wants challenge (high diff)
        #    Prof difficulty is 1-5 scale
        actual_diff = summary.get("avg_difficulty", 3.0) or 3.0
        if difficulty <= 2:
            # Wants easy: lower diff = better
            diff_score = max(0, (5 - actual_diff) / 4) * 100
        elif difficulty >= 4:
            # Wants challenge: higher diff = better (but not punishing 5.0)
            diff_score = max(0, actual_diff / 5) * 100
        else:
            # Neutral: slight preference for moderate
            diff_score = max(0, (1 - abs(actual_diff - 3.0) / 2)) * 100
        weight = 2.0
        score += diff_score * weight
        weights_total += weight

        # 2-5. Sentiment category matches
        # Posterior-predictive moderation (Lecture 8 pp.3–4): for each category,
        # convert (n_reviews, pct_positive) -> (successes, n) -> Beta posterior
        # with a weak prior, and use the posterior mean instead of the raw MLE.
        # A category with 2 reviews at 100% positive now scores ~75 instead of
        # 100, automatically preventing confidently-wrong fit scores on thin n.
        pref_map = {
            "grading": grading,
            "lectures": lectures,
            "approachability": approachability,
            "workload": workload,
        }
        FIT_PRIOR = BetaPrior(2.0, 2.0, source="fit_weak_prior")
        per_category_posteriors = {}  # for returning explainers
        for cat, pref_val in pref_map.items():
            cat_data = sentiment.get(cat, {})
            pct_positive = cat_data.get("pct_positive")
            n_cat = cat_data.get("n_reviews") or 0
            if pct_positive is None:
                continue

            if n_cat > 0:
                successes = max(0, min(n_cat, round(pct_positive / 100.0 * n_cat)))
                post = posterior_from_counts(successes, n_cat, FIT_PRIOR)
                moderated_pct = post.mean * 100
                ci_lo, ci_hi = post.credible_interval(0.95)
                per_category_posteriors[cat] = {
                    "n_reviews": n_cat,
                    "raw_pct_positive": pct_positive,
                    "posterior_pct": round(moderated_pct, 1),
                    "ci_lower_pct": round(ci_lo * 100, 1),
                    "ci_upper_pct": round(ci_hi * 100, 1),
                }
            else:
                moderated_pct = pct_positive

            cat_score = moderated_pct  # 0-100

            # If student says "very important" (4-5), weight this category more
            # and penalize low scores harder
            if pref_val >= 4:
                weight = 2.5
                # Penalize if below 50%
                if cat_score < 50:
                    cat_score *= 0.6
            elif pref_val <= 2:
                weight = 0.5  # Don't care much
            else:
                weight = 1.5

            score += cat_score * weight
            weights_total += weight

        # 3. Bonus: overall quality
        avg_rating = summary.get("avg_rating", 3.0) or 3.0
        quality_score = (avg_rating / 5.0) * 100
        weight = 1.5
        score += quality_score * weight
        weights_total += weight

        # 4. Bonus: would take again
        wta = summary.get("would_take_again_pct")
        if wta is not None and wta >= 0:
            weight = 1.0
            score += wta * weight
            weights_total += weight

        # Normalize to 0-100
        fit_score = round(score / weights_total, 1) if weights_total > 0 else 50.0

        # The per-dimension Beta-moderation above already does most of the
        # shrinkage work, but we keep a small total-review-count floor penalty
        # to avoid very-thin-data profs dominating the top of the list.
        if num_ratings < 10:
            fit_score = round(fit_score * 0.85, 1)  # 15% penalty
        elif num_ratings < 20:
            fit_score = round(fit_score * 0.92, 1)  # 8% penalty

        # Credible band on the fit score, by propagating variance across the
        # per-dimension Beta posteriors. Gives the UI an honest +/- instead
        # of just a point estimate.
        def _weight_for(pref):
            return 2.5 if pref >= 4 else (0.5 if pref <= 2 else 1.5)
        w_map = {cat: _weight_for(pref_map[cat]) for cat in pref_map}
        components = []
        for cat, pref_val in pref_map.items():
            info = per_category_posteriors.get(cat)
            if not info:
                continue
            successes = max(0, min(info["n_reviews"], round(info["raw_pct_positive"] / 100.0 * info["n_reviews"])))
            post = posterior_from_counts(successes, info["n_reviews"], FIT_PRIOR)
            components.append((cat, w_map[cat], post))
        match = posterior_predictive_match(components) if components else None

        # Build match reasons
        reasons = []
        if difficulty <= 2 and actual_diff <= 2.5:
            reasons.append("Low difficulty matches your preference")
        elif difficulty >= 4 and actual_diff >= 3.5:
            reasons.append("Challenging, as you prefer")
        lec = sentiment.get("lectures", {}).get("pct_positive")
        if lectures >= 4 and lec and lec >= 70:
            reasons.append(f"Strong lectures ({lec:.0f}% positive)")
        elif lectures >= 4 and lec and lec < 40:
            reasons.append(f"Lectures may not match your expectations ({lec:.0f}% positive)")
        appr = sentiment.get("approachability", {}).get("pct_positive")
        if approachability >= 4 and appr and appr >= 70:
            reasons.append(f"Highly approachable ({appr:.0f}% positive)")
        grade_probs = p.get("grade_probabilities", {})
        a_pct = grade_probs.get("A range", 0)
        if grading >= 4 and a_pct >= 70:
            reasons.append(f"{a_pct:.0f}% of reported grades in the A range")

        good_post = _headline_good(p)

        scored.append({
            "id": p.get("professor_id"),
            "name": p.get("name"),
            "department": p.get("department"),
            "fit_score": fit_score,
            "fit_reasons": reasons[:3],
            "verdict": p.get("verdict", ""),
            "verdict_emoji": p.get("verdict_emoji", ""),
            "avg_rating": summary.get("avg_rating"),
            "avg_difficulty": summary.get("avg_difficulty"),
            "num_ratings": num_ratings,
            "would_take_again_pct": summary.get("would_take_again_pct"),
            "grade_probabilities": grade_probs,
            "bayesian_good_prob": good_post.get("mean"),
            "confidence_level": p.get("confidence_level", ""),
            # Posterior-predictive match with credible band
            "match_posterior": match.as_dict() if match else None,
            "category_posteriors": per_category_posteriors,
        })

    scored.sort(key=lambda x: -x["fit_score"])
    return {"count": len(scored[:limit]), "preferences": {
        "difficulty": difficulty, "grading": grading,
        "lectures": lectures, "approachability": approachability,
        "workload": workload,
    }, "results": scored[:limit]}


@app.get("/api/{school}/courses")
def list_courses(school: str, search: Optional[str] = Query(None)):
    """List all courses with professor counts."""
    profs = load_school(school).get("analysis", [])
    course_map = {}
    for p in profs:
        for c in p.get("class_breakdown", []):
            name = c.get("class_name", "").strip().upper()
            if not name:
                continue
            if name not in course_map:
                course_map[name] = {"name": name, "professors": [], "total_reviews": 0}
            course_map[name]["professors"].append(p.get("name"))
            course_map[name]["total_reviews"] += c.get("num_reviews", 0)

    courses = list(course_map.values())
    if search:
        s = search.upper()
        courses = [c for c in courses if s in c["name"]]

    courses.sort(key=lambda x: -x["total_reviews"])
    return {"courses": courses[:100]}


@app.get("/api/{school}/schedule")
def schedule_helper(school: str, courses: str = Query(..., description="Comma-separated course codes")):
    """
    Schedule helper - given a list of courses, return the best professor
    options for each course with their full analysis.
    """
    course_list = [c.strip().upper() for c in courses.split(",") if c.strip()]
    profs = load_school(school).get("analysis", [])

    results = {}
    for course_code in course_list:
        results[course_code] = []
        for p in profs:
            for c in p.get("class_breakdown", []):
                cname = c.get("class_name", "").strip().upper()
                if _course_matches(course_code, cname):
                    good_post = _headline_good(p)
                    results[course_code].append({
                        "id": p.get("professor_id"),
                        "name": p.get("name"),
                        "department": p.get("department"),
                        "verdict": p.get("verdict", ""),
                        "verdict_emoji": p.get("verdict_emoji", ""),
                        "confidence_level": p.get("confidence_level", ""),
                        "avg_rating": p.get("summary", {}).get("avg_rating"),
                        "avg_difficulty": p.get("summary", {}).get("avg_difficulty"),
                        "would_take_again_pct": p.get("summary", {}).get("would_take_again_pct"),
                        "bayesian_good_prob": good_post.get("mean"),
                        "grade_probabilities": p.get("grade_probabilities", {}),
                        "course_specific": {
                            "avg_rating": c.get("avg_rating"),
                            "num_reviews": c.get("num_reviews"),
                            "grades": c.get("grades", {}),
                        },
                    })

        # Sort by course-specific rating first, then overall
        results[course_code].sort(
            key=lambda x: (x["course_specific"].get("avg_rating") or x.get("avg_rating") or 0),
            reverse=True,
        )

    return {"courses": course_list, "results": results}


@app.get("/api/{school}/optimize")
def optimize_semester(
    school: str,
    courses: str = Query(..., description="Comma-separated course codes"),
    preference: str = Query("balanced", description="balanced, easy, or challenge"),
):
    """
    Semester optimizer - finds the best professor combination across all courses
    and predicts overall semester difficulty and estimated GPA.
    """
    course_list = [c.strip().upper() for c in courses.split(",") if c.strip()]
    profs = load_school(school).get("analysis", [])

    # Build candidate professors for each course
    course_candidates = {}
    for course_code in course_list:
        candidates = []
        for p in profs:
            for c in p.get("class_breakdown", []):
                cname = c.get("class_name", "").strip().upper()
                if _course_matches(course_code, cname):
                    summary = p.get("summary", {})
                    good_post = _headline_good(p)
                    grade_probs = p.get("grade_probabilities", {})

                    # Compute a composite score based on preference
                    rating = summary.get("avg_rating") or 3.0
                    difficulty = summary.get("avg_difficulty") or 3.0
                    good_prob = good_post.get("mean") if good_post.get("mean") is not None else 0.5
                    wta = summary.get("would_take_again_pct")
                    # 0% would-take-again is a real (bad) signal; only a missing
                    # value (None or RMP's -1) falls back to the neutral 0.5.
                    wta_score = (wta / 100) if (wta is not None and wta >= 0) else 0.5
                    has_grades = any(grade_probs.values()) if grade_probs else False
                    a_pct = (grade_probs.get("A range", 0) / 100) if has_grades else 0.3

                    if preference == "easy":
                        score = (rating / 5) * 0.2 + (1 - difficulty / 5) * 0.35 + a_pct * 0.25 + wta_score * 0.2
                    elif preference == "challenge":
                        score = (rating / 5) * 0.4 + good_prob * 0.3 + wta_score * 0.2 + (difficulty / 5) * 0.1
                    else:  # balanced
                        score = (rating / 5) * 0.3 + good_prob * 0.25 + a_pct * 0.2 + wta_score * 0.15 + (1 - difficulty / 5) * 0.1

                    # Confidence penalty for few reviews
                    n_reviews = c.get("num_reviews", 0)
                    if n_reviews < 5:
                        score *= 0.8
                    elif n_reviews < 10:
                        score *= 0.9

                    candidates.append({
                        "id": p.get("professor_id"),
                        "name": p.get("name"),
                        "department": p.get("department"),
                        "verdict": p.get("verdict", ""),
                        "verdict_emoji": p.get("verdict_emoji", ""),
                        "avg_rating": rating,
                        "avg_difficulty": difficulty,
                        "would_take_again_pct": wta,
                        "bayesian_good_prob": good_prob,
                        "grade_probabilities": grade_probs,
                        "course_rating": c.get("avg_rating"),
                        "course_reviews": c.get("num_reviews", 0),
                        "course_grades": c.get("grades", {}),
                        "optimizer_score": round(score, 4),
                    })

        candidates.sort(key=lambda x: -x["optimizer_score"])
        course_candidates[course_code] = candidates

    # Pick the best professor for each course (the "recommended" schedule)
    recommended = {}
    warnings = []
    for course_code, candidates in course_candidates.items():
        if candidates:
            best = candidates[0]
            recommended[course_code] = best
            # Generate warnings
            if best["avg_difficulty"] >= 4.0:
                warnings.append(f"{course_code}: {best['name']} is rated very difficult ({best['avg_difficulty']:.1f}/5)")
            if best.get("would_take_again_pct") is not None and 0 <= best["would_take_again_pct"] < 40:
                warnings.append(f"{course_code}: Only {best['would_take_again_pct']:.0f}% would retake with {best['name']}")
            if best["bayesian_good_prob"] < 0.4:
                warnings.append(f"{course_code}: {best['name']} has low confidence rating - consider alternatives")
        else:
            recommended[course_code] = None
            warnings.append(f"{course_code}: No professor data found")

    # Compute semester-level predictions
    rec_profs = [v for v in recommended.values() if v]
    if rec_profs:
        avg_difficulty = sum(p["avg_difficulty"] for p in rec_profs) / len(rec_profs)
        avg_rating = sum(p["avg_rating"] for p in rec_profs) / len(rec_profs)

        # Estimated GPA from grade probabilities
        gpa_map = {"A range": 3.8, "B range": 3.0, "C range": 2.0, "D/F": 0.8}
        gpa_estimates = []
        for p in rec_profs:
            gp = p.get("grade_probabilities", {})
            if any(gp.values()):
                est = sum(gpa_map.get(k, 2.5) * (v / 100) for k, v in gp.items() if v)
                gpa_estimates.append(est)
        est_gpa = round(sum(gpa_estimates) / len(gpa_estimates), 2) if gpa_estimates else None

        # Semester difficulty label
        if avg_difficulty >= 4.0:
            difficulty_label = "Very heavy semester"
        elif avg_difficulty >= 3.5:
            difficulty_label = "Challenging semester"
        elif avg_difficulty >= 2.5:
            difficulty_label = "Manageable semester"
        else:
            difficulty_label = "Light semester"
    else:
        avg_difficulty = None
        avg_rating = None
        est_gpa = None
        difficulty_label = "Not enough data"

    return {
        "courses": course_list,
        "preference": preference,
        "recommended": recommended,
        "alternatives": {k: v[1:4] for k, v in course_candidates.items() if len(v) > 1},
        "semester_prediction": {
            "avg_difficulty": round(avg_difficulty, 2) if avg_difficulty else None,
            "avg_quality": round(avg_rating, 2) if avg_rating else None,
            "estimated_gpa": est_gpa,
            "difficulty_label": difficulty_label,
            "num_courses": len(course_list),
            "courses_with_data": len(rec_profs),
        },
        "warnings": warnings,
    }
