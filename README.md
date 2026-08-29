# ProfInsight

**Know your professor before you register.**

ProfInsight turns RateMyProfessors reviews into calibrated estimates. A professor with 4.5 stars from 3 reviews and one with 4.5 from 300 get different answers, with the uncertainty shown, and the site says whether ratings are rising or falling, what grades students report, and which professor fits how you learn.

**Live:** [profinsight-three.vercel.app](https://profinsight-three.vercel.app)

Every number below comes from `python evaluate.py` and is written to [`metrics/latest.md`](metrics/latest.md). Re-run it after any change.

## Scale

| | |
|---|---|
| Schools | 65 (UMich, Berkeley, MIT, Stanford, CMU, Georgia Tech, UT Austin, UCLA, USC, Duke, Vanderbilt, ... full list in `bulk_update.py`) |
| Professors | 50,842 |
| Reviews | 1,386,314 (64M words of review text) |
| Departments / courses | 4,902 school-department pairs, 159,568 school-course pairs (course codes as reviewers typed them) |
| Review dates | 1999 to 2026; 408,819 since 2024 |
| Code | ~9,000 lines: Python pipeline, FastAPI, React; 65 pytest cases + 107 doctests, run in CI on every push |
| Refresh | Nightly GitHub Actions: one third of the schools each night, UMD course schedule every night; the topic classifier is retrained on every refresh |

## What the models do, and how well

All modeling is pure Python (no NumPy, SciPy or scikit-learn). Every model is scored on held-out data by `evaluate.py`; the protocol is in [Evaluation](#evaluation).

| Model | What it produces | Held-out result |
|---|---|---|
| Beta-Binomial with empirical-Bayes priors (type-II maximum likelihood per department) | Calibrated P(good rating), P(would take again), exact 95% credible intervals | Log-loss 16.6% lower than raw averages overall and 46% lower for professors with 4 or fewer training reviews (take-again; 14.5% and 50% on good-rating); 90% posterior-predictive intervals cover 88.5% of held-out outcomes. On the good-rating outcome a fixed Beta(2,2) prior edges the EB prior overall (0.579 vs 0.582), and a concentration sweep shows the ML-II prior (alpha+beta near 2) is weaker than optimal under drift (best at 8); the sweep is in the metrics file |
| Recency-weighted posterior (3-year half-life) | Current-quality estimate | Best single estimator on the temporal hold-out on both outcomes: log-loss 0.326 vs 0.332 (unweighted) vs 0.398 (raw average) on take-again, and the best calibrated: 90% intervals cover 90.4% |
| Gaussian process on monthly-binned rating history (RBF kernel, heteroscedastic noise by bin count, hand-written Cholesky, length-scale by marginal likelihood) | Trend curve with credible band, trend label | Predicts the next period's mean rating with MAE 0.63 stars, about the same as the running average (0.64) and better than a last-5 average (0.68); the earlier zero-mean GP scored 2.40. The GP earns its place through the credible band and the trend label, not through point accuracy |
| Multinomial Naive Bayes trained on tag-weak-labeled reviews | Per-review topic (grading, lectures, workload, approachability, exams) | 53.2% top-1 on 96K reviews from 32 unseen schools, vs 27.4% majority class and 17.5% for the self-trained model it replaced (macro-F1 0.45). The exams class is weak (F1 under 0.1); per-class numbers are in the metrics file |
| Fixed-effects regression of rating on reported grade | Grade-inflation slope per school, grade-adjusted rating | Median slope 0.78 rating points per GPA point across 65 schools; split-half gap 0.05 |
| Monte Carlo P(A > B) over two Beta posteriors | Head-to-head verdict on the compare page | Checked against the closed form in tests |

## What students see

- Letter-grade style verdicts with a confidence level and a plain-language reason
- Conservative / Expected / Optimistic toggle driven by posterior quantiles (decision-theoretic point estimates)
- Trend chart with a credible band and a label such as "Declining over time"
- Grade distribution, personal grade forecast from your GPA, and grade-inflation-adjusted rating
- Teaching-style attributes pulled from review text and RMP's structured fields (slides posted, attendance mandatory, curved, multiple-choice exams)
- Per-tag posteriors with credible bands, so "Tough grader" from 3 reviews looks different from 300
- Fit quiz: rank professors by your preferences, with a credible band on the match score
- Compare two professors: P(A is rated higher), not two averages
- Semester optimizer: pick courses, get a professor per course and a predicted GPA
- UMD only: which sections each professor is teaching this term, joined from Testudo

## Evaluation

`evaluate.py` runs in about 75 seconds on a laptop for all 65 schools and writes `metrics/latest.json` and `metrics/latest.md`.

1. **Shrinkage hold-out.** For every professor with at least 4 dated reviews, sort by date, train on the first half, test on the second. Priors are fit on training halves only. Compare raw average, school mean, fixed Beta(2,2), naive method-of-moments EB, type-II ML EB, and the recency-weighted posterior on log-loss, Brier score and per-professor MAE, stratified by training size. Coverage of 80/90/95% Beta-Binomial posterior-predictive intervals on the held-out success count.
2. **GP hold-out.** Professors with at least 8 dated reviews: fit on the first 70%, predict the mean of the last 30%.
3. **Topic classifier.** Reviews whose RMP tags map to exactly one topic are weak labels. Schools are split alternately; the model trains on one half and is scored on the other.
4. **Grade-inflation slope stability** on odd vs even professors.

Building the harness found three bugs that were live on the site, all fixed in August 2026:

- The empirical-Bayes prior fit used the raw variance of per-professor proportions, which includes binomial sampling noise, so 78% of department priors collapsed to the clamp floor. Replacing it with a marginal-likelihood fit (35% at the floor) was the correct estimator, and the hold-out showed the predictions barely moved: the professor population is heterogeneous enough (alpha + beta near 2) that the clamp had landed near the right answer.
- The GP had no mean function on a 1 to 5 scale, so 51% of trend curves dipped below one star in gaps between reviews and 61% of trend labels change after centering (measured in the harness). "Declining over time" was the most common label on the site; it is now the fourth. The same pass found the GP ran on raw reviews, an O(n cubed) solve that could not finish for BYU's 6,626-review professor; ratings are now binned by month with noise scaled by bin count, and BYU analyzes in 22 seconds.
- The topic classifier's self-training step scored 17.5% on weak labels, below the 27.4% majority-class baseline. Training on tag-derived labels instead scores 53.2%.

## Architecture

```
rmp_scraper.py ──► data/<slug>.json ──► bayesian_pipeline.py ──► data/<slug>_analyzed.json.gz ──► api.py (FastAPI) ──► frontend/ (React)
                                              ▲                                                    ▲
                        train_classifier.py ──┘ models/nb_topic_model.json      umd_scheduler.py ──┘ data/umd_schedule.json
                                                                                evaluate.py ──► metrics/latest.{json,md}

Data is not in git. publish_data.py uploads data/ to the GitHub release `data-latest`
(131 assets, 311 MB gzipped); fetch_data.py pulls it, and api.py does so by itself on
a machine whose data/ is empty.
```

| File | Role |
|---|---|
| `rmp_scraper.py` | RMP GraphQL scraper: two-letter search discovery, paged reviews, retry with backoff, refuses to save a bad scrape |
| `bulk_update.py` | School list with pinned RMP school IDs, batch rotation for the nightly job |
| `bayesian_calibration.py` | Regularized incomplete Beta, exact credible intervals, EB prior fits (ML and MoM), P(A > B), decision summaries |
| `bayesian_pipeline.py` | Beta-Binomial model, Naive Bayes, Gaussian process, per-professor analysis, JSON writer |
| `bayesian_advanced.py` | Personal grade forecast, recency weighting, outlier mixture model |
| `bayesian_honest.py` | Grade-inflation fixed effects, teaching-attribute extraction |
| `train_classifier.py` | Builds the topic classifier from tag weak labels |
| `evaluate.py` | The evaluation harness |
| `api.py` | 16 GET routes, per-file LRU cache with mtime reload, rate limiting, cache and security headers |
| `datafiles.py` | Gzip-aware IO for raw and analyzed files (the deploy payload is 118 MB gzipped vs 844 MB plain) |
| `fetch_data.py`, `publish_data.py` | Pull from / push to the rolling `data-latest` GitHub release; the nightly workflows publish instead of committing, and a publish refuses to replace a school with fewer than half its published professors |
| `umd_scheduler.py` | Testudo schedule scraper and instructor-to-professor matcher |
| `frontend/` | React 18, Vite, Tailwind, Recharts; 6 components |
| `.github/workflows/` | `test.yml` (pytest + doctests + harness smoke test), `update-data.yml` (nightly refresh), `umd-schedule.yml`, `scrape-school.yml` (on demand) |
| `docs/` | `DATA.md` (data files and the school-ID rule), `INTERVIEW.md` (how to talk about the project), `BAYESIAN_CONCEPTS.md`, `USER_RESEARCH.md`, `UMD_SCHEDULE.md` |

Deployment: API on Render (`uvicorn api:app`, `MAX_CACHED_SCHOOLS=2` on the free tier; it fetches the data release at boot), frontend on Vercel, data refreshed nightly by GitHub Actions into the release and the API redeployed through Render's deploy hook.

## Running locally

Prerequisites: Python 3.10+, Node 18+.

```bash
git clone https://github.com/thesanatt/profinsight.git
cd profinsight
./deploy.sh setup     # venv + pip + npm
./deploy.sh fetch     # data snapshot from the GitHub release (add --raw for scrapes, ~310 MB)
./deploy.sh test      # pytest + doctests
./deploy.sh dev       # API on :8000, frontend on :5173
```

Other subcommands: `analyze`, `train-classifier`, `evaluate`, `build`, `serve`, `scrape <slug> "<Name>"`, `refresh`, `status`. Publishing a local scrape: `python publish_data.py --schools <slug>` (needs `gh auth login`).

## Adding a school

```bash
python - <<'PY'
import rmp_scraper as s
for r in s.search_school("University of X")[:5]:
    print(r["id"], r["name"], r.get("city"))
PY
python rmp_scraper.py --school "University of X" --school-id <id> --output data/x.json
python bayesian_pipeline.py --input data/x.json --output data/x_analyzed.json.gz
```

Pin the ID. RMP's name search returns the wrong campus for several large schools (Irvine came back as Riverside, Dallas as Arlington, College Park as UMBC, USC as its dentistry school); five schools shipped under the wrong campus until the harness caught it. Details in [`docs/DATA.md`](docs/DATA.md). Add the slug and ID to `DEFAULT_SCHOOLS` in `bulk_update.py` to include it in the nightly rotation.

## Limitations

- Reviews are self-selected and unverified. Shrinkage and outlier flagging reduce the effect of small samples and single hostile reviews; they cannot fix selection bias.
- The topic classifier's labels are weak. 52% top-1 over five classes is useful for aggregating sentiment by topic, not for labeling an individual review.
- Grade forecasts use self-reported grades, which skew high (A-range is 62% of reports). The forecast's 95% interval is a normal approximation on a four-bucket posterior; treat it as a rough width.
- Per-school coverage is capped at 1,500 professors per scrape and professors with fewer than 3 ratings are skipped; large schools are not exhaustive.
- Course schedules are joined for UMD only (2,232 instructor assignments across 455 professors this term). UMich's course guide moved behind SSO; other public schedule endpoints are listed in `docs/UMD_SCHEDULE.md`.
- No user traffic is measured or claimed.

## Disclaimer

ProfInsight is an independent, non-commercial academic project. Not affiliated with or endorsed by RateMyProfessors or any university. Verdicts and forecasts are computed estimates from public review data.

## License

MIT

## Author

Built by [Sanat Gupta](https://thesanatgupta.com) ([LinkedIn](https://linkedin.com/in/sanat-gupta)).
