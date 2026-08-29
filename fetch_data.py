"""
Download the data snapshot from the GitHub release `data-latest`.

The repository no longer carries data files. The nightly workflows publish
every `data/<slug>.json.gz` (raw scrape), `data/<slug>_analyzed.json.gz`
(pipeline output) and `data/umd_schedule.json` as assets of one rolling
release, and this script pulls whatever a machine needs:

    python fetch_data.py                   # analyzed + schedule (what the API serves)
    python fetch_data.py --raw             # also raw scrapes (pipeline, harness, classifier)
    python fetch_data.py --schools umich,mit --raw   # a subset

api.py calls fetch_analyzed() at startup when data/ is empty, so a fresh
Render instance populates itself (about 120 MB, a few seconds from GitHub's CDN).

No token is needed for a public repository. Assets already on disk with the
same byte size are skipped, so re-running is cheap.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
REPO = os.environ.get("PROFINSIGHT_DATA_REPO", "thesanatt/profinsight")
TAG = os.environ.get("PROFINSIGHT_DATA_TAG", "data-latest")
API = f"https://api.github.com/repos/{REPO}/releases/tags/{TAG}"
# Direct download URLs need no API call, so they carry no rate limit and no token.
DOWNLOAD = f"https://github.com/{REPO}/releases/download/{TAG}"


def _get(url: str, headers: dict | None = None, retries: int = 3):
    h = {"User-Agent": "profinsight-fetch", "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        h["Authorization"] = f"Bearer {token}"
    if headers:
        h.update(headers)
    last = None
    for i in range(retries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=120)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            last = e
            time.sleep(2 ** i)
    raise RuntimeError(f"GET {url} failed: {last}")


def load_manifest() -> dict[str, dict]:
    """name -> {size} from the manifest asset publish_data.py maintains."""
    with _get(f"{DOWNLOAD}/manifest.json", headers={"Accept": "application/octet-stream"}) as r:
        m = json.load(r)
    return m.get("assets", {})


def list_assets() -> dict[str, dict]:
    """name -> {url, size} for every asset on the release. Prefers the
    manifest (direct URL, no API); falls back to the releases API."""
    try:
        manifest = load_manifest()
        if manifest:
            return {name: {"url": f"{DOWNLOAD}/{name}", "size": meta["size"]} for name, meta in manifest.items()}
    except Exception as e:
        print(f"[data] manifest unavailable ({e!r}); using the releases API", flush=True)
    with _get(API) as r:
        rel = json.load(r)
    return {a["name"]: {"url": a["browser_download_url"], "size": a["size"]} for a in rel.get("assets", [])}


def _want(name: str, raw: bool, analyzed: bool, schedule: bool, schools: set[str] | None) -> bool:
    if name in ("nb_topic_model.json", "manifest.json"):
        return False  # model is fetched by fetch_model(); the manifest is metadata
    if name.endswith("_schedule.json"):
        return schedule
    if name.endswith("_analyzed.json.gz"):
        if not analyzed:
            return False
        slug = name[: -len("_analyzed.json.gz")]
    elif name.endswith(".json.gz"):
        if not raw:
            return False
        slug = name[: -len(".json.gz")]
    else:
        return False
    return schools is None or slug in schools


def fetch(raw: bool = False, analyzed: bool = True, schedule: bool = True,
          schools: set[str] | None = None, data_dir: str = DATA_DIR, quiet: bool = False) -> list[str]:
    """Download the selected assets into data_dir. Returns the paths written."""
    os.makedirs(data_dir, exist_ok=True)
    assets = list_assets()
    written = []
    for name, meta in sorted(assets.items()):
        if not _want(name, raw, analyzed, schedule, schools):
            continue
        dest = os.path.join(data_dir, name)
        if os.path.exists(dest) and os.path.getsize(dest) == meta["size"]:
            continue
        tmp = dest + ".part"
        got = _download(meta["url"], tmp)
        if got != meta["size"]:
            os.remove(tmp)
            raise RuntimeError(f"{name}: downloaded {got} bytes, expected {meta['size']}")
        os.replace(tmp, dest)
        written.append(dest)
        if not quiet:
            print(f"  {name}  {meta['size'] / 1e6:.1f} MB", flush=True)
    return written


def _download(url: str, tmp: str) -> int:
    """Stream url to tmp; return bytes written. http.client returns b'' on a
    server-side close before Content-Length is reached, so callers compare
    the count against the expected size."""
    written = 0
    with _get(url, headers={"Accept": "application/octet-stream"}) as r, open(tmp, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            written += len(chunk)
    return written


def fetch_model(dest: str = os.path.join(ROOT, "models", "nb_topic_model.json")) -> bool:
    """Download the nightly-retrained topic classifier over the committed copy."""
    meta = list_assets().get("nb_topic_model.json")
    if not meta:
        return False
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    got = _download(meta["url"], dest + ".part")
    if got != meta["size"]:
        os.remove(dest + ".part")
        raise RuntimeError(f"nb_topic_model.json: downloaded {got} bytes, expected {meta['size']}")
    os.replace(dest + ".part", dest)
    return True


def fetch_analyzed(data_dir: str = DATA_DIR) -> list[str]:
    """What the API needs: analyzed files plus schedules."""
    return fetch(raw=False, analyzed=True, schedule=True, data_dir=data_dir, quiet=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", action="store_true", help="also download raw scrape files")
    ap.add_argument("--no-analyzed", action="store_true")
    ap.add_argument("--no-schedule", action="store_true")
    ap.add_argument("--schools", default="", help="comma-separated slugs (default: all)")
    ap.add_argument("--data-dir", default=DATA_DIR)
    ap.add_argument("--model", action="store_true", help="also download the latest topic classifier")
    args = ap.parse_args()
    schools = {s.strip() for s in args.schools.split(",") if s.strip()} or None
    t0 = time.time()
    written = fetch(raw=args.raw, analyzed=not args.no_analyzed, schedule=not args.no_schedule,
                    schools=schools, data_dir=args.data_dir)
    if args.model and fetch_model():
        written.append("models/nb_topic_model.json")
    print(f"{len(written)} file(s) downloaded from {REPO}@{TAG} in {time.time() - t0:.0f}s "
          f"({'nothing new' if not written else 'ok'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
