"""
ProfInsight — Bulk School Scraper & Analyzer
=============================================
One command to scrape and analyze multiple schools.

Usage:
    python bulk_update.py                          # All default schools
    python bulk_update.py --schools "MIT,Stanford"  # Specific schools
    python bulk_update.py --add "Georgia Tech"      # Add a new school
    python bulk_update.py --refresh                 # Re-scrape all existing
    python bulk_update.py --list                    # Show available schools
"""

import subprocess
import sys
import os
import json
import time
import argparse

# ─── Default School List ──────────────────────────────────────────────────────
# slug: (search name, max_professors)

DEFAULT_SCHOOLS = {
    "umich": ("University of Michigan", 200),
    "mit": ("Massachusetts Institute of Technology", 150),
    "stanford": ("Stanford University", 150),
    "berkeley": ("University of California Berkeley", 150),
    "utdallas": ("University of Texas at Dallas", 150),
    "gatech": ("Georgia Institute of Technology", 150),
    "uiuc": ("University of Illinois Urbana-Champaign", 150),
    "cmu": ("Carnegie Mellon University", 150),
    "purdue": ("Purdue University", 150),
    "umass": ("University of Massachusetts Amherst", 150),
    "unc": ("University of North Carolina at Chapel Hill", 150),
    "nyu": ("New York University", 150),
    "columbia": ("Columbia University", 150),
    "upenn": ("University of Pennsylvania", 150),
    "cornell": ("Cornell University", 150),
    "umd": ("University of Maryland", 150),
    "uw": ("University of Washington", 150),
    "ucla": ("University of California Los Angeles", 150),
    "ucsd": ("University of California San Diego", 150),
    "osu": ("Ohio State University", 150),
    "wisc": ("University of Wisconsin Madison", 150),
    "uf": ("University of Florida", 150),
    "fsu": ("Florida State University", 150),
    "utaustin": ("University of Texas at Austin", 150),
    "tamu": ("Texas A&M University", 150),
    "msu": ("Michigan State University", 150),
    "psu": ("Penn State University", 150),
    "bu": ("Boston University", 150),
    "northeastern": ("Northeastern University", 150),
    "rice": ("Rice University", 150),
}

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SCRAPER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rmp_scraper.py")
PIPELINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bayesian_pipeline.py")


def scrape_school(slug, name, max_profs):
    """Scrape a single school."""
    raw_path = os.path.join(DATA_DIR, f"{slug}.json")
    analyzed_path = os.path.join(DATA_DIR, f"{slug}_analyzed.json")

    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"  Slug: {slug} | Max professors: {max_profs}")
    print(f"{'='*60}")

    # Step 1: Scrape
    print(f"\n[1/2] Scraping from RateMyProfessor...")
    t0 = time.time()
    result = subprocess.run(
        [sys.executable, SCRAPER,
         "--school", name,
         "--max-professors", str(max_profs),
         "--output", raw_path],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  FAILED: {result.stderr[-300:]}")
        return False

    # Quick stats from output
    for line in result.stdout.split("\n"):
        if "Saved to" in line or "Total:" in line or "Found" in line:
            print(f"  {line.strip()}")
    print(f"  Scrape time: {time.time() - t0:.0f}s")

    # Step 2: Analyze
    print(f"\n[2/2] Running Bayesian analysis...")
    t1 = time.time()
    result = subprocess.run(
        [sys.executable, PIPELINE,
         "--input", raw_path,
         "--output", analyzed_path],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  FAILED: {result.stderr[-300:]}")
        return False

    for line in result.stdout.split("\n"):
        if "Professors analyzed" in line or "saved" in line.lower():
            print(f"  {line.strip()}")
    print(f"  Analysis time: {time.time() - t1:.0f}s")

    # Show summary
    try:
        with open(analyzed_path) as f:
            data = json.load(f)
        meta = data.get("metadata", {})
        print(f"\n  ✓ {meta.get('school_name', slug)}: {meta.get('total_professors', 0)} professors, {meta.get('total_reviews', 0)} reviews")
    except Exception:
        pass

    return True


def list_schools():
    """Show all available schools and their data status."""
    os.makedirs(DATA_DIR, exist_ok=True)
    print(f"\n{'Slug':<15} {'School':<45} {'Status':<20} {'Profs':>6} {'Reviews':>8}")
    print("-" * 100)

    for slug, (name, max_p) in sorted(DEFAULT_SCHOOLS.items()):
        analyzed = os.path.join(DATA_DIR, f"{slug}_analyzed.json")
        if os.path.exists(analyzed):
            try:
                with open(analyzed) as f:
                    meta = json.load(f).get("metadata", {})
                profs = meta.get("total_professors", "?")
                reviews = meta.get("total_reviews", "?")
                status = "✓ Ready"
            except Exception:
                profs = reviews = "?"
                status = "⚠ Error"
        else:
            profs = reviews = "—"
            status = "○ Not scraped"

        print(f"{slug:<15} {name:<45} {status:<20} {str(profs):>6} {str(reviews):>8}")


def main():
    parser = argparse.ArgumentParser(description="ProfInsight Bulk School Manager")
    parser.add_argument("--schools", type=str, help="Comma-separated slugs to scrape (e.g., 'mit,stanford')")
    parser.add_argument("--add", type=str, help="Add a new school by name (e.g., 'Georgia Tech')")
    parser.add_argument("--add-slug", type=str, help="Slug for the new school (used with --add)")
    parser.add_argument("--refresh", action="store_true", help="Re-scrape all existing schools")
    parser.add_argument("--all", action="store_true", help="Scrape ALL default schools")
    parser.add_argument("--list", action="store_true", help="List all schools and their status")
    parser.add_argument("--max-professors", type=int, default=None, help="Override max professors per school")
    args = parser.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)

    if args.list:
        list_schools()
        return

    schools_to_scrape = []

    if args.add:
        # Add a custom school
        slug = args.add_slug or args.add.lower().replace(" ", "").replace("-", "")[:12]
        max_p = args.max_professors or 150
        schools_to_scrape.append((slug, args.add, max_p))

    elif args.schools:
        # Specific schools by slug
        for slug in args.schools.split(","):
            slug = slug.strip().lower()
            if slug in DEFAULT_SCHOOLS:
                name, max_p = DEFAULT_SCHOOLS[slug]
                schools_to_scrape.append((slug, name, args.max_professors or max_p))
            else:
                print(f"Unknown slug: {slug}. Use --list to see available schools.")

    elif args.refresh:
        # Re-scrape all that have existing data
        for slug, (name, max_p) in DEFAULT_SCHOOLS.items():
            analyzed = os.path.join(DATA_DIR, f"{slug}_analyzed.json")
            if os.path.exists(analyzed):
                schools_to_scrape.append((slug, name, args.max_professors or max_p))

    elif args.all:
        # Scrape everything
        for slug, (name, max_p) in DEFAULT_SCHOOLS.items():
            schools_to_scrape.append((slug, name, args.max_professors or max_p))

    else:
        # Default: scrape schools that don't have data yet
        for slug, (name, max_p) in DEFAULT_SCHOOLS.items():
            analyzed = os.path.join(DATA_DIR, f"{slug}_analyzed.json")
            if not os.path.exists(analyzed):
                schools_to_scrape.append((slug, name, args.max_professors or max_p))

    if not schools_to_scrape:
        print("Nothing to scrape. Use --list to see status, or --all to scrape everything.")
        return

    print(f"\nWill scrape {len(schools_to_scrape)} schools:")
    for slug, name, max_p in schools_to_scrape:
        print(f"  • {name} ({slug}, max {max_p} profs)")

    total_start = time.time()
    success = 0
    failed = 0

    for slug, name, max_p in schools_to_scrape:
        try:
            if scrape_school(slug, name, max_p):
                success += 1
            else:
                failed += 1
        except KeyboardInterrupt:
            print("\n\nInterrupted! Schools scraped so far are saved.")
            break
        except Exception as e:
            print(f"  ERROR: {e}")
            failed += 1

    total_time = time.time() - total_start
    print(f"\n{'='*60}")
    print(f"  Done! {success} succeeded, {failed} failed")
    print(f"  Total time: {total_time/60:.1f} minutes")
    print(f"{'='*60}")

    # Show final status
    list_schools()


if __name__ == "__main__":
    main()
