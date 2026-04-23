# 09 — UMich Current-Semester Schedule Scoping

Goal: For every course offered in the upcoming UMich term, know `(course_code, section_id, term, instructor_name)` so we can join against our existing 430-professor RMP dataset in `data/umich.json` and show "CS 461 Fall 2026 — Profs X/Y/Z, here are their reviews."

All findings below are as of 2026-04-23. Evidence-vs-guess is called out inline. No scraping was performed — HEAD requests only.

---

## TL;DR recommendation

**Build against the LSA Course Guide (`lsa.umich.edu/cg`) HTML pages using Playwright (headless Chromium) in a nightly GitHub Action. Effort: medium (~8–12h for v1).**

Reasoning:
1. It's the only source that is (a) publicly accessible without UM SSO, (b) has the exact fields we need (instructor + course code + section + term), and (c) has a stable, parameterized URL structure that the Michigan Daily has been scraping for years via cron (https://github.com/michigandaily/lsa-cg-scraper).
2. The Registrar's CSV dumps at `ro.umich.edu/system/files/timesched/pdf/FA2026.csv` would be perfect — documented schema, one-file-per-term — **but they now 302-redirect to Shibboleth OIDC login (verified via curl 2026-04-23).** Off the table unless we get UM sponsorship.
3. Atlas's ToS (https://atlas.ai.umich.edu/legal/) **explicitly prohibits** "robot, spider, site search/retrieval application, or other manual or automated process." Off the table.
4. UMich's internal API Directory has a `ScheduleBuilder` API (https://dir.api.it.umich.edu/docs/schedulebuilder/1/overview) but it requires a sponsored developer-org subscription through TeamDynamix + faculty endorsement. Possible Phase-2 route; not v1.
5. The lsa.umich.edu/cg site is now behind a Cloudflare bot challenge (`cf-mitigated: challenge` on HEAD, verified 2026-04-23) — plain `requests` won't work anymore, which is why Playwright is the right tool.

**Coverage caveat:** LSA CG only covers courses whose home school is LSA. Engineering (EECS, AEROSP, etc.), Ross, SI, Music, etc. are **not** in LSA CG. For those we need a second source — see "Open Questions." For a v1 MVP focused on CS/EECS specifically, this is the single biggest gap.

---

## Option-by-option analysis

### 1. UMich Atlas (https://atlas.ai.umich.edu)

- **Data available:** Yes, all of it — instructor, course code, section, enrollment history, grade distributions.
- **Access:** **Prohibited.** Verbatim from the Atlas ToS (https://atlas.ai.umich.edu/legal/): *"you will not use any robot, spider, site search/retrieval application, or other manual or automated process to access, retrieve, scrape, or index any portion of Software."* Also noncommercial/education-only. Atlas requires UM SSO to load anyway.
- **Scrape shape:** Would require Duo 2FA + a valid UM account per kvnshu/atlas-to-ics (https://github.com/kvnshu/atlas-to-ics, last relevant note Oct 2024 says "unnecessary now that Atlas has gcal export"). ldnelson16/atlas (https://github.com/ldnelson16/atlas) uses Selenium against logged-in sessions.
- **Maintenance:** N/A — don't do this.
- **Effort:** N/A. **Skip.**

### 2. LSA Course Guide (https://www.lsa.umich.edu/cg) — RECOMMENDED

- **Data available:** Yes. The Michigan Daily scraper's URL patterns (confirmed by WebFetch of https://github.com/michigandaily/lsa-cg-scraper/blob/main/scraper.py) pull:
  - Subject list: `https://www.lsa.umich.edu/cg/cg_subjectlist.aspx?termArray={TERM}&cgtype={ug|gr}&allsections=true`
  - Course search: `https://www.lsa.umich.edu/cg/cg_results.aspx?termArray={TERM}&cgtype={ug|gr}&department={DEP}&allsections=true&show=40`
  - Extracted fields: department, number, name, section, term, credits, mode, instructor, enrollment status, open seats, waitlist. **Exactly what we need.**
  - Term format example seen in the wild: `f_19_2260`, `w_26_2660` (unverified mapping but apparently `{f|w|sp|su}_{YY}_{4-digit-UM-term-id}`).
- **Legal/ToS:** No Atlas-style scraping prohibition found. robots.txt at https://www.lsa.umich.edu/robots.txt only disallows `/etc/`, `/libs/`, `/tests/` — **`/cg/` is not disallowed** (evidence: full robots fetched 2026-04-23). Michigan Daily has been running a cron against it since at least 2019. Still worth a one-line email to the LSA webteam as courtesy.
- **Scrape shape:** HTML parsing with BeautifulSoup. **Gotcha:** `www.lsa.umich.edu` now returns `HTTP 403 / cf-mitigated: challenge` to plain curl + browser-UA (verified 2026-04-23). Plain `requests` library may not cut it anymore. Use **Playwright headless Chromium** (~30 extra lines vs `requests`). Approx ~100 subjects × 1 index page + ~1–2 page-clicks per course page = a few thousand HTTP GETs per term. Throttle to ~1/sec to stay polite; total job time ~30–60 min.
- **Maintenance:** Michigan Daily's scraper has been running on an EC2 hourly cron ("13 * * * *") for years, and the `.aspx` URL structure hasn't changed since 2019 (search results include 2015 `f_15_2060` URL cached by Google, same pattern as today). Reasonably stable. Cloudflare challenge difficulty may escalate over time — that's the biggest unknown.
- **Effort: medium (~8h).** ~2h to get Playwright working past the CF challenge, ~3h to parse subject list + results tables reliably, ~2h to wire the nightly GitHub Action + commit-back-to-repo flow, ~1h to build the name-join with existing RMP data.
- **Coverage:** LSA only. Does NOT include engineering (EECS/AEROSP/etc.), Ross Business, SI, Law, Music, etc. **This is the biggest drawback.** Probably fine if initial launch is CS-adjacent but users will notice EECS missing.

### 3. Schedule of Classes — ro.umich.edu CSV dumps

- **Data available:** Yes, **and it's the best data.** The Registrar publishes per-term CSVs at `https://ro.umich.edu/system/files/timesched/pdf/FA2026.csv` (and `FA2026_open.csv`, `WN2026.csv`, `SU2026.csv`, etc.). Columns are documented at https://ro.umich.edu/calendars/schedule-classes/key — includes CAT #, CLASS # (unique 5-digit section id), COURSE TITLE, SEC, CR, CMP, DAYS, CLASS TIME, LOCATION, instructor, enrollment codes. Covers **all schools on the Ann Arbor campus**, not just LSA.
- **Legal/ToS:** The files are listed on a public-facing page but **the files themselves redirect to Shibboleth login** (verified 2026-04-23: both `FA2026.csv` and `FA2026.pdf` return `HTTP 302 Location: /user/login?destination=...` with `redirect_uri` pointing to `shibboleth.umich.edu`). So these are *functionally* student-only despite being linked publicly. If we had a UM session cookie we could download them trivially, and @umich.edu is the user's email so this is technically possible for personal/manual use, but **automating it from a GitHub Action is effectively impossible** (Duo 2FA per session).
- **Scrape shape:** Trivial `requests.get(URL, cookies=umich_session).text` once authenticated. Without auth: blocked.
- **Maintenance:** Would be near-zero if we had access — static CSV URLs per term.
- **Effort:** small (~2h) **if** access granted. Realistic effort: unknown — would need to ask the Registrar whether the CSVs can be made public or whether an API key can be issued. Worth an email to `ro.classified@umich.edu`.
- **Verdict:** Ideal data, blocked by auth. Pursue as **Phase 2**.

### 4. Wolverine Access / public course catalog

- **Wolverine Access** (https://wolverineaccess.umich.edu/task/all/schedule): gated by UM SSO. Same story as #3.
- **LSA UG Course Catalog** at `https://webapps.lsa.umich.edu/CrsMaint/Public/CB_PublicBulletin.aspx?crselevel=ug` exists (appeared in search) — this is the **catalog** (static course descriptions), not current-semester sections/instructors. Not useful for our use case.
- **Effort:** N/A.

### 5. UM API Directory — ScheduleBuilder API (https://dir.api.it.umich.edu/docs/schedulebuilder/1/overview)

- **Data available:** Per the ITS press release from 2020 (https://michigan.it.umich.edu/news/2020/02/14/api-directory-now-available-to-university-students/) and the API Directory docs (https://documentation.its.umich.edu/api-directory), the ScheduleBuilder API returns courses, instructors, and sections by term. The docs page itself returned empty content when fetched anonymously (likely gated behind Apigee developer portal login), so the specific endpoint list is **unverified**.
- **Legal/ToS:** Legitimate path. Requires (a) creating a developer org in Apigee via a TeamDynamix ticket, (b) faculty sponsor attestation that it's for academic use, (c) per-API subscription approvals from product managers and security admins. Non-trivial bureaucracy.
- **Scrape shape:** Standard REST with an API key. Rate limits unverified.
- **Maintenance:** Low — official API, versioned.
- **Effort: large (~40h wall-clock) but mostly waiting on approvals.** Actual coding ~6h once keys are in hand.
- **Verdict:** Best long-term answer. Pursue in parallel with LSA CG scraper as **Phase 2**, because the approval lead time is weeks, not days.

### 6. Existing open-source scrapers

| Repo | Data source | Approach | Last activity | Useful to us? |
|---|---|---|---|---|
| https://github.com/michigandaily/lsa-cg-scraper | LSA CG HTML | `requests` + BeautifulSoup, cron every hour | Commit count 36; dates not visible in WebFetch output (**unverified recent activity**) | **Yes — canonical reference for URL patterns.** Even if the code itself is stale, the `cg_subjectlist.aspx` / `cg_results.aspx` URL templates are the starting point. |
| https://github.com/kvnshu/atlas-to-ics | Atlas (auth'd) | Selenium + Duo push | Oct 2024 self-deprecation note | No — needs personal login. |
| https://github.com/ldnelson16/atlas | Atlas (auth'd) | Selenium | 45 commits, dates unverified | No — same reason. |
| https://github.com/mfro/umich-scheduler | Unknown (JS/Vue frontend + backend) | Could not determine data source from README via WebFetch | unverified | Worth a manual 10-min look at the backend source — **may contain an undocumented JSON endpoint** used by one of the UM frontends. |
| https://github.com/anders617/michigan-dining-api | Dining only | gRPC+REST | Oct 2023 | Not our domain but nice precedent for "@umich student-built API proxy." |
| https://github.com/tl-its-umich-edu/api-utils-python | UM API Directory client | Python wrapper around Apigee | unverified | Only useful once we have API Directory credentials (option #5). |

### Creative / long-shot sources

- **Registrar PDFs** (`FA2026.pdf`) — same Shibboleth gate as CSVs. Not public.
- **CourseTree / CTools / Canvas** — all gated by SSO.
- **Kaggle / HuggingFace datasets** — searched "umich course schedule dataset" (https://www.kaggle.com/datasets/); no hits for current schedules. There are historical CAI learning-analytics datasets (https://ai.umich.edu/educational-research-learning-analytics/datasets/) but they require IRB-style data requests and don't have current-term section data.
- **The Michigan Daily's own published data** — they scrape this; they might redistribute it. Worth emailing `data@michigandaily.com`. Unverified.
- **Google cache / Wayback Machine** — legal grey area and stale. Not viable.
- **Atlas mobile app API** — likely exists (the web app must call something) but per Atlas ToS still prohibited even if we reverse-engineer it.
- **`webapps.lsa.umich.edu`** subdomain (seen in search results for `default.aspx?termArray=f_15_2060`) — appears to be an older mirror of the same `/cg/` endpoints. Might have a lighter bot-mitigation posture — worth trying before fighting Cloudflare on `www.lsa.umich.edu`. **Unverified.**

---

## Legal / ToS concerns

- **LSA CG**: No explicit scraping prohibition found in the visible robots.txt (verified 2026-04-23). The LSA website ToS was not directly fetched; I did not find a blanket "no automated access" clause for `lsa.umich.edu` in search results. Low risk for a polite, rate-limited, nightly scrape. Still, **send a one-line heads-up email to `lsa-webteam@umich.edu`** with the scrape cadence and User-Agent string — documents good-faith intent.
- **Atlas**: Hard no. Verbatim ToS quoted above.
- **Registrar CSVs**: Redirected to UM login; **do not try to automate past the SSO** with scraped Duo codes even if user has a UM account — crosses a clear line.
- **UM API Directory**: Legit if approved. Commercial-use ambiguity unverified — their Getting Started page emphasizes academic use; ProfInsight is arguably research/education but the site is public so there's a conversation to have.
- **Displaying instructor names publicly**: Instructor-of-record is public directory information at UMich (it's printed on the public schedule each semester). No FERPA issue. Student-level data is a different story but we don't touch that.
- **RMP data**: Separate ToS concern already in scope for the existing scraper; unchanged by this feature.

---

## Fuzzy-match plan: instructor name → existing `data/umich.json` professor ID

Schema on hand (verified):

```
data/umich.json → {metadata, professors: [
  { id, legacy_id, first_name, last_name, department, avg_rating, ... }
]}
```

430 professors, Department values like `"English"`, etc. LSA CG instructor field in the wild looks like `"Last, First M."` or `"First M. Last"` depending on where it's rendered (format not verified from a live page; assumption based on Michigan Daily's parser extracting `instructor` as a single string).

**Matching algorithm (v1):**
1. **Normalize both sides** — lower-case, strip titles (Dr., Prof., Professor), punctuation, middle initials, diacritics (`unidecode`).
2. **Attempt exact match** on `(first_name_normalized, last_name_normalized)`.
3. **Fall back to last-name + first-initial** match, **scoped to the same RMP department if available** (EECS section → only match professors with department in {Computer Science, Electrical Engineering, Computer Engineering, ...}). This handles Michael vs Mike, J. vs John.
4. **Fall back to fuzzy** using `rapidfuzz.fuzz.token_set_ratio` ≥ 90, again department-scoped.
5. **Persist a manual override table** at `data/umich_name_overrides.json` keyed on the scraped string → RMP `id`, for the long tail. Expect ~10–30 overrides the first run, trailing off.

**Expected hit rate:** The 430 RMP professors represent only the ones who've been reviewed ≥1 time, so only a fraction of current-term instructors will match — and that's fine. Unmatched instructors just render as "No reviews yet" in the UI, same as RMP itself.

**Bigger risk:** Common last names in large departments (e.g. two "Smith"s in EECS). Mitigate by showing "likely match" badges or letting the user click through to a disambiguation page if fuzzy score is in 75–90 range.

**Join key stability:** Instructor names change (marriage, preferred-name updates). Good idea to log every unmatched name monthly and review — this is the thing that breaks silently. Put it in the nightly Action output.

---

## Open questions I couldn't answer from public info alone

1. **How do we cover non-LSA courses (EECS, AEROSP, Ross, etc.)?** LSA CG is LSA-only. Options: (a) accept the gap in v1 and be explicit in the UI; (b) apply for UM API Directory access; (c) ask the Registrar directly whether the public-facing CSVs can be ungated for non-student-specific fields; (d) scrape individual school catalogs (e.g. the CoE has its own course planner — unverified whether it's public). **Need decision before scoping a v1 ship.**
2. **Does the Cloudflare challenge on lsa.umich.edu escalate to CAPTCHA for headless Chromium?** Only way to know is to run a test scrape. If yes, we'd need `playwright-stealth` or a residential proxy (much more effort + cost).
3. **What's the exact term-ID format?** Search hits suggest `f_YY_NNNN` where NNNN is a 4-digit UM term code. The Michigan Daily scraper presumably hard-codes term IDs per run. **Need to confirm by reading their actual Python.** Would add ~30 min to scoping once repo is cloned.
4. **What's the scraper's actual last-updated date?** WebFetch could not surface commit dates; need to `git clone https://github.com/michigandaily/lsa-cg-scraper` to see. If it hasn't been touched since 2022, Cloudflare's challenge may already have broken it, which changes our "proven to work" confidence.
5. **Does the UM API Directory's ScheduleBuilder API actually include instructor-of-record, or only time/location?** Doc page returned empty body to WebFetch. **Unverified.** Worth asking UM ITS before committing 40h to that path.
6. **Would UM consider ProfInsight as a third party under Atlas ToS if we only consume LSA CG's public HTML, never Atlas itself?** Almost certainly yes — Atlas's ToS governs Atlas, not LSA CG. But worth a quick legal read from a UM lawyer friend.
7. **`webapps.lsa.umich.edu` vs `www.lsa.umich.edu/cg` — are they the same data, different bot postures?** Unverified.

---

## References

- LSA robots.txt — https://www.lsa.umich.edu/robots.txt
- LSA Course Guide — https://www.lsa.umich.edu/cg/
- LSA CG example URL — https://www.lsa.umich.edu/cg/cg_results.aspx?termArray=f_19_2260&cgtype=ug&show=20&department=INSTHUM
- Michigan Daily scraper — https://github.com/michigandaily/lsa-cg-scraper
- Registrar schedule page — https://ro.umich.edu/calendars/schedule-classes
- Registrar schedule key — https://ro.umich.edu/calendars/schedule-classes/key
- Registrar FA2026 CSV (auth-gated) — https://ro.umich.edu/system/files/timesched/pdf/FA2026.csv
- Atlas — https://atlas.ai.umich.edu/
- Atlas ToS — https://atlas.ai.umich.edu/legal/
- ScheduleBuilder API — https://dir.api.it.umich.edu/docs/schedulebuilder/1/overview
- API Directory — https://documentation.its.umich.edu/api-directory
- API Directory announcement — https://michigan.it.umich.edu/news/2020/02/14/api-directory-now-available-to-university-students/
- API utils Python client — https://github.com/tl-its-umich-edu/api-utils-python
- kvnshu/atlas-to-ics — https://github.com/kvnshu/atlas-to-ics
- ldnelson16/atlas — https://github.com/ldnelson16/atlas
- mfro/umich-scheduler — https://github.com/mfro/umich-scheduler
- Wolverine Access class schedule — https://wolverineaccess.umich.edu/task/all/schedule
- UM data areas (teaching/learning) — https://its.umich.edu/enterprise/administrative-systems/data-warehouse/data-areas/teaching-learning
- CAI datasets — https://ai.umich.edu/educational-research-learning-analytics/datasets/
