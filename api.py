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

app = FastAPI(title="ProfInsight API", version="0.3.0")

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

    ip = request.client.host or "unknown"
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
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:5173", "https://*.vercel.app"],
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
MAX_CACHED_SCHOOLS = 10  # only keep 10 schools in memory at once


def discover_schools() -> list:
    """Find all analyzed JSON files. Cached for 5 minutes."""
    global _schools_cache, _schools_cache_time
    now = _time.time()
    if _schools_cache and (now - _schools_cache_time) < SCHOOLS_CACHE_TTL:
        return _schools_cache

    schools = []
    pattern = os.path.join(DATA_DIR, "*_analyzed.json")
    for filepath in sorted(glob.glob(pattern)):
        try:
            # Only read metadata, not the full file
            with open(filepath, "r") as f:
                # Read just enough to get metadata (first ~2000 chars)
                raw = f.read(5000)
                # Find metadata section
                meta_start = raw.find('"metadata"')
                if meta_start == -1:
                    continue
                # Quick parse just the metadata
                data = json.loads(raw[:raw.find('"analysis"')] + '"analysis": []}')
                meta = data.get("metadata", {})

            slug = os.path.basename(filepath).replace("_analyzed.json", "")
            schools.append({
                "slug": slug,
                "name": meta.get("school_name", slug),
                "professors": meta.get("total_professors", 0),
                "reviews": meta.get("total_reviews", 0),
            })
        except Exception:
            # Fallback: just list the file
            slug = os.path.basename(filepath).replace("_analyzed.json", "")
            schools.append({"slug": slug, "name": slug, "professors": 0, "reviews": 0})

    _schools_cache = schools
    _schools_cache_time = now
    return schools


def load_school(slug: str) -> dict:
    """Load a school's analyzed data. LRU cache with eviction."""
    if slug in _cache:
        # Move to front (most recently used)
        _cache[slug] = _cache.pop(slug)
        return _cache[slug]

    filepath = os.path.join(DATA_DIR, f"{slug}_analyzed.json")
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"School '{slug}' not found")

    with open(filepath, "r") as f:
        data = json.load(f)

    # Evict oldest if cache is full
    if len(_cache) >= MAX_CACHED_SCHOOLS:
        oldest = next(iter(_cache))
        del _cache[oldest]

    _cache[slug] = data
    return data


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
        bayesian = p.get("bayesian_analysis", {})
        good_post = bayesian.get("rating_posteriors", {}).get("good", {})
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
    """Full analysis for a single professor."""
    data = load_school(school)
    for p in data.get("analysis", []):
        if p.get("professor_id") == professor_id:
            return p
    raise HTTPException(status_code=404, detail="Professor not found")


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
        pref_map = {
            "grading": grading,
            "lectures": lectures,
            "approachability": approachability,
            "workload": workload,
        }
        for cat, pref_val in pref_map.items():
            cat_data = sentiment.get(cat, {})
            pct_positive = cat_data.get("pct_positive")
            if pct_positive is None:
                continue

            importance = pref_val / 5.0  # 0.2 to 1.0
            cat_score = pct_positive  # 0-100

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

        # Confidence penalty: fewer reviews = less certain about the fit
        if num_ratings < 10:
            fit_score = round(fit_score * 0.85, 1)  # 15% penalty
        elif num_ratings < 20:
            fit_score = round(fit_score * 0.92, 1)  # 8% penalty

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
        if grading <= 2 and a_pct >= 70:
            reasons.append(f"{a_pct:.0f}% chance of A")

        bayesian = p.get("bayesian_analysis", {})
        good_post = bayesian.get("rating_posteriors", {}).get("good", {})

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
                if course_code in cname or cname in course_code:
                    bayesian = p.get("bayesian_analysis", {})
                    good_post = bayesian.get("rating_posteriors", {}).get("good", {})
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
                if course_code in cname or cname in course_code:
                    summary = p.get("summary", {})
                    bayesian = p.get("bayesian_analysis", {})
                    good_post = bayesian.get("rating_posteriors", {}).get("good", {})
                    grade_probs = p.get("grade_probabilities", {})

                    # Compute a composite score based on preference
                    rating = summary.get("avg_rating") or 3.0
                    difficulty = summary.get("avg_difficulty") or 3.0
                    good_prob = good_post.get("mean", 0.5)
                    wta = summary.get("would_take_again_pct")
                    wta_score = (wta / 100) if wta and wta >= 0 else 0.5
                    a_pct = grade_probs.get("A range", 0) / 100 if grade_probs.get("A range") else 0.3

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
