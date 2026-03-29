"""
Deep scraper for maximum professor coverage at a single school.
Searches three-letter combos, resumes from existing data, and auto-pushes to GitHub.

Usage:
    python deep_scrape.py --school umich
    python deep_scrape.py --school umich --push    # auto git push when done
    python deep_scrape.py --school msu --push
"""

import json
import os
import sys
import time
import subprocess
import argparse
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# RMP GraphQL config
RMP_URL = "https://www.ratemyprofessors.com/graphql"
HEADERS = {
    "Authorization": "Basic dGVzdDp0ZXN0",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.ratemyprofessors.com/",
    "Origin": "https://www.ratemyprofessors.com",
}

SEARCH_PROFS_QUERY = """
query SearchProfs($query: TeacherSearchQuery!, $after: String) {
  newSearch {
    teachers(query: $query, after: $after) {
      edges {
        node {
          id firstName lastName department
          avgRating avgDifficulty numRatings wouldTakeAgainPercent
          teacherRatingTags { tagName tagCount }
        }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
}
"""

REVIEWS_QUERY = """
query ProfReviews($profID: ID!, $after: String) {
  node(id: $profID) {
    ... on Teacher {
      ratings(first: 20, after: $after) {
        edges {
          node {
            id class date comment helpfulRating clarityRating
            difficultyRating ratingTags wouldTakeAgain grade
            isForOnlineClass isForCredit attendanceMandatory
            thumbsUpTotal thumbsDownTotal
          }
        }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}
"""

# School ID lookup
SCHOOL_IDS = {
    "umich": ("University of Michigan", None),  # auto-search
    "msu": ("Michigan State University", "U2Nob29sLTYwMQ=="),
    "mit": ("Massachusetts Institute of Technology", None),
    "berkeley": ("University of California Berkeley", None),
    "stanford": ("Stanford University", None),
    "gatech": ("Georgia Institute of Technology", None),
    "cmu": ("Carnegie Mellon University", None),
    "purdue": ("Purdue University", "U2Nob29sLTc4Mw=="),
    "nyu": ("New York University", "U2Nob29sLTY3NQ=="),
    "osu": ("The Ohio State University", "U2Nob29sLTcyNA=="),
    "uiuc": ("University of Illinois Urbana-Champaign", "U2Nob29sLTExMTI="),
    "umass": ("University of Massachusetts Amherst", "U2Nob29sLTE1MTM="),
}


def gql(query, variables, retries=3):
    for attempt in range(retries + 1):
        try:
            r = requests.post(RMP_URL, headers=HEADERS, json={"query": query, "variables": variables}, timeout=15)
            if r.status_code == 429:
                wait = 2 ** attempt + 2
                print(f"    Rate limited, waiting {wait}s...", flush=True)
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json().get("data", {})
        except Exception:
            if attempt < retries:
                time.sleep(2 ** attempt)
            else:
                return {}
    return {}


def search_school(name):
    query = """query($q: String!) { newSearch { schools(query: {text: $q}) { edges { node { id name city state } } } } }"""
    data = gql(query, {"q": name})
    edges = data.get("newSearch", {}).get("schools", {}).get("edges", [])
    return [e["node"] for e in edges]


def discover_professors(school_id, existing_ids=None):
    """Search with 1, 2, and 3 letter combos for maximum coverage."""
    seen = set(existing_ids or [])
    professors = {}
    letters = "abcdefghijklmnopqrstuvwxyz"

    # Build search terms: a-z, then aa-zz, then common 3-letter prefixes
    terms = list(letters)
    for a in letters:
        for b in letters:
            terms.append(a + b)

    total = len(terms)
    new_found = 0

    for i, term in enumerate(terms):
        cursor = None
        term_new = 0

        while True:
            variables = {"query": {"text": term, "schoolID": school_id}}
            if cursor:
                variables["after"] = cursor

            data = gql(SEARCH_PROFS_QUERY, variables)
            teachers = data.get("newSearch", {}).get("teachers", {})
            edges = teachers.get("edges", [])

            if not edges:
                break

            for edge in edges:
                p = edge["node"]
                pid = p.get("id")
                if pid in seen:
                    continue
                seen.add(pid)
                if p.get("numRatings", 0) > 0:
                    professors[pid] = p
                    term_new += 1
                    new_found += 1

            page_info = teachers.get("pageInfo", {})
            if not page_info.get("hasNextPage") or not page_info.get("endCursor"):
                break
            cursor = page_info["endCursor"]
            time.sleep(0.2)

        # Progress logging
        if len(term) == 1:
            print(f"  [{i+1}/{total}] '{term}' +{term_new} new (total: {len(professors)} new, {len(seen)} seen)", flush=True)
        elif term_new > 0:
            print(f"  [{i+1}/{total}] '{term}' +{term_new}", flush=True)

        if len(term) == 2 and (i + 1) % 100 == 0:
            print(f"  ... {i+1}/{total} searched, {len(professors)} new professors found", flush=True)

        time.sleep(0.15)

    print(f"\n  Discovery complete: {len(professors)} new professors found ({len(seen)} total seen)")
    return professors


def fetch_reviews(prof_id, max_reviews=None):
    reviews = []
    cursor = None
    while True:
        variables = {"profID": prof_id}
        if cursor:
            variables["after"] = cursor
        data = gql(REVIEWS_QUERY, variables)
        node = data.get("node", {})
        if not node:
            break
        ratings = node.get("ratings", {})
        edges = ratings.get("edges", [])
        for edge in edges:
            reviews.append(edge["node"])
        pi = ratings.get("pageInfo", {})
        if not pi.get("hasNextPage") or not pi.get("endCursor"):
            break
        cursor = pi["endCursor"]
        if max_reviews and len(reviews) >= max_reviews:
            break
        time.sleep(0.2)
    return reviews


def fetch_all_reviews(professors, min_ratings=3):
    """Fetch reviews for all professors using 2 parallel workers."""
    filtered = {pid: p for pid, p in professors.items() if p.get("numRatings", 0) >= min_ratings}
    print(f"\n  Fetching reviews for {len(filtered)} professors (min {min_ratings} ratings)...")

    results = []
    done = 0

    def fetch_one(pid, prof):
        reviews = fetch_reviews(pid)
        return {
            "id": pid,
            "first_name": prof["firstName"],
            "last_name": prof["lastName"],
            "department": prof.get("department", "Unknown"),
            "avg_rating": prof.get("avgRating"),
            "avg_difficulty": prof.get("avgDifficulty"),
            "num_ratings": prof.get("numRatings"),
            "would_take_again_pct": prof.get("wouldTakeAgainPercent"),
            "top_tags": [{"tag": t["tagName"], "count": t["tagCount"]} for t in (prof.get("teacherRatingTags") or [])],
            "reviews": [{
                "id": r.get("id"), "class_name": r.get("class"), "date": r.get("date"),
                "comment": r.get("comment", ""), "helpful_rating": r.get("helpfulRating"),
                "clarity_rating": r.get("clarityRating"), "difficulty_rating": r.get("difficultyRating"),
                "rating_tags": r.get("ratingTags", ""), "would_take_again": r.get("wouldTakeAgain"),
                "grade": r.get("grade"), "is_online": r.get("isForOnlineClass"),
                "is_for_credit": r.get("isForCredit"), "attendance_mandatory": r.get("attendanceMandatory"),
                "thumbs_up": r.get("thumbsUpTotal", 0), "thumbs_down": r.get("thumbsDownTotal", 0),
            } for r in reviews],
        }

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(fetch_one, pid, prof): pid for pid, prof in filtered.items()}
        for future in as_completed(futures):
            try:
                data = future.result()
                results.append(data)
                done += 1
                if done % 50 == 0 or done == len(filtered):
                    with_reviews = sum(1 for r in results if len(r["reviews"]) > 0)
                    print(f"  {done}/{len(filtered)} fetched ({with_reviews} with reviews)", flush=True)
                if done % 30 == 0:
                    time.sleep(1)
            except Exception as e:
                print(f"  [ERROR] {futures[future]}: {e}")
                done += 1

    return results


def main():
    parser = argparse.ArgumentParser(description="Deep scrape a school for maximum professor coverage")
    parser.add_argument("--school", required=True, help="School slug (e.g., umich, msu)")
    parser.add_argument("--push", action="store_true", help="Auto git add, commit, push when done")
    parser.add_argument("--min-ratings", type=int, default=3, help="Minimum ratings to include")
    args = parser.parse_args()

    slug = args.school.lower()
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    raw_path = os.path.join(data_dir, f"{slug}.json")
    analyzed_path = os.path.join(data_dir, f"{slug}_analyzed.json")
    pipeline = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bayesian_pipeline.py")

    # Resolve school
    if slug in SCHOOL_IDS:
        school_name, school_id = SCHOOL_IDS[slug]
    else:
        school_name = slug
        school_id = None

    if not school_id:
        print(f"Searching for '{school_name}'...")
        results = search_school(school_name)
        if not results:
            print("School not found")
            sys.exit(1)
        school_id = results[0]["id"]
        school_name = results[0]["name"]
        print(f"Found: {school_name} (ID: {school_id})")

    # Load existing data to avoid re-fetching known professors
    existing_ids = set()
    existing_profs = []
    if os.path.exists(raw_path):
        with open(raw_path) as f:
            old = json.load(f)
        existing_profs = old.get("professors", [])
        existing_ids = {p["id"] for p in existing_profs}
        existing_with_reviews = sum(1 for p in existing_profs if len(p.get("reviews", [])) > 0)
        print(f"Existing data: {len(existing_profs)} professors ({existing_with_reviews} with reviews)")

    # Discover new professors
    print(f"\nDiscovering professors at {school_name}...")
    new_profs = discover_professors(school_id, existing_ids)

    if not new_profs:
        print("No new professors found. Checking for professors missing reviews...")
        # Re-fetch reviews for professors that had empty reviews (rate limited last time)
        empty_profs = {p["id"]: {
            "firstName": p["first_name"], "lastName": p["last_name"],
            "department": p["department"], "numRatings": p["num_ratings"],
            "avgRating": p["avg_rating"], "avgDifficulty": p["avg_difficulty"],
            "wouldTakeAgainPercent": p["would_take_again_pct"],
            "teacherRatingTags": [{"tagName": t["tag"], "tagCount": t["count"]} for t in p.get("top_tags", [])],
        } for p in existing_profs if len(p.get("reviews", [])) == 0 and p.get("num_ratings", 0) >= args.min_ratings}

        if empty_profs:
            print(f"Re-fetching reviews for {len(empty_profs)} professors that were rate-limited...")
            new_results = fetch_all_reviews(empty_profs, args.min_ratings)
            # Merge: replace empty professors with new data
            existing_by_id = {p["id"]: p for p in existing_profs}
            for r in new_results:
                if len(r["reviews"]) > 0:
                    existing_by_id[r["id"]] = r
            existing_profs = list(existing_by_id.values())
        else:
            print("All professors already have reviews. Nothing to do.")
            return
    else:
        # Fetch reviews for new professors
        new_results = fetch_all_reviews(new_profs, args.min_ratings)
        existing_profs.extend(new_results)

    # Save
    total_reviews = sum(len(p.get("reviews", [])) for p in existing_profs)
    with_reviews = sum(1 for p in existing_profs if len(p.get("reviews", [])) > 0)
    result = {
        "metadata": {
            "school_name": school_name,
            "school_id": school_id,
            "total_professors": len(existing_profs),
            "total_reviews": total_reviews,
            "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "professors": existing_profs,
    }
    with open(raw_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nSaved to {raw_path}")
    print(f"  Total professors: {len(existing_profs)}")
    print(f"  With reviews: {with_reviews}")
    print(f"  Total reviews: {total_reviews}")

    # Run pipeline
    print(f"\nRunning Bayesian analysis...")
    subprocess.run([sys.executable, pipeline, "--input", raw_path, "--output", analyzed_path])

    # Auto push
    if args.push:
        print("\nPushing to GitHub...")
        subprocess.run(["git", "add", "data/"])
        subprocess.run(["git", "commit", "-m", f"Deep scrape {school_name}: {len(existing_profs)} professors, {total_reviews} reviews"])
        subprocess.run(["git", "push"])
        print("Pushed.")


if __name__ == "__main__":
    main()
