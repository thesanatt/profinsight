"""
ProfInsight - RateMyProfessor GraphQL Scraper
=============================================
Scrapes professor profiles and full review text from RMP's GraphQL API.
Outputs clean JSON ready for the Bayesian ML pipeline.

Usage:
    python rmp_scraper.py --school "University of Michigan" --output data/umich.json
    python rmp_scraper.py --school-id "U2Nob29sLTEyNTg=" --output data/umich.json
"""

import requests
import json
import base64
import time
import argparse
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed


# RMP GraphQL Config

RMP_GRAPHQL_URL = "https://www.ratemyprofessors.com/graphql"

# RMP uses a static auth header (base64 encoded "test:test" - this is their
# public-facing token embedded in the frontend JS bundle)
RMP_AUTH_TOKEN = "dGVzdDp0ZXN0"

HEADERS = {
    "Authorization": f"Basic {RMP_AUTH_TOKEN}",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Referer": "https://www.ratemyprofessors.com/",
    "Origin": "https://www.ratemyprofessors.com",
}

# Rate limiting: respect RMP's limits
REQUEST_DELAY = 0.3  # seconds between requests
MAX_WORKERS = 2  # parallel review fetches (higher = risk of 429s)


# GraphQL Queries

SEARCH_SCHOOL_QUERY = """
query SearchSchool($query: String!) {
  newSearch {
    schools(query: { text: $query }) {
      edges {
        node {
          id
          name
          city
          state
        }
      }
    }
  }
}
"""

# Search for professors at a specific school (paginated)
SEARCH_PROFESSORS_QUERY = """
query SearchProfessorsAtSchool($query: TeacherSearchQuery!, $after: String) {
  newSearch {
    teachers(query: $query, after: $after) {
      edges {
        cursor
        node {
          id
          legacyId
          firstName
          lastName
          department
          avgRating
          avgDifficulty
          numRatings
          wouldTakeAgainPercent
          teacherRatingTags {
            tagName
            tagCount
          }
        }
      }
      pageInfo {
        hasNextPage
        endCursor
      }
    }
  }
}
"""

# Get full reviews for a specific professor
PROFESSOR_REVIEWS_QUERY = """
query ProfessorReviews($profID: ID!, $after: String) {
  node(id: $profID) {
    ... on Teacher {
      id
      legacyId
      firstName
      lastName
      department
      school {
        id
        name
      }
      avgRating
      avgDifficulty
      numRatings
      wouldTakeAgainPercent
      teacherRatingTags {
        tagName
        tagCount
      }
      ratings(first: 20, after: $after) {
        edges {
          cursor
          node {
            id
            legacyId
            class
            date
            comment
            helpfulRating
            clarityRating
            difficultyRating
            ratingTags
            wouldTakeAgain
            grade
            isForOnlineClass
            isForCredit
            attendanceMandatory
            thumbsUpTotal
            thumbsDownTotal
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
  }
}
"""


# API Helpers

def graphql_request(query: str, variables: dict, max_retries: int = 3) -> dict:
    """Send a GraphQL request to RMP with retry and exponential backoff."""
    payload = {"query": query, "variables": variables}
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(RMP_GRAPHQL_URL, headers=HEADERS, json=payload, timeout=15)
            if response.status_code == 429:
                # Rate limited - back off exponentially
                wait = 2 ** attempt + 1  # 2s, 3s, 5s, 9s
                if attempt < max_retries:
                    time.sleep(wait)
                    continue
                else:
                    return {}
            response.raise_for_status()
            data = response.json()
            if "errors" in data:
                pass  # silent, don't spam logs
            return data.get("data", {})
        except requests.exceptions.RequestException as e:
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            return {}


def search_school(school_name: str) -> list:
    """Search for a school by name. Returns list of {id, name, city, state}."""
    data = graphql_request(SEARCH_SCHOOL_QUERY, {"query": school_name})
    schools = data.get("newSearch", {}).get("schools", {}).get("edges", [])
    return [edge["node"] for edge in schools]


def get_all_professors(school_id: str, max_professors: int = None) -> list:
    """
    Paginate through all professors at a school.
    Uses two-letter search combinations with concurrent requests for speed.
    Returns list of professor summary dicts (deduplicated).
    """
    import threading

    seen_ids = set()
    seen_lock = threading.Lock()
    professors = []
    professors_lock = threading.Lock()

    letters = "abcdefghijklmnopqrstuvwxyz"
    search_terms = list(letters)
    for a in letters:
        for b in letters:
            search_terms.append(a + b)

    def search_term(term):
        """Search a single term and return new professors found."""
        results = []
        cursor = None
        while True:
            variables = {"query": {"text": term, "schoolID": school_id}}
            if cursor:
                variables["after"] = cursor
            data = graphql_request(SEARCH_PROFESSORS_QUERY, variables)
            if not data:
                break
            teachers = data.get("newSearch", {}).get("teachers", {})
            edges = teachers.get("edges", [])
            if not edges:
                break
            for edge in edges:
                prof = edge["node"]
                pid = prof.get("id")
                with seen_lock:
                    if pid in seen_ids:
                        continue
                    seen_ids.add(pid)
                if prof.get("numRatings", 0) > 0:
                    results.append(prof)
            page_info = teachers.get("pageInfo", {})
            if not page_info.get("hasNextPage") or not page_info.get("endCursor"):
                break
            cursor = page_info["endCursor"]
            time.sleep(0.15)
        return term, results

    # First do single letters sequentially (fast, gives us a baseline)
    print("  Phase 1: Single letter search...", flush=True)
    for term in search_terms[:26]:
        _, results = search_term(term)
        professors.extend(results)
        if results:
            print(f"    '{term}': {len(results)} new", flush=True)
        if max_professors and len(professors) >= max_professors:
            professors = professors[:max_professors]
            print(f"  Reached limit ({max_professors})")
            return professors

    print(f"  Phase 1 done: {len(professors)} professors", flush=True)

    if max_professors and len(professors) >= max_professors:
        professors = professors[:max_professors]
        return professors

    # Phase 2: Two-letter combos in parallel (8 workers)
    print(f"  Phase 2: Two-letter combos (8 concurrent)...", flush=True)
    two_letter_terms = search_terms[26:]
    done = 0
    stopped = False

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(search_term, t): t for t in two_letter_terms}
        for future in as_completed(futures):
            if stopped:
                continue
            try:
                term, results = future.result()
                done += 1
                if results:
                    with professors_lock:
                        professors.extend(results)
                    if len(results) > 3:
                        print(f"    '{term}': {len(results)} new (total: {len(professors)})", flush=True)

                if done % 100 == 0:
                    print(f"  ... {done}/{len(two_letter_terms)} searched, {len(professors)} found", flush=True)

                if max_professors and len(professors) >= max_professors:
                    stopped = True
                    print(f"  Reached limit ({max_professors}) at {done}/{len(two_letter_terms)} searches")
            except Exception as e:
                done += 1

    if max_professors:
        professors = professors[:max_professors]

    print(f"  Total: {len(professors)} professors with ratings.")
    return professors


def get_professor_reviews(prof_id: str, max_reviews: int = None) -> list:
    """
    Paginate through all reviews for a professor.
    Returns list of review dicts with full comment text.
    """
    reviews = []
    cursor = None
    page = 0

    while True:
        page += 1
        variables = {"profID": prof_id}
        if cursor:
            variables["after"] = cursor

        data = graphql_request(PROFESSOR_REVIEWS_QUERY, variables)
        node = data.get("node", {})
        if not node:
            break

        ratings = node.get("ratings", {})
        edges = ratings.get("edges", [])

        for edge in edges:
            review = edge["node"]
            reviews.append(review)

        page_info = ratings.get("pageInfo", {})
        has_next = page_info.get("hasNextPage", False)
        cursor = page_info.get("endCursor")

        if max_reviews and len(reviews) >= max_reviews:
            reviews = reviews[:max_reviews]
            break

        if not has_next or not cursor:
            break

        time.sleep(REQUEST_DELAY)

    return reviews


# Main Scraping Pipeline

def scrape_school(
    school_name: str = None,
    school_id: str = None,
    max_professors: int = None,
    max_reviews_per_prof: int = None,
    min_ratings: int = 3,
) -> dict:
    """
    Full scraping pipeline for a school.

    Args:
        school_name: Name to search (e.g., "University of Michigan")
        school_id: Direct RMP school ID (base64 encoded)
        max_professors: Limit number of professors to scrape
        max_reviews_per_prof: Limit reviews per professor
        min_ratings: Skip professors with fewer than this many ratings

    Returns:
        Dict with school info and list of professor profiles + reviews.
    """
    # Step 1: Resolve school
    if school_id:
        print(f"Using provided school ID: {school_id}")
        school_info = {"id": school_id, "name": school_name or "Unknown"}
    else:
        print(f"Searching for school: {school_name}")
        results = search_school(school_name)
        if not results:
            print("No schools found!")
            return {}
        school_info = results[0]
        school_id = school_info["id"]
        print(f"Found: {school_info['name']} ({school_info.get('city', '')}, {school_info.get('state', '')})")
        print(f"School ID: {school_id}")

    # Step 2: Get all professors
    print(f"\nFetching professors...")
    professors = get_all_professors(school_id, max_professors)

    # Filter by min ratings
    professors = [p for p in professors if p.get("numRatings", 0) >= min_ratings]
    print(f"After filtering (min {min_ratings} ratings): {len(professors)} professors")

    # Step 3: Fetch reviews for each professor (parallel for speed)
    print(f"\nFetching reviews for {len(professors)} professors (parallel)...")
    professor_data = []

    def fetch_one(prof):
        reviews = get_professor_reviews(prof["id"], max_reviews_per_prof)
        return {
            "id": prof["id"],
            "legacy_id": prof.get("legacyId"),
            "first_name": prof["firstName"],
            "last_name": prof["lastName"],
            "department": prof.get("department", "Unknown"),
            "avg_rating": prof.get("avgRating"),
            "avg_difficulty": prof.get("avgDifficulty"),
            "num_ratings": prof.get("numRatings"),
            "would_take_again_pct": prof.get("wouldTakeAgainPercent"),
            "top_tags": [
                {"tag": t["tagName"], "count": t["tagCount"]}
                for t in (prof.get("teacherRatingTags") or [])
            ],
            "reviews": [
                {
                    "id": r.get("id"),
                    "class_name": r.get("class"),
                    "date": r.get("date"),
                    "comment": r.get("comment", ""),
                    "helpful_rating": r.get("helpfulRating"),
                    "clarity_rating": r.get("clarityRating"),
                    "difficulty_rating": r.get("difficultyRating"),
                    "rating_tags": r.get("ratingTags", ""),
                    "would_take_again": r.get("wouldTakeAgain"),
                    "grade": r.get("grade"),
                    "is_online": r.get("isForOnlineClass"),
                    "is_for_credit": r.get("isForCredit"),
                    "attendance_mandatory": r.get("attendanceMandatory"),
                    "thumbs_up": r.get("thumbsUpTotal", 0),
                    "thumbs_down": r.get("thumbsDownTotal", 0),
                }
                for r in reviews
            ],
        }

    done = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_one, prof): prof for prof in professors}
        for future in as_completed(futures):
            try:
                data = future.result()
                professor_data.append(data)
                done += 1
                if done % 50 == 0 or done == len(professors):
                    print(f"  {done}/{len(professors)} professors fetched...", flush=True)
                # Small delay every batch to avoid rate limits
                if done % 20 == 0:
                    time.sleep(1)
            except Exception as e:
                prof = futures[future]
                print(f"  [ERROR] {prof['firstName']} {prof['lastName']}: {e}")
                done += 1

    # Step 4: Package result
    result = {
        "metadata": {
            "school_name": school_info.get("name", "Unknown"),
            "school_id": school_id,
            "city": school_info.get("city", ""),
            "state": school_info.get("state", ""),
            "scraped_at": datetime.now(tz=__import__("datetime").timezone.utc).isoformat(),
            "total_professors": len(professor_data),
            "total_reviews": sum(len(p["reviews"]) for p in professor_data),
        },
        "professors": professor_data,
    }

    return result


def save_json(data: dict, output_path: str):
    """Save scraped data to JSON file."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\nSaved to {output_path}")
    print(f"  Professors: {data['metadata']['total_professors']}")
    print(f"  Reviews: {data['metadata']['total_reviews']}")


# CLI

def main():
    parser = argparse.ArgumentParser(description="ProfInsight RMP Scraper")
    parser.add_argument("--school", type=str, help="School name to search")
    parser.add_argument("--school-id", type=str, help="Direct RMP school ID (base64)")
    parser.add_argument("--output", type=str, default="data/school_data.json",
                        help="Output JSON file path")
    parser.add_argument("--max-professors", type=int, default=None,
                        help="Max professors to scrape (default: all)")
    parser.add_argument("--max-reviews", type=int, default=None,
                        help="Max reviews per professor (default: all)")
    parser.add_argument("--min-ratings", type=int, default=3,
                        help="Min ratings to include a professor (default: 3)")

    args = parser.parse_args()

    if not args.school and not args.school_id:
        parser.error("Either --school or --school-id is required")

    data = scrape_school(
        school_name=args.school,
        school_id=args.school_id,
        max_professors=args.max_professors,
        max_reviews_per_prof=args.max_reviews,
        min_ratings=args.min_ratings,
    )

    if data:
        save_json(data, args.output)
    else:
        print("No data scraped.")


if __name__ == "__main__":
    main()
