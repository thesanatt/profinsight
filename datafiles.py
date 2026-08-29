"""
Analyzed-file IO shared by the pipeline, API, matcher and workflows.

Analyzed JSON ships gzipped (`data/<slug>_analyzed.json.gz`): the 65-school set
is 844 MB as plain JSON and 118 MB gzipped, and the API only ever reads it.
Raw scrapes (`data/<slug>.json`) stay plain because the pipeline, the harness
and the classifier trainer read them and they are not part of the deploy path.

Every reader accepts either suffix so a checkout with old plain files keeps
working; writers pick the suffix from the path they are given.
"""

from __future__ import annotations

import glob
import gzip
import json
import os
from typing import Optional

ANALYZED_SUFFIXES = (".json.gz", ".json")


def is_gz(path: str) -> bool:
    return path.endswith(".gz")


def open_text(path: str, mode: str = "rt"):
    """Open plain or gzipped text; mode is 'rt' or 'wt'."""
    if is_gz(path):
        return gzip.open(path, mode, encoding="utf-8")
    return open(path, mode.replace("t", ""), encoding="utf-8")


def load_json(path: str):
    with open_text(path, "rt") as f:
        return json.load(f)


def dump_json(obj, path: str, indent: Optional[int] = None) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open_text(path, "wt") as f:
        json.dump(obj, f, indent=indent, ensure_ascii=False)


def analyzed_path(data_dir: str, slug: str, prefer_existing: bool = True) -> str:
    """Path of a school's analyzed file. Existing files win (gz first); a new
    file is written gzipped."""
    gz = os.path.join(data_dir, f"{slug}_analyzed.json.gz")
    plain = os.path.join(data_dir, f"{slug}_analyzed.json")
    if prefer_existing:
        if os.path.exists(gz):
            return gz
        if os.path.exists(plain):
            return plain
    return gz


def slug_from_analyzed(path: str) -> str:
    base = os.path.basename(path)
    for suf in ANALYZED_SUFFIXES:
        if base.endswith("_analyzed" + suf):
            return base[: -len("_analyzed" + suf)]
    return base


def list_analyzed(data_dir: str) -> list[str]:
    """All analyzed files, one per slug; gz shadows plain."""
    by_slug: dict[str, str] = {}
    for path in sorted(glob.glob(os.path.join(data_dir, "*_analyzed.json"))):
        by_slug[slug_from_analyzed(path)] = path
    for path in sorted(glob.glob(os.path.join(data_dir, "*_analyzed.json.gz"))):
        by_slug[slug_from_analyzed(path)] = path
    return [by_slug[k] for k in sorted(by_slug)]


def raw_path(data_dir: str, slug: str, prefer_existing: bool = True) -> str:
    """Path of a school's raw scrape. Plain `.json` is what the scraper writes;
    `.json.gz` is what the data release stores. Existing files win (plain first
    because it is the fresher one right after a scrape)."""
    plain = os.path.join(data_dir, f"{slug}.json")
    gz = plain + ".gz"
    if prefer_existing:
        if os.path.exists(plain):
            return plain
        if os.path.exists(gz):
            return gz
    return plain


def slug_from_raw(path: str) -> str:
    base = os.path.basename(path)
    for suf in (".json.gz", ".json"):
        if base.endswith(suf):
            return base[: -len(suf)]
    return base


def list_raw(data_dir: str) -> list[str]:
    """All raw scrape files, one per slug (plain shadows gz), excluding
    analyzed and schedule files."""
    by_slug: dict[str, str] = {}
    for pattern in ("*.json.gz", "*.json"):
        for path in sorted(glob.glob(os.path.join(data_dir, pattern))):
            base = os.path.basename(path)
            if "_analyzed.json" in base or base.endswith("_schedule.json"):
                continue
            by_slug[slug_from_raw(path)] = path
    return [by_slug[k] for k in sorted(by_slug)]


def read_metadata(path: str, max_chars: int = 8000) -> dict:
    """Parse just the leading metadata block without loading the whole file."""
    with open_text(path, "rt") as f:
        head = f.read(max_chars)
    cut = head.find('"analysis"')
    if cut == -1:
        raise ValueError("no analysis key in header")
    return json.loads(head[:cut] + '"analysis": []}').get("metadata", {})
