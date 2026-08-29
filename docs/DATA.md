# Data: what is in `data/`, where it comes from, and the school-ID rule

## Files

| File | Producer | Consumer |
|---|---|---|
| `data/<slug>.json` | `rmp_scraper.py` | `bayesian_pipeline.py`, `train_classifier.py`, `evaluate.py` |
| `data/<slug>_analyzed.json.gz` | `bayesian_pipeline.py` | `api.py` (the only file the API reads); gzipped because the 65-school set is 844 MB plain and 118 MB compressed, and it is the whole deploy payload. Readers accept a plain `.json` too |
| `data/umd_schedule.json` | `umd_scheduler.py` | `api.py` (`teaching_now`, `schedule_status`) |
| `models/nb_topic_model.json` | `train_classifier.py` | `bayesian_pipeline.py` |
| `metrics/latest.{json,md}` | `evaluate.py` | README, docs |

Raw files hold every review (text, sub-ratings, tags, grade, date). Analyzed
files hold per-professor posteriors, trend curves, highlights and verdicts.
The API never opens a raw file. `datafiles.py` is the one place that knows
about the suffixes; use `analyzed_path()`, `load_json()`, `dump_json()`.

## The school-ID rule

`rmp_scraper.py --school "<name>"` takes the **first** hit from RMP's school
search. RMP's ranking is loose, and for several large schools the first hit is
a different campus:

| Query | First hit (wrong) | Correct school | Correct `school_id` |
|---|---|---|---|
| University of Maryland | UMBC | UMD College Park | `U2Nob29sLTEyNzA=` |
| University of California Irvine | UC Riverside | UC Irvine | `U2Nob29sLTEwNzQ=` |
| University of Texas at Dallas | UT Arlington | UT Dallas | `U2Nob29sLTEyNzM=` |
| Texas A&M University | Texas A&M (Beaumont, 5 profs) | Texas A&M College Station | `U2Nob29sLTEwMDM=` |
| University of Southern California | USC School of Dentistry (4 profs) | USC, Los Angeles | `U2Nob29sLTEzODE=` |
| University of Central Florida | UCF Cocoa campus (54 profs) | UCF, Orlando | `U2Nob29sLTEwODI=` |

Five school files shipped under the wrong campus until August 2026 (`uci`
was Riverside, `utdallas` was Arlington, `tamu` was Beaumont, `usc` was the
dentistry school, `ucf` was a satellite campus). The Riverside and Arlington
files were renamed to the slug of the school they actually contain (`ucr`,
`uta`); the five real schools were re-scraped with pinned IDs.

**Rule:** every entry in `bulk_update.DEFAULT_SCHOOLS` for a school whose name
is a prefix of, or shares a word with, another RMP school gets an explicit
`school_id`. When adding a school, run the search first and look at the city:

```bash
python - <<'PY'
import rmp_scraper as s
for r in s.search_school("University of X")[:5]:
    print(r["id"], r["name"], r.get("city"))
PY
```

The IDs are base64 of `School-<n>`, so `U2Nob29sLTEwMDM=` is `School-1003`.

## Scraper behaviour

- GraphQL endpoint with the public `Basic dGVzdDp0ZXN0` header, 3 retries
  with exponential backoff (`rmp_scraper.graphql_request`).
- Professor discovery: single-letter search, then two-letter combos with 8
  concurrent workers, until `--max-professors` (nightly default 1500).
- Professors with fewer than 3 ratings are skipped (`--min-ratings`).
- Reviews are paged 20 at a time until exhausted.

## Refresh cadence

`.github/workflows/update-data.yml` runs nightly at 03:00 UTC and refreshes one
of three deterministic batches (`day-of-year mod 3`), so every school is
refreshed about every three days. `umd-schedule.yml` refreshes the Testudo
schedule nightly at 04:30 UTC. `scrape-school.yml` is the on-demand entry
point for adding a school.

## Regenerating everything locally

```bash
./deploy.sh train-classifier   # models/nb_topic_model.json from tag weak labels
./deploy.sh analyze            # every data/<slug>.json -> data/<slug>_analyzed.json.gz
./deploy.sh evaluate           # metrics/latest.json + metrics/latest.md
```
