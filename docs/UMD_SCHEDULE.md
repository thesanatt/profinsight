# 10 — UMD Schedule integration shipped

## What's new
Current-semester course schedule integration for UMD via **Testudo** (`app.testudo.umd.edu/soc`). Public endpoint, no auth, polite nightly scrape.

## Why UMD, not UMich
The earlier scoping doc (`09_UMICH_SCHEDULE_SCOPING.md`) recommended UMich's LSA CG. Between when that doc was written and the attempt, **`lsa.umich.edu/cg/` got fully gated behind Shibboleth SSO** — every URL now 302-redirects through `shibboleth.umich.edu/idp`. No headless-browser trick helps when the wall is full SSO rather than CF bot-mitigation. Pivoted to UMD Testudo, which is still genuinely public (PlanetTerp has been built on it for a decade).

## Architecture (pluggable per school)
- `umd_scheduler.py` — Testudo scraper + matcher.
- `data/umd_schedule.json` — scraped output, joined with professor IDs.
- `api.py` — schedule with mtime cache; endpoints:
  - `GET /api/{school}/schedule_status`
  - `GET /api/{school}/teaching_now/{course_code}`
  - `GET /api/{school}/professors/{id}` now enriched with `teaching_now`
- Frontend: `TeachingNow` card on `ProfessorDetail` (silent when no schedule).
- `.github/workflows/umd-schedule.yml` — nightly 04:30 UTC cron.

## Data correction (shipped in this PR)

### Bug
Our `umd` slug was actually **UMBC** (University of Maryland, Baltimore County), not UMD College Park — `rmp_scraper.py` had searched "University of Maryland" and picked the first RMP match, which is UMBC.

### Fix
- Renamed the old UMBC data to `data/umbc.json` + `data/umbc_analyzed.json` under a new `umbc` slug. Preserved, not lost.
- Re-scraped UMD College Park with the correct school_id `U2Nob29sLTEyNzA=` (from RMP's GraphQL search). **912 professors**, 13,927 reviews.
- Re-ran Bayesian pipeline + schedule matcher.
- Updated `bulk_update.py` DEFAULT_SCHOOLS to pin both UMD and UMBC school_ids so nightly runs don't regress.

### Match quality — before / after
|           | before (UMBC mismatch) | after (College Park) |
|-----------|------------------------|----------------------|
| matched instructor assignments | 15 | **1,834** (2,232 after the Aug 2026 matcher rewrite) |
| distinct profs teaching this term | 2 | **428** (455 after the rewrite) |
| unmatched instructors | 2,777 | 2,417 (2,643 distinct names on the Aug 2026 schedule, 8,465 sections) |

Highly-reviewed profs now matching (spot check):
- Bonnie Dixon (Chemistry, 193 reviews) → BCHM462, CHEM231, CHEM241
- Michael Keller (Biology, 161 reviews) → BSCI170, BSCI180
- Larry Herman (CS, 130 reviews) → CMSC132
- Nelson Padua-Perez (CS, 119 reviews) → CMSC106, CMSC335
- Evan Golub (CS, 107 reviews) → CMSC434
- Howard Smead (History, 91 reviews) → HIST200–357
- Tracy Tomlinson (Psychology, 85 reviews) → PSYC200, PSYC425, PSYC440

## Remaining limitations

### Department scoping is strict
The matcher accepts an exact full-name match with a relaxed department gate (RMP department labels and Testudo subject names often disagree), and a last-name plus first-initial match only when it is unique and the department gate passes at a strict threshold. An optional manual override file (`data/umd_name_overrides.json`, instructor name to professor_id) is read if present; none is shipped.

### TBA instructor rows not surfaced to UI
Sections with unassigned instructors are counted but not shown. Worth a "TBA — check back" tag in a follow-up.

### Only UMD has a scraper
Other schools have RMP data but no schedule yet. Infrastructure is pluggable — per-school scraper file + generic API endpoints — so adding Berkeley (`classes.berkeley.edu`), UIUC (`courses.illinois.edu`), MIT (`student.mit.edu/catalog`), Purdue, etc. is a ~2h per-school follow-up. All four endpoints were verified public during recon.

## How to test locally
```bash
./deploy.sh dev
# Visit a matched prof (Larry Herman, CS):
http://localhost:5173/#/school/umd/prof/VGVhY2hlci01NDQ3MTg=
# "Teaching Fall 2026" green card with CMSC132 chip appears at the top.
```
