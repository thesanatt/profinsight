"""
ProfInsight — RateMyProfessor GraphQL Scraper
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


# ─── RMP GraphQL Config ───────────────────────────────────────────────────────

RMP_GRAPHQL_URL = "https://www.ratemyprofessors.com/graphql"

# RMP uses a static auth header (base64 encoded "test:test" — this is their
# public-facing token embedded in the frontend JS bundle)
RMP_AUTH_TOKEN = "dGVzdDp0ZXN0"

HEADERS = {
    "Authorization": f"Basic {RMP_AUTH_TOKEN}",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Referer": "https://www.ratemyprofessors.com/",
    "Origin": "https://www.ratemyprofessors.com",
}

# Rate limiting: be respectful
REQUEST_DELAY = 0.3  # seconds between requests


# ─── GraphQL Queries ──────────────────────────────────────────────────────────

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


# ─── API Helpers ──────────────────────────────────────────────────────────────

def graphql_request(query: str, variables: dict) -> dict:
    """Send a GraphQL request to RMP and return the JSON response."""
    payload = {"query": query, "variables": variables}
    try:
        response = requests.post(RMP_GRAPHQL_URL, headers=HEADERS, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        if "errors" in data:
            print(f"  [WARN] GraphQL errors: {data['errors']}")
        return data.get("data", {})
    except requests.exceptions.RequestException as e:
        print(f"  [ERROR] Request failed: {e}")
        return {}


def search_school(school_name: str) -> list:
    """Search for a school by name. Returns list of {id, name, city, state}."""
    data = graphql_request(SEARCH_SCHOOL_QUERY, {"query": school_name})
    schools = data.get("newSearch", {}).get("schools", {}).get("edges", [])
    return [edge["node"] for edge in schools]


def get_all_professors(school_id: str, max_professors: int = None) -> list:
    """
    Paginate through all professors at a school.
    RMP's search API limits empty-text queries, so we search through
    each letter of the alphabet to find all professors.
    Returns list of professor summary dicts (deduplicated).
    """
    seen_ids = set()
    professors = []

    # Search with each letter to get broad coverage
    search_terms = list("abcdefghijklmnopqrstuvwxyz")

    for letter_idx, letter in enumerate(search_terms):
        cursor = None
        page = 0

        while True:
            page += 1
            variables = {
                "query": {
                    "text": letter,
                    "schoolID": school_id,
                }
            }
            if cursor:
                variables["after"] = cursor

            if page == 1:
                print(f"  Searching '{letter}' ({letter_idx+1}/{len(search_terms)})...", end="", flush=True)

            data = graphql_request(SEARCH_PROFESSORS_QUERY, variables)

            if not data:
                break

            teachers = data.get("newSearch", {}).get("teachers", {})
            edges = teachers.get("edges", [])

            if not edges:
                break

            new_count = 0
            for edge in edges:
                prof = edge["node"]
                pid = prof.get("id")
                if pid in seen_ids:
                    continue
                seen_ids.add(pid)
                if prof.get("numRatings", 0) > 0:
                    professors.append(prof)
                    new_count += 1

            page_info = teachers.get("pageInfo", {})
            has_next = page_info.get("hasNextPage", False)
            cursor = page_info.get("endCursor")

            if not has_next or not cursor:
                break

            time.sleep(REQUEST_DELAY)

        if page == 1:
            print(f" {new_count} new")
        else:
            print(f" {new_count} new ({page} pages)")

        if max_professors and len(professors) >= max_professors:
            professors = professors[:max_professors]
            print(f"  Reached max_professors limit ({max_professors})")
            break

        time.sleep(REQUEST_DELAY)

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


# ─── Main Scraping Pipeline ──────────────────────────────────────────────────

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

    # Step 3: Fetch reviews for each professor
    print(f"\nFetching reviews for {len(professors)} professors...")
    professor_data = []

    for i, prof in enumerate(professors):
        prof_name = f"{prof['firstName']} {prof['lastName']}"
        print(f"  [{i+1}/{len(professors)}] {prof_name} ({prof['numRatings']} ratings)...")

        reviews = get_professor_reviews(prof["id"], max_reviews_per_prof)

        professor_data.append({
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
        })

        time.sleep(REQUEST_DELAY)

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


# ─── CLI ──────────────────────────────────────────────────────────────────────

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
