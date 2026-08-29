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


def published_professor_counts() -> tuple[dict[str, int], set[str]]:
    """(slug -> total_professors for analyzed assets already on the release,
    slugs whose count could not be read). Reads a 64 KB prefix of each asset."""
    import fetch_data
    import io
    counts: dict[str, int] = {}
    unreadable: set[str] = set()
    try:
        assets = fetch_data.list_assets()
    except Exception as e:
        print(f"  WARNING: cannot list release assets ({e!r})")
        return counts, unreadable
    for name, meta in assets.items():
        if not name.endswith("_analyzed.json.gz"):
            continue
        slug = name[: -len("_analyzed.json.gz")]
        try:
            with fetch_data._get(meta["url"], headers={"Accept": "application/octet-stream",
                                                        "Range": "bytes=0-65535"}) as r:
                head = r.read(65536)
            try:
                text = gzip.GzipFile(fileobj=io.BytesIO(head)).read(8000).decode("utf-8", "ignore")
            except EOFError:
                text = gzip.decompress(head[:0]) if False else ""  # short body: fall through
                text = _partial_gunzip(head)
            cut = text.find('"analysis"')
            if cut <= 0:
                raise ValueError("no analysis key in header")
            counts[slug] = json.loads(text[:cut] + '"analysis": []}')["metadata"].get("total_professors", 0)
        except Exception as e:
            print(f"  WARNING: published count for {slug} unreadable ({e!r})")
            unreadable.add(slug)
    return counts, unreadable


def _partial_gunzip(head: bytes, want: int = 8000) -> str:
    """Decompress as much as a truncated gzip prefix allows."""
    import zlib
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)
    return d.decompress(head, want).decode("utf-8", "ignore")


RESERVED_SLUG_SUFFIXES = ("_schedule", "_analyzed")


def valid_slug(slug: str) -> bool:
    """Slugs are file-name prefixes; a slug ending in a reserved suffix would
    be misclassified as a schedule or analyzed asset."""
    return bool(slug) and not slug.endswith(RESERVED_SLUG_SUFFIXES) and "." not in slug and "/" not in slug


def collect(schools: set[str] | None, tmpdir: str, include_schedules: bool = False) -> list[tuple[str, str]]:
    """(asset_name, local_path) for everything to upload, one entry per asset
    name. Raw scrapes: a plain `data/<slug>.json` (a fresh scrape) shadows a
    `data/<slug>.json.gz` (the copy fetched from the release), matching
    datafiles.list_raw, and is gzipped into tmpdir. Schedules are only
    included on request so the nightly job cannot overwrite the schedule the
    UMD workflow just published."""
    by_name: dict[str, str] = {}
    raw_plain: dict[str, str] = {}
    raw_gz: dict[str, str] = {}
    for path in sorted(glob.glob(os.path.join(DATA_DIR, "*"))):
        name = os.path.basename(path)
        if name.endswith("_schedule.json"):
            slug = name[: -len("_schedule.json")]
            if include_schedules and (schools is None or slug in schools):
                by_name[name] = path
        elif name.endswith("_analyzed.json.gz"):
            slug = name[: -len("_analyzed.json.gz")]
            if schools is None or slug in schools:
                by_name[name] = path
        elif name.endswith("_analyzed.json"):
            continue  # legacy plain analyzed file; regenerate as .gz instead
        elif name.endswith(".json.gz"):
            raw_gz[name[: -len(".json.gz")]] = path
        elif name.endswith(".json"):
            raw_plain[name[: -len(".json")]] = path
    for slug, path in raw_gz.items():
        if slug in raw_plain:
            continue  # plain shadows gz
        if schools is None or slug in schools:
            by_name[slug + ".json.gz"] = path
    for slug, path in raw_plain.items():
        if schools is None or slug in schools:
            gz = os.path.join(tmpdir, slug + ".json.gz")
            with open(path, "rb") as f_in, gzip.open(gz, "wb", compresslevel=6) as f_out:
                shutil.copyfileobj(f_in, f_out)
            by_name[slug + ".json.gz"] = gz
    return sorted(by_name.items())


def write_manifest(tmpdir: str, uploaded: list[tuple[str, str]]) -> str:
    """manifest.json: every asset name with its byte size, so fetch_data can
    resolve assets through the direct download URL without the GitHub API
    (no rate limit, no token). Merged over the previous manifest so partial
    publishes keep the full list."""
    import fetch_data
    try:
        prev = fetch_data.load_manifest()
    except Exception:
        # First publish: seed from the releases API so the manifest is complete.
        try:
            prev = {n: {"size": m["size"]} for n, m in fetch_data.list_assets().items()
                    if n not in ("manifest.json",)}
        except Exception:
            prev = {}
    entries = dict(prev)
    for name, path in uploaded:
        entries[name] = {"size": os.path.getsize(path)}
    out = os.path.join(tmpdir, "manifest.json")
    with open(out, "w") as f:
        json.dump({"tag": TAG, "assets": entries}, f, indent=0, sort_keys=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--schools", default="", help="comma-separated slugs (default: everything in data/)")
    ap.add_argument("--create", action="store_true", help="create the release if missing")
    ap.add_argument("--no-guard", action="store_true", help="skip the professor-count guard")
    ap.add_argument("--model", action="store_true", help="also upload models/nb_topic_model.json")
    ap.add_argument("--schedule-only", default="", metavar="SLUG",
                    help="upload only data/<SLUG>_schedule.json")
    ap.add_argument("--with-schedules", action="store_true",
                    help="include data/*_schedule.json in a normal publish (the initial upload)")
    args = ap.parse_args()
    schools = {s.strip() for s in args.schools.split(",") if s.strip()} or None
    for slug in (schools or set()) | ({args.schedule_only} if args.schedule_only else set()):
        if not valid_slug(slug):
            print(f"refusing slug {slug!r}: reserved suffix or bad characters", file=sys.stderr)
            return 2

    if not release_exists():
        if not args.create:
            print(f"release {TAG} does not exist on {REPO}; pass --create", file=sys.stderr)
            return 2
        create_release()
        print(f"created release {TAG}")

    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        if args.schedule_only:
            path = os.path.join(DATA_DIR, f"{args.schedule_only}_schedule.json")
            items = [(os.path.basename(path), path)] if os.path.exists(path) else []
        else:
            items = collect(schools, tmp, include_schedules=args.with_schedules)
        if args.model:
            model = os.path.join(ROOT, "models", "nb_topic_model.json")
            if os.path.exists(model):
                items.append(("nb_topic_model.json", model))
        names = [n for n, _ in items]
        assert len(names) == len(set(names)), f"duplicate asset names: {sorted(set(n for n in names if names.count(n) > 1))}"

        analyzed_items = [n for n, _ in items if n.endswith("_analyzed.json.gz")]
        prev, unreadable = ({}, set())
        if analyzed_items and not args.no_guard:
            prev, unreadable = published_professor_counts()
            if not prev and not unreadable:
                print("  WARNING: could not list published assets; the professor-count guard is inactive")
        skipped = []
        upload = []
        for name, path in items:
            if name.endswith("_analyzed.json.gz") and not args.no_guard:
                slug = name[: -len("_analyzed.json.gz")]
                if slug in unreadable:
                    # Fail closed: an unreadable published count must not be treated as 0.
                    skipped.append((slug, None, None))
                    continue
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
            if n_new is None:
                print(f"  GUARD: not replacing {slug}: published professor count could not be read")
            else:
                print(f"  GUARD: not replacing {slug}: {n_new} professors vs {n_old} published")
        # gh accepts many files per call; keep batches modest for clearer logs
        for i in range(0, len(upload), 10):
            batch = upload[i:i + 10]
            gh("release", "upload", TAG, "--repo", REPO, "--clobber", *[p for _, p in batch])
            for name, path in batch:
                print(f"  uploaded {name}  {os.path.getsize(path) / 1e6:.1f} MB", flush=True)
        if upload:
            manifest = write_manifest(tmp, upload)
            gh("release", "upload", TAG, "--repo", REPO, "--clobber", manifest)
            print("  uploaded manifest.json")
    print(f"{len(upload)} asset(s) published to {REPO}@{TAG} in {time.time() - t0:.0f}s"
          + (f", {len(skipped)} held back by the guard" if skipped else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
