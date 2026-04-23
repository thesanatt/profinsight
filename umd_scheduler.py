"""
ProfInsight — UMD Current-Term Schedule + Instructor Join
==========================================================

Scrapes UMD's public Testudo Schedule of Classes (no auth required) and joins
instructor-of-record names to professor IDs from `data/umd_analyzed.json`.
Produces `data/umd_schedule.json` which the API reads to annotate each
professor with the courses they're teaching this semester.

Why UMD and not UMich: UMich LSA CG moved behind SSO; Testudo is genuinely
public and has been PlanetTerp's data source for a decade.

Public endpoints used (all unauthenticated, GET-only):
  GET /soc/                                  — root; lists subjects + terms
  GET /soc/{term}/{subject}                  — course listing for a subject
  GET /soc/{term}/sections?courseIds=a,b,c   — batch sections with instructors

Architecture: pure curl-cffi + BeautifulSoup. No Playwright. No auth. No
heavy dep. Pure-Python name matching via Levenshtein (rapidfuzz).

Usage:
    python umd_scheduler.py                    # scrape current term + match
    python umd_scheduler.py --term 202601      # scrape a specific term (YYYYMM)
    python umd_scheduler.py --only-match       # just rebuild the join
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from curl_cffi import requests as cf
from bs4 import BeautifulSoup
from rapidfuzz import fuzz, process

TESTUDO_ROOT = "https://app.testudo.umd.edu/soc"
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

SCRAPE_DELAY = 0.25  # seconds between subject requests — polite throttle

# Term format: YYYY + MM where MM is {01=Spring, 05=Summer, 08=Fall, 12=Winter}.
TERM_LABELS = {"01": "Spring", "05": "Summer", "08": "Fall", "12": "Winter"}


def term_label(term_code: str) -> str:
    """202608 -> 'Fall 2026'."""
    if not re.match(r"^\d{6}$", term_code):
        return term_code
    year, mm = term_code[:4], term_code[4:]
    return f"{TERM_LABELS.get(mm, '')} {year}".strip()


# ─── subject + term discovery ──────────────────────────────────────────────

def discover_subjects_and_current_term() -> tuple[list[tuple[str, str]], str]:
    """Fetch the Testudo root and return (subjects, current_term).

    subjects is a list of (code, name) pairs.
    current_term is the default-selected term code (e.g. '202608').
    """
    r = cf.get(f"{TESTUDO_ROOT}/", impersonate="chrome", timeout=25)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    subjects: list[tuple[str, str]] = []
    for el in soup.select("[class*=prefix]"):
        txt = el.get_text(" ", strip=True)
        m = re.match(r"([A-Z]{2,5})\s+(.*)", txt)
        if m:
            subjects.append((m.group(1), m.group(2).strip()))

    # Dedupe
    seen = set()
    uniq_subjects = []
    for code, name in subjects:
        if code in seen:
            continue
        seen.add(code)
        uniq_subjects.append((code, name))

    # Current term: selected option on the term dropdown
    current_term = None
    term_sel = soup.select_one("#term-id-input")
    if term_sel:
        for opt in term_sel.find_all("option"):
            if opt.get("selected") is not None:
                current_term = opt.get("value")
                break
    return uniq_subjects, current_term or _guess_current_term()


def _guess_current_term() -> str:
    """Fallback when the dropdown parse fails: guess the current academic term."""
    now = datetime.now()
    year = now.year
    month = now.month
    if month in (8, 9, 10, 11, 12):
        return f"{year}08"
    if month in (1, 2, 3, 4, 5):
        return f"{year}01"
    return f"{year}05"  # summer


# ─── course + section scraping ─────────────────────────────────────────────

def list_course_ids_for_subject(term: str, subject: str) -> list[str]:
    """Fetch the per-subject course-listing page; return all course IDs."""
    url = f"{TESTUDO_ROOT}/{term}/{subject}"
    r = cf.get(url, impersonate="chrome", timeout=25)
    if r.status_code != 200:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    ids = []
    for el in soup.select(".course-id"):
        txt = el.get_text(strip=True)
        if txt:
            ids.append(txt)
    return ids


_JUNK_INSTRUCTOR_RE = re.compile(r"^[\s,;:/\-\|.]+$")
_JUNK_INSTRUCTOR_VALUES = {"", "tba", "staff", "instructor: tba", "instructor tba", "t.b.a."}


def _is_junk_instructor(name: str) -> bool:
    """Filter obvious non-names: empty, punctuation-only, or TBA-style placeholders."""
    s = name.strip().lower()
    if not s:
        return True
    if s in _JUNK_INSTRUCTOR_VALUES:
        return True
    if _JUNK_INSTRUCTOR_RE.match(s):
        return True
    # Must contain at least one letter
    if not re.search(r"[A-Za-z]", s):
        return True
    return False


@dataclass
class SectionRecord:
    course_id: str            # e.g. "CMSC131"
    section_id: str           # e.g. "0101"
    instructors: list[str]    # e.g. ["Elias Gonzalez"]
    meeting: str              # short free-form "MWF 10:00am - 10:50am IRB 0324"
    seats_total: Optional[int]
    seats_open: Optional[int]
    waitlist: Optional[int]

    def as_dict(self) -> dict:
        return self.__dict__


def fetch_sections_for_courses(term: str, course_ids: list[str]) -> list[SectionRecord]:
    """Batch-request sections for up to N course IDs. Testudo accepts up to
    ~200 IDs in the querystring; we batch to 25 to be safe."""
    out: list[SectionRecord] = []
    if not course_ids:
        return out

    BATCH = 25
    for i in range(0, len(course_ids), BATCH):
        batch = course_ids[i:i + BATCH]
        url = f"{TESTUDO_ROOT}/{term}/sections?courseIds={','.join(batch)}"
        r = cf.get(url, impersonate="chrome", timeout=30)
        if r.status_code != 200:
            continue
        soup = BeautifulSoup(r.text, "html.parser")

        for course_block in soup.select(".course-sections"):
            cid = course_block.get("id", "").strip()
            if not cid:
                continue
            for sec in course_block.select(".section"):
                sec_id_el = sec.select_one(".section-id")
                sec_id = sec_id_el.get_text(strip=True) if sec_id_el else ""

                # Each instructor lives in <span class="section-instructor">.
                # The outer .section-instructors is just the wrapper. If the
                # wrapper exists but has no .section-instructor children the
                # section has no assigned instructor.
                instructors: list[str] = []
                instr_wrap = sec.select_one(".section-instructors")
                if instr_wrap:
                    for inner in instr_wrap.select(".section-instructor"):
                        name = inner.get_text(strip=True)
                        # Skip punctuation-only / placeholder names
                        if name and not _is_junk_instructor(name):
                            instructors.append(name)
                    # Fallback for (rare) inline-text instructor blobs
                    if not instructors:
                        raw = instr_wrap.get_text(" ", strip=True)
                        if raw and not _is_junk_instructor(raw):
                            instructors.append(raw)

                # Seats
                seats_total = seats_open = waitlist = None
                seats_el = sec.select_one(".total-seats-count")
                if seats_el:
                    try:
                        seats_total = int(seats_el.get_text(strip=True))
                    except ValueError:
                        pass
                open_el = sec.select_one(".open-seats-count")
                if open_el:
                    try:
                        seats_open = int(open_el.get_text(strip=True))
                    except ValueError:
                        pass
                wait_el = sec.select_one(".waitlist-count")
                if wait_el:
                    try:
                        waitlist = int(wait_el.get_text(strip=True))
                    except ValueError:
                        pass

                # Meeting summary
                meet_parts = []
                for m in sec.select(".class-days-container .section-days, .class-time, .class-room-container"):
                    t = m.get_text(" ", strip=True)
                    if t:
                        meet_parts.append(t)
                meeting = " ".join(meet_parts) if meet_parts else ""

                out.append(SectionRecord(
                    course_id=cid,
                    section_id=sec_id,
                    instructors=instructors,
                    meeting=meeting,
                    seats_total=seats_total,
                    seats_open=seats_open,
                    waitlist=waitlist,
                ))
    return out


def scrape_full_term(term: str) -> dict:
    """Scrape the whole term. Returns a dict keyed by course_id → list of sections."""
    subjects, detected_term = discover_subjects_and_current_term()
    term = term or detected_term
    print(f"[umd_scheduler] term {term} ({term_label(term)}) — {len(subjects)} subjects")

    all_sections: list[SectionRecord] = []
    for idx, (code, name) in enumerate(subjects):
        course_ids = list_course_ids_for_subject(term, code)
        if not course_ids:
            continue
        secs = fetch_sections_for_courses(term, course_ids)
        all_sections.extend(secs)
        if idx % 15 == 0 or idx == len(subjects) - 1:
            print(f"  [{idx+1:>3}/{len(subjects)}] {code:5}  +{len(secs)} sections  (running total {len(all_sections)})")
        time.sleep(SCRAPE_DELAY)

    # Group by course_id
    by_course: dict[str, list[dict]] = {}
    for s in all_sections:
        by_course.setdefault(s.course_id, []).append(s.as_dict())

    return {
        "school": "umd",
        "source": "testudo",
        "term": term,
        "term_label": term_label(term),
        "scraped_at": datetime.now().isoformat(),
        "n_courses": len(by_course),
        "n_sections": len(all_sections),
        "courses": by_course,
        # Subject-prefix → full subject name. Used by build_joined_schedule
        # to scope name matches to the plausible academic department, which
        # is the fix for same-name collisions across departments.
        "subjects": dict(subjects),
    }


# ─── instructor-name → professor-id join ───────────────────────────────────

_NAME_NORMALIZERS = (
    (re.compile(r"\b(Dr|Prof|Professor|Mr|Mrs|Ms|Miss|PhD|Ph\.D)\.?\b", re.IGNORECASE), ""),
    (re.compile(r"\s+"), " "),
)


def _normalize_name(name: str) -> str:
    out = name.strip()
    for pat, repl in _NAME_NORMALIZERS:
        out = pat.sub(repl, out)
    return out.lower().strip()


def _build_prof_index(analyzed_path: str) -> tuple[list[dict], dict]:
    """Load the UMD analyzed JSON and build a fast lookup from normalized
    'first last' → professor record."""
    with open(analyzed_path) as f:
        data = json.load(f)
    profs = data.get("analysis", [])

    index = {}
    for p in profs:
        name = p.get("name", "")
        norm = _normalize_name(name)
        if norm:
            index.setdefault(norm, p)
    return profs, index


def match_instructor_to_prof(
    instructor_name: str,
    profs_by_name: dict,
    all_profs: list[dict],
    threshold: int = 90,
    expected_department: Optional[str] = None,
    dept_threshold: int = 55,
) -> Optional[dict]:
    """Match a scraped instructor name to a professor record. Returns the
    matched prof or None.

    Strategy (in order):
      1. Exact normalized first-last AND department plausibility check.
      2. Last-name + first-initial within the expected department.
      3. rapidfuzz token_set_ratio ≥ threshold, department-scoped when possible.

    `expected_department` comes from the course prefix (e.g. MATH → Mathematics).
    When provided, a match is only accepted if the candidate prof's department
    fuzzy-matches the expected subject ≥ `dept_threshold`. This is the fix for
    same-name collisions across departments (e.g. two Michael Abramses).
    """
    norm = _normalize_name(instructor_name)
    if not norm:
        return None

    def dept_ok(prof: dict) -> bool:
        if not expected_department:
            return True  # no signal — accept
        rmp_dept = (prof.get("department") or "").strip().lower()
        if not rmp_dept:
            return False
        score = fuzz.partial_ratio(rmp_dept, expected_department.lower())
        return score >= dept_threshold

    # Step 1: exact normalized match, dept-gated
    if norm in profs_by_name:
        cand = profs_by_name[norm]
        if dept_ok(cand):
            return cand

    # Handle "Last, First" → "First Last"
    if "," in norm:
        last, first = [s.strip() for s in norm.split(",", 1)]
        candidate = f"{first} {last}"
        if candidate in profs_by_name:
            cand = profs_by_name[candidate]
            if dept_ok(cand):
                return cand
        norm_for_fuzz = candidate
    else:
        norm_for_fuzz = norm

    # Step 2: last-name exact + first-initial, dept-gated
    parts = norm_for_fuzz.split()
    if len(parts) >= 2:
        first_initial, last = parts[0][0], parts[-1]
        hits = [p for k, p in profs_by_name.items()
                if k.split() and k.split()[-1] == last and k.split()[0][0] == first_initial]
        dept_hits = [p for p in hits if dept_ok(p)]
        if len(dept_hits) == 1:
            return dept_hits[0]
        if len(hits) == 1 and not expected_department:
            return hits[0]

    # Step 3: fuzzy within dept-matching candidates
    if expected_department:
        candidates = {k: p for k, p in profs_by_name.items() if dept_ok(p)}
    else:
        candidates = profs_by_name
    if candidates:
        names = list(candidates.keys())
        match = process.extractOne(norm_for_fuzz, names, scorer=fuzz.token_set_ratio)
        if match and match[1] >= threshold:
            return candidates[match[0]]

    return None


def _subject_name_for_prefix(schedule: dict, prefix: str) -> Optional[str]:
    return schedule.get("subjects", {}).get(prefix)


def build_joined_schedule(
    schedule: dict,
    analyzed_path: str,
    overrides_path: Optional[str] = None,
) -> dict:
    """Walk the scraped schedule and attach a professor_id wherever we can
    match. Persist a list of unmatched instructor names for review."""
    profs_list, profs_by_name = _build_prof_index(analyzed_path)

    overrides: dict[str, str] = {}
    if overrides_path and os.path.exists(overrides_path):
        with open(overrides_path) as f:
            overrides = json.load(f)

    matched = 0
    unmatched = {}
    prof_teaching: dict[str, set[str]] = {}

    for course_id, sections in schedule["courses"].items():
        # Extract the subject prefix (letters at the start of the course id).
        m = re.match(r"^([A-Z]+)", course_id)
        subject_prefix = m.group(1) if m else None
        expected_dept = _subject_name_for_prefix(schedule, subject_prefix) if subject_prefix else None

        for s in sections:
            matched_ids: list[str] = []
            for instr_name in s.get("instructors", []):
                if _is_junk_instructor(instr_name):
                    continue
                if instr_name in overrides:
                    prof = next((p for p in profs_list if p.get("professor_id") == overrides[instr_name]), None)
                else:
                    prof = match_instructor_to_prof(
                        instr_name, profs_by_name, profs_list,
                        expected_department=expected_dept,
                    )
                if prof:
                    matched += 1
                    pid = prof.get("professor_id")
                    matched_ids.append(pid)
                    prof_teaching.setdefault(pid, set()).add(course_id)
                else:
                    unmatched[instr_name] = unmatched.get(instr_name, 0) + 1
            s["matched_professor_ids"] = matched_ids

    schedule["match_stats"] = {
        "matched_instructor_assignments": matched,
        "distinct_profs_teaching": len(prof_teaching),
        "unmatched_instructor_names": sorted(unmatched.items(), key=lambda x: -x[1])[:50],
        "n_unmatched_total": len(unmatched),
    }
    schedule["teaching_now_by_prof"] = {pid: sorted(courses) for pid, courses in prof_teaching.items()}
    return schedule


# ─── main ──────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Scrape UMD Testudo + match instructors.")
    ap.add_argument("--term", type=str, default=None,
                    help="Term code like 202608 (Fall 2026). Omit to use Testudo's current term.")
    ap.add_argument("--output", type=str, default=os.path.join(DATA_DIR, "umd_schedule.json"))
    ap.add_argument("--analyzed", type=str, default=os.path.join(DATA_DIR, "umd_analyzed.json"))
    ap.add_argument("--overrides", type=str, default=os.path.join(DATA_DIR, "umd_name_overrides.json"))
    ap.add_argument("--only-match", action="store_true",
                    help="Skip scraping; re-run the join against an existing umd_schedule.json.")
    args = ap.parse_args()

    if args.only_match:
        if not os.path.exists(args.output):
            print(f"[umd_scheduler] {args.output} missing — nothing to re-match.")
            return 1
        with open(args.output) as f:
            schedule = json.load(f)
    else:
        schedule = scrape_full_term(args.term)
    if not os.path.exists(args.analyzed):
        print(f"[umd_scheduler] {args.analyzed} missing — run bayesian_pipeline on umd first.")
        return 2

    schedule = build_joined_schedule(schedule, args.analyzed, args.overrides)

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(schedule, f, indent=2, ensure_ascii=False)

    stats = schedule["match_stats"]
    print(f"\n[umd_scheduler] wrote {args.output}")
    print(f"  term: {schedule['term_label']} ({schedule['term']})")
    print(f"  courses: {schedule['n_courses']}, sections: {schedule['n_sections']}")
    print(f"  matched instructor assignments: {stats['matched_instructor_assignments']}")
    print(f"  distinct profs teaching this term: {stats['distinct_profs_teaching']}")
    print(f"  unmatched instructor names: {stats['n_unmatched_total']}")
    if stats["unmatched_instructor_names"]:
        print(f"  top unmatched (add to {args.overrides} for manual join):")
        for name, n in stats["unmatched_instructor_names"][:10]:
            print(f"    {n:>3}× {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
