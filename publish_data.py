"""
Upload data files to the rolling GitHub release `data-latest`.

    python publish_data.py                    # every data/*.json.gz and data/*_schedule.json
    python publish_data.py --schools umich    # one school's raw + analyzed
    python publish_data.py --create           # create the release if it does not exist

Raw scrapes are gzipped on the way up (`data/<slug>.json` -> `<slug>.json.gz`).
Uploads use the GitHub CLI (`gh release upload --clobber`), so `gh` must be
authenticated (GH_TOKEN in Actions).

Guard: an analyzed asset is not replaced when the new file has fewer than
half the professors of the one already published. A capped or rate-limited
scrape must never overwrite a good snapshot.
"""

from __future__ import annotations

import argparse
import glob
import gzip
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

from datafiles import load_json, read_metadata

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
REPO = os.environ.get("PROFINSIGHT_DATA_REPO", "thesanatt/profinsight")
TAG = os.environ.get("PROFINSIGHT_DATA_TAG", "data-latest")


def gh(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=check)


def release_exists() -> bool:
    return gh("release", "view", TAG, "--repo", REPO, check=False).returncode == 0


def create_release() -> None:
    gh("release", "create", TAG, "--repo", REPO, "--title", "Data snapshot (rolling)",
       "--notes", "Rolling snapshot of scraped and analyzed data. Overwritten by the nightly "
                  "workflows; see docs/DATA.md. Not a code release.")


def published_professor_counts() -> dict[str, int]:
    """slug -> total_professors for analyzed assets already on the release,
    read from a small header download of each (a few KB per school)."""
    import fetch_data
    counts = {}
    try:
        assets = fetch_data.list_assets()
    except Exception:
        return counts
    for name, meta in assets.items():
        if not name.endswith("_analyzed.json.gz"):
            continue
        slug = name[: -len("_analyzed.json.gz")]
        try:
            with fetch_data._get(meta["url"], headers={"Accept": "application/octet-stream",
                                                        "Range": "bytes=0-65535"}) as r:
                head = r.read(65536)
            text = gzip.GzipFile(fileobj=__import__("io").BytesIO(head)).read(8000).decode("utf-8", "ignore")
            cut = text.find('"analysis"')
            if cut > 0:
                counts[slug] = json.loads(text[:cut] + '"analysis": []}')["metadata"].get("total_professors", 0)
        except Exception:
            continue
    return counts


def collect(schools: set[str] | None, tmpdir: str) -> list[tuple[str, str]]:
    """(asset_name, local_path) for everything to upload. Raw plain files are
    gzipped into tmpdir first."""
    out = []
    for path in sorted(glob.glob(os.path.join(DATA_DIR, "*"))):
        name = os.path.basename(path)
        if name.endswith("_schedule.json"):
            slug = name[: -len("_schedule.json")]
            if schools is None or slug in schools:
                out.append((name, path))
        elif name.endswith("_analyzed.json.gz"):
            slug = name[: -len("_analyzed.json.gz")]
            if schools is None or slug in schools:
                out.append((name, path))
        elif name.endswith("_analyzed.json"):
            continue  # legacy plain analyzed file; regenerate as .gz instead
        elif name.endswith(".json.gz"):
            slug = name[: -len(".json.gz")]
            if schools is None or slug in schools:
                out.append((name, path))
        elif name.endswith(".json"):
            slug = name[: -len(".json")]
            if schools is None or slug in schools:
                gz = os.path.join(tmpdir, name + ".gz")
                with open(path, "rb") as f_in, gzip.open(gz, "wb", compresslevel=6) as f_out:
                    shutil.copyfileobj(f_in, f_out)
                out.append((name + ".gz", gz))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--schools", default="", help="comma-separated slugs (default: everything in data/)")
    ap.add_argument("--create", action="store_true", help="create the release if missing")
    ap.add_argument("--no-guard", action="store_true", help="skip the professor-count guard")
    ap.add_argument("--model", action="store_true", help="also upload models/nb_topic_model.json")
    ap.add_argument("--schedule-only", default="", metavar="SLUG",
                    help="upload only data/<SLUG>_schedule.json")
    args = ap.parse_args()
    schools = {s.strip() for s in args.schools.split(",") if s.strip()} or None

    if not release_exists():
        if not args.create:
            print(f"release {TAG} does not exist on {REPO}; pass --create", file=sys.stderr)
            return 2
        create_release()
        print(f"created release {TAG}")

    prev = {} if args.no_guard else published_professor_counts()
    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        if args.schedule_only:
            path = os.path.join(DATA_DIR, f"{args.schedule_only}_schedule.json")
            items = [(os.path.basename(path), path)] if os.path.exists(path) else []
        else:
            items = collect(schools, tmp)
        if args.model:
            model = os.path.join(ROOT, "models", "nb_topic_model.json")
            if os.path.exists(model):
                items.append(("nb_topic_model.json", model))
        skipped = []
        upload = []
        for name, path in items:
            if name.endswith("_analyzed.json.gz") and prev:
                slug = name[: -len("_analyzed.json.gz")]
                try:
                    n_new = read_metadata(path).get("total_professors", 0)
                except Exception:
                    n_new = 0
                n_old = prev.get(slug, 0)
                if n_old and n_new < 0.5 * n_old:
                    skipped.append((slug, n_new, n_old))
                    continue
            upload.append((name, path))
        for slug, n_new, n_old in skipped:
            print(f"  GUARD: not replacing {slug}: {n_new} professors vs {n_old} published")
        # gh accepts many files per call; keep batches modest for clearer logs
        for i in range(0, len(upload), 10):
            batch = upload[i:i + 10]
            gh("release", "upload", TAG, "--repo", REPO, "--clobber", *[p for _, p in batch])
            for name, path in batch:
                print(f"  uploaded {name}  {os.path.getsize(path) / 1e6:.1f} MB", flush=True)
    print(f"{len(upload)} asset(s) published to {REPO}@{TAG} in {time.time() - t0:.0f}s"
          + (f", {len(skipped)} held back by the guard" if skipped else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
