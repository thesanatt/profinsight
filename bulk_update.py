"""
ProfInsight - Bulk School Scraper & Analyzer
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
from datafiles import analyzed_path, load_json

# Default School List
# slug: (search name, max_professors, school_id_override)
# school_id_override is used when RMP search returns the wrong campus

# Each entry: slug -> (search name, default max_professors, school_id_override).
# The max value is a reasonable ceiling for the per-school scrape; for full
# coverage runs, pass --max-professors 0 (unlimited). The school_id_override
# is used when RMP search returns the wrong campus.
#
# When adding a new school, just append to this dict — the autoscrape workflows
# pick up new entries automatically on the next scheduled run.
DEFAULT_SCHOOLS = {
    # Original 30 (kept for stability; bumped to 1500 default so we capture
    # nearly every rated professor rather than just the most popular 150).
    "umich":        ("University of Michigan", 1500, None),
    "mit":          ("Massachusetts Institute of Technology", 1500, None),
    "stanford":     ("Stanford University", 1500, None),
    "berkeley":     ("University of California Berkeley", 1500, None),
    # RMP's name search ranks the wrong campus first for several schools
    # (Dallas -> Arlington, Irvine -> Riverside, A&M -> Beaumont), so every
    # ambiguous entry pins its school_id. See docs/DATA.md.
    "utdallas":     ("University of Texas at Dallas", 1500, "U2Nob29sLTEyNzM="),
    "uta":          ("University of Texas at Arlington", 1500, "U2Nob29sLTEzNDM="),
    "gatech":       ("Georgia Institute of Technology", 1500, None),
    "uiuc":         ("University of Illinois Urbana-Champaign", 1500, "U2Nob29sLTExMTI="),
    "cmu":          ("Carnegie Mellon University", 1500, None),
    "purdue":       ("Purdue University", 1500, "U2Nob29sLTc4Mw=="),
    "umass":        ("University of Massachusetts Amherst", 1500, "U2Nob29sLTE1MTM="),
    "unc":          ("University of North Carolina at Chapel Hill", 1500, None),
    "nyu":          ("New York University", 1500, "U2Nob29sLTY3NQ=="),
    "columbia":     ("Columbia University", 1500, None),
    "upenn":        ("University of Pennsylvania", 1500, None),
    "cornell":      ("Cornell University", 1500, None),
    # UMD College Park: the unqualified RMP search returns UMBC first, so pin
    # the school_id to College Park (U2Nob29sLTEyNzA=). UMBC lives on its own
    # slug below so we don't lose that data.
    "umd":          ("University of Maryland", 1500, "U2Nob29sLTEyNzA="),
    "umbc":         ("University of Maryland, Baltimore County", 1500, "U2Nob29sLTEyNDQ="),
    "uw":           ("University of Washington", 1500, "U2Nob29sLTE1MzA="),
    "ucla":         ("University of California Los Angeles", 1500, None),
    "ucsd":         ("University of California San Diego", 1500, None),
    "osu":          ("The Ohio State University", 1500, "U2Nob29sLTcyNA=="),
    "wisc":         ("University of Wisconsin Madison", 1500, None),
    "uf":           ("University of Florida", 1500, None),
    "fsu":          ("Florida State University", 1500, "U2Nob29sLTEyMzc="),
    "utaustin":     ("University of Texas at Austin", 1500, None),
    "tamu":         ("Texas A&M University", 1500, "U2Nob29sLTEwMDM="),
    "msu":          ("Michigan State University", 1500, None),
    "psu":          ("Penn State University", 1500, None),
    "bu":           ("Boston University", 1500, None),
    "northeastern": ("Northeastern University", 1500, None),
    "rice":         ("Rice University", 1500, None),

    # Ivies + elite privates not already listed
    "harvard":      ("Harvard University", 1500, None),
    "yale":         ("Yale University", 1500, None),
    "princeton":    ("Princeton University", 1500, None),
    "brown":        ("Brown University", 1500, None),
    "dartmouth":    ("Dartmouth College", 1500, None),
    "uchicago":     ("University of Chicago", 1500, None),
    "northwestern": ("Northwestern University", 1500, None),
    "duke":         ("Duke University", 1500, None),
    "jhu":          ("Johns Hopkins University", 1500, "U2Nob29sLTQ2NA=="),
    "vanderbilt":   ("Vanderbilt University", 1500, None),
    "wustl":        ("Washington University in St. Louis", 1500, None),
    "emory":        ("Emory University", 1500, "U2Nob29sLTM0MA=="),
    "notredame":    ("University of Notre Dame", 1500, "U2Nob29sLTE1NzY="),
    "caltech":      ("California Institute of Technology", 1500, "U2Nob29sLTE0OA=="),
    "usc":          ("University of Southern California", 1500, "U2Nob29sLTEzODE="),

    # Big public research schools
    "rutgers":      ("Rutgers University", 1500, "U2Nob29sLTgyNQ=="),
    "uva":          ("University of Virginia", 1500, None),
    "vt":           ("Virginia Tech", 1500, None),
    "ucdavis":      ("University of California Davis", 1500, None),
    "ucsb":         ("University of California Santa Barbara", 1500, None),
    "uci":          ("University of California Irvine", 1500, "U2Nob29sLTEwNzQ="),
    "ucr":          ("University of California Riverside", 1500, "U2Nob29sLTEwNzY="),
    "asu":          ("Arizona State University", 1500, None),
    "ua":           ("University of Arizona", 1500, "U2Nob29sLTE0MDI="),
    "cuboulder":    ("University of Colorado Boulder", 1500, "U2Nob29sLTEwODc="),
    "iub":          ("Indiana University Bloomington", 1500, None),
    "iastate":      ("Iowa State University", 1500, None),
    "kansas":       ("University of Kansas", 1500, None),
    "mizzou":       ("University of Missouri", 1500, None),
    "ncsu":         ("North Carolina State University", 1500, "U2Nob29sLTY4NQ=="),
    "uga":          ("University of Georgia", 1500, None),
    "alabama":      ("University of Alabama", 1500, None),
    "auburn":       ("Auburn University", 1500, "U2Nob29sLTYw"),
    "miami":        ("University of Miami", 1500, None),
    "ucf":          ("University of Central Florida", 1500, "U2Nob29sLTEwODI="),
    "uic":          ("University of Illinois Chicago", 1500, None),
    "uiowa":        ("University of Iowa", 1500, "U2Nob29sLTExMTU="),
    "uky":          ("University of Kentucky", 1500, None),
    "pittsburgh":   ("University of Pittsburgh", 1500, "U2Nob29sLTEyNDc="),
    "uoregon":      ("University of Oregon", 1500, None),
    "wvu":          ("West Virginia University", 1500, "U2Nob29sLTExNjY="),
    "tcu":          ("Texas Christian University", 1500, None),
    "smu":          ("Southern Methodist University", 1500, None),
    "rpi":          ("Rensselaer Polytechnic Institute", 1500, None),
    "wpi":          ("Worcester Polytechnic Institute", 1500, None),
    "stevens":      ("Stevens Institute of Technology", 1500, "U2Nob29sLTE5MDAy"),
    "byu":          ("Brigham Young University", 1500, None),
    "utah":         ("University of Utah", 1500, None),
}

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SCRAPER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rmp_scraper.py")
PIPELINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bayesian_pipeline.py")


def batch_slugs(spec):
    """Slugs in rotation slice 'i/N' of DEFAULT_SCHOOLS (sorted by slug), the
    same slicing --batch applies. Used by the nightly workflow to publish only
    the schools it refreshed."""
    i_str, n_str = spec.split("/")
    i, n = int(i_str), int(n_str)
    if n <= 0 or not 0 <= i < n:
        raise ValueError(f"--batch must be 'i/N' with 0 <= i < N; got {spec!r}")
    return [slug for idx, slug in enumerate(sorted(DEFAULT_SCHOOLS)) if idx % n == i]


def _scraped_at_epoch(analyzed_path):
    """Epoch seconds of metadata.scraped_at in an analyzed file; 0 if missing
    or unparseable so the school counts as stale."""
    if not os.path.exists(analyzed_path):
        return 0.0
    try:
        from datetime import datetime, timezone
        from datafiles import open_text
        with open_text(analyzed_path, "rt") as f:
            # metadata is the first key; read a prefix rather than the whole file
            head = f.read(4000)
        import re
        m = re.search(r'"scraped_at":\s*"([^"]+)"', head)
        if not m:
            return os.path.getmtime(analyzed_path)
        dt = datetime.fromisoformat(m.group(1).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return 0.0


def scrape_school(slug, name, max_profs, school_id=None):
    """Scrape a single school."""
    raw_path = os.path.join(DATA_DIR, f"{slug}.json")
    analyzed_path_ = analyzed_path(DATA_DIR, slug, prefer_existing=False)

    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"  Slug: {slug} | Max professors: {max_profs}" + (f" | ID: {school_id}" if school_id else ""))
    print(f"{'='*60}")

    # Step 1: Scrape
    print(f"\n[1/2] Scraping from RateMyProfessor...")
    t0 = time.time()
    cmd = [sys.executable, SCRAPER, "--output", raw_path]
    if max_profs is not None and max_profs > 0:
        cmd.extend(["--max-professors", str(max_profs)])
    if school_id:
        cmd.extend(["--school-id", school_id, "--school", name])
    else:
        cmd.extend(["--school", name])
    result = subprocess.run(cmd, capture_output=True, text=True)
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
         "--output", analyzed_path_],
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
        data = load_json(analyzed_path_)
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

    for slug, (name, max_p, sid) in sorted(DEFAULT_SCHOOLS.items()):
        analyzed = analyzed_path(DATA_DIR, slug)
        if os.path.exists(analyzed):
            try:
                meta = load_json(analyzed).get("metadata", {})
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
    parser.add_argument("--max-professors", type=int, default=None,
                        help="Override max professors per school (0 = unlimited)")
    parser.add_argument("--batch", type=str, default=None,
                        help="Run only a slice of the school list as 'i/N' (e.g. '0/3' = first third). "
                             "Use this to spread a nightly refresh across multiple days or jobs.")
    parser.add_argument("--stale-days", type=int, default=None,
                        help="Only refresh schools whose analyzed file is older than this many days.")
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
        schools_to_scrape.append((slug, args.add, max_p, None))

    elif args.schools:
        # Specific schools by slug
        for slug in args.schools.split(","):
            slug = slug.strip().lower()
            if slug in DEFAULT_SCHOOLS:
                name, max_p, sid = DEFAULT_SCHOOLS[slug]
                schools_to_scrape.append((slug, name, args.max_professors or max_p, sid))
            else:
                print(f"Unknown slug: {slug}. Use --list to see available schools.")

    elif args.refresh:
        # Re-scrape all that have existing data
        for slug, (name, max_p, sid) in DEFAULT_SCHOOLS.items():
            analyzed = analyzed_path(DATA_DIR, slug)
            if os.path.exists(analyzed):
                schools_to_scrape.append((slug, name, args.max_professors or max_p, sid))

    elif args.all:
        # Scrape everything
        for slug, (name, max_p, sid) in DEFAULT_SCHOOLS.items():
            schools_to_scrape.append((slug, name, args.max_professors or max_p, sid))

    else:
        # Default: scrape schools that don't have data yet
        for slug, (name, max_p, sid) in DEFAULT_SCHOOLS.items():
            analyzed = analyzed_path(DATA_DIR, slug)
            if not os.path.exists(analyzed):
                schools_to_scrape.append((slug, name, args.max_professors or max_p, sid))

    # Apply --batch i/N rotation: deterministic slicing by slug so each school
    # always lands in the same batch across runs. The i-th batch out of N gets
    # roughly len/N schools, slugs sorted alphabetically. This is how the
    # nightly GitHub Action rotates through every school over several days.
    if args.batch:
        try:
            i_str, n_str = args.batch.split("/")
            i, n = int(i_str), int(n_str)
            assert n > 0 and 0 <= i < n
        except (ValueError, AssertionError):
            print(f"--batch must be 'i/N' with 0 <= i < N; got {args.batch!r}")
            return
        schools_to_scrape.sort(key=lambda x: x[0])
        schools_to_scrape = [s for idx, s in enumerate(schools_to_scrape) if idx % n == i]

    # --stale-days: keep only schools scraped more than the cutoff ago, read
    # from metadata.scraped_at (file mtime is the checkout time in CI).
    if args.stale_days is not None:
        cutoff = time.time() - args.stale_days * 86400
        kept = []
        for slug, name, max_p, sid in schools_to_scrape:
            if _scraped_at_epoch(analyzed_path(DATA_DIR, slug)) < cutoff:
                kept.append((slug, name, max_p, sid))
            else:
                print(f"  skip (fresh): {slug}")
        schools_to_scrape = kept

    # --max-professors 0 means unlimited; pass None to the scraper so it
    # discovers every rated professor.
    if args.max_professors == 0:
        schools_to_scrape = [(s, n, None, sid) for s, n, _, sid in schools_to_scrape]

    if not schools_to_scrape:
        print("Nothing to scrape. Use --list to see status, or --all to scrape everything.")
        return

    print(f"\nWill scrape {len(schools_to_scrape)} schools:")
    for slug, name, max_p, sid in schools_to_scrape:
        print(f"  • {name} ({slug}, max {max_p} profs{', ID override' if sid else ''})")

    total_start = time.time()
    success = 0
    failed = 0

    for slug, name, max_p, sid in schools_to_scrape:
        try:
            if scrape_school(slug, name, max_p, school_id=sid):
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
