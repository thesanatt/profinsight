# 10 — UMD Schedule integration shipped

## What's new
Current-semester course schedule integration for UMD via **Testudo** (`app.testudo.umd.edu/soc`). Public endpoint, no auth, polite nightly scrape.

## Why UMD and not UMich (which the prior scoping doc recommended)
The UMich recommendation in `09_UMICH_SCHEDULE_SCOPING.md` was based on LSA CG being public. **Between when that doc was written (earlier today) and the actual attempt, `lsa.umich.edu/cg/` got fully gated behind Shibboleth SSO** — every URL now 302-redirects through `shibboleth.umich.edu/idp`. Plain `curl-cffi` impersonation, headless browser — none of it helps when the site is full SSO rather than a bot-mitigation challenge.

So the scoping doc's recommendation is stale. Pivoted to a school where:
1. Course schedule is genuinely public (Testudo: no auth, no 2FA, no SSO).
2. We already have RMP-side professor data.

Testudo fit both. PlanetTerp has been built on it for a decade; confirmed still public 2026-04-23.

## Architecture (pluggable per school)
- `umd_scheduler.py` — standalone scraper + matcher for UMD Testudo.
- `data/umd_schedule.json` — output: per-course section data with matched professor IDs.
- `api.py` — loads schedule with mtime-based cache; new endpoints:
  - `GET /api/{school}/schedule_status` — coverage stats for this school
  - `GET /api/{school}/teaching_now/{course_code}` — profs teaching this course, joined with ratings
  - `GET /api/{school}/professors/{id}` — existing endpoint, now enriched with `teaching_now` block when schedule is available
- Frontend: `TeachingNow` card on `ProfessorDetail`, silent when no schedule data.
- `.github/workflows/umd-schedule.yml` — nightly cron (04:30 UTC) that re-scrapes + commits.

## v1 known limitations (honest inventory)

### The `umd` slug in our data is actually UMBC, not UMD College Park
Root cause: `rmp_scraper.py` searched RateMyProfessors for "University of Maryland" and picked the first match, which was **UMBC (University of Maryland, Baltimore County)**. That's the `data/umd.json` professor list (413 profs). Testudo is **UMD College Park's** schedule. Different school. Different faculty.

**Consequence**: The current match rate is trivially low (2 matched profs teaching 7 courses) because the RMP data and the Testudo data are from different institutions. The matched ones (Howard Smead in History, Diana Rodriguez in Spanish) are profs whose names happen to overlap across both campuses.

**Fix (separate PR)**: Re-scrape RMP with UMD College Park's actual school ID. RMP's GraphQL API supports this — look up the College Park school ID manually (browse ratemyprofessors.com), then:
```
python rmp_scraper.py --school "University of Maryland" --school-id <COLLEGE_PARK_ID> --output data/umd.json --max-professors 1500
python bayesian_pipeline.py --input data/umd.json --output data/umd_analyzed.json
python umd_scheduler.py
```
This will raise the match rate dramatically. Expect 100-200+ matches instead of 2.

### LSA-/Testudo-only — no other schools
Only UMD (Testudo) has a scraper in v1. Other schools have RMP data but no schedule. The infrastructure is pluggable (per-school schedule JSON + mtime cache + generic API endpoints), so adding Berkeley (`classes.berkeley.edu`, public), UIUC (`courses.illinois.edu`, public), MIT (`student.mit.edu/catalog`, public), Purdue (`selfservice.mypurdue.purdue.edu`, public) each takes ~2 hours.

### Department scoping is strict
The matcher requires the RMP department to fuzzy-match the Testudo course prefix (e.g., CMSC → "Computer Science") at ratio ≥55. This is the fix for same-name collisions across departments (previously: "Michael Abrams (Math)" was wrongly matched to "Michael Abrams (Architecture)" teaching ARCH170). The tradeoff: department aliases will be missed. Manual-override file (`data/umd_name_overrides.json`) handles the long tail.

### Instructor "TBA" rows not yet surfaced to UI
Sections with no assigned instructor yet (placeholder TBA / Staff) are counted but not shown in the UI. Could be worth adding a "TBA — check back" tag.

## For the next session

Pick one:
1. **Fix UMD College Park data** (30 min). Re-scrape with the correct school_id. Match rate jumps to real numbers. Single highest-leverage fix.
2. **Add a second school** (2–3 h). Berkeley or UIUC recommended — both public. Replicate the `umd_scheduler.py` pattern with a new `{school}_scheduler.py`.
3. **UMich via API Directory** (multi-week). The proper path per the earlier scoping doc — request TeamDynamix credentials for the ScheduleBuilder API.

## How to test locally
```bash
# Scrape + match (takes ~4 min)
python umd_scheduler.py

# Start API
./deploy.sh dev

# Visit a matched prof in the UI
http://localhost:5173/#/school/umd/prof/VGVhY2hlci00Nzk1OQ==  # Howard Smead
```

A "Teaching Fall 2026" green card should appear at the top with `HIST200`, `HIST201`, `HIST266`, `HIST289V`, `HIST357` chips.
