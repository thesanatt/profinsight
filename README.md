# ProfInsight

**Know your professor before you register.**

ProfInsight analyzes student reviews using Bayesian machine learning to give you more than a star rating. It tells you how confident we are in that rating, whether a professor is getting better or worse, what grades students actually get, and which professor fits how you learn.

**Live:** [profinsight-three.vercel.app](https://profinsight-three.vercel.app)

---

## Why this exists

RateMyProfessors gives you a number. But a professor with 4.5 stars from 3 reviews is very different from a professor with 4.5 stars from 300 reviews. A professor trending from 3.0 to 4.5 over the last two years is very different from one trending from 4.5 down to 3.0. ProfInsight captures that nuance.

## What it does

**For students:**
- Letter-grade ratings for every professor (A+ through D) based on Bayesian confidence, not just averages
- Plain language verdicts: "Tough course, but students consistently rate the teaching highly"
- Grade predictions: "Likely an A" vs "Could go either way" vs "Tough grading"
- Red flag detection: declining ratings, low retake rates, poor lecture reviews
- Semester optimizer: enter your courses, pick a preference (easy / balanced / challenge), and get the best professor combination with a predicted semester GPA
- Student fit quiz: tell us how you learn, we rank professors by compatibility
- Side-by-side professor comparison with radar charts

**Under the hood:**
- Beta-Binomial posteriors with **empirical-Bayes priors** fit per department so small-n professors shrink toward their peers (no more "5.0 from 2 reviews" artifact)
- **Decision-theoretic display toggle** — Conservative / Expected / Optimistic point estimates driven by posterior quantiles (Lecture 4)
- **Posterior hypothesis test** `P(Prof A > Prof B)` on the compare view via Monte Carlo over two Beta posteriors
- **Posterior-predictive moderation** on fit scores — thin-data dimensions automatically widen the credible band
- **Per-tag Beta-Binomial** — each tag gets its own posterior mean with a 95% credible interval, not a raw count
- Naive Bayes classifier for multi-category sentiment analysis (lectures, grading, workload, approachability, exams)
- Gaussian Process Regression for rating trend detection with credible bands
- Grade probability estimation from self-reported grade distributions
- **Exact** Beta credible intervals (regularized incomplete Beta via continued fraction) — no more normal-approximation overshoot into [−0.1, 1.1]
- No LLM APIs, no scipy, no sklearn. All analysis is original statistical modeling in pure Python.

## Coverage

29 universities including University of Michigan, MIT, Stanford, UC Berkeley, Georgia Tech, Carnegie Mellon, Purdue, NYU, Ohio State, Michigan State, and more. Data refreshes weekly via automated GitHub Actions.

## Architecture

```
┌──────────────┐     ┌────────────────────┐     ┌──────────────┐
│  RMP GraphQL  │────▶│  Bayesian Pipeline  │────▶│  FastAPI      │
│  Scraper      │     │  (Beta-Binomial,    │     │  REST API     │
│  (Python)     │     │   NB, GP Regression)│     │               │
└──────────────┘     └────────────────────┘     └──────┬───────┘
                                                        │
                                                 ┌──────▼───────┐
                                                 │  React +      │
                                                 │  Tailwind     │
                                                 │  Frontend     │
                                                 └──────────────┘
```

| Component | Tech |
|-----------|------|
| Scraper | Python, requests, RMP GraphQL API, ThreadPoolExecutor, retry with exponential backoff |
| ML Pipeline | Pure Python: Beta-Binomial posteriors, Naive Bayes, Gaussian Process Regression (no sklearn/scipy) |
| Backend | FastAPI, in-memory LRU cache, rate limiting, response caching |
| Frontend | React 18, Vite, Tailwind CSS, Recharts |
| Deployment | Render (API), Vercel (frontend), GitHub Actions (weekly data refresh) |

## Running locally

**Prerequisites:** Python 3.10+, Node.js 18+

```bash
git clone https://github.com/thesanatt/profinsight.git
cd profinsight

# One-shot: installs deps, analyzes, builds, runs both servers
./deploy.sh setup
./deploy.sh dev
```

Subcommands: `setup`, `analyze`, `build`, `dev`, `serve`, `scrape <slug> "<Name>"`, `refresh`, `status`, `deploy`. See `./deploy.sh help`.

Open http://localhost:5173

## Adding a new school

```bash
python rmp_scraper.py --school "Harvard University" --max-professors 500 --output data/harvard.json
python bayesian_pipeline.py --input data/harvard.json --output data/harvard_analyzed.json
```

The API auto-discovers new `*_analyzed.json` files. Refresh the browser and the school appears.

To add it to the weekly auto-update, add an entry to `DEFAULT_SCHOOLS` in `bulk_update.py`.

## How the ML works

**Beta-Binomial with empirical-Bayes priors:** Each professor's quality is a Beta distribution. We don't pick a fixed prior — we fit `Beta(α, β)` by method of moments from every other professor in their department (or the school, if the department is small). That means a small-n professor's posterior is automatically pulled toward their department's baseline, and the amount of pulling is inferred from the between-professor variance. Credible intervals are computed exactly via the regularized incomplete Beta (numerical CDF inversion), so they don't overflow `[0, 1]`.

**Decision-theoretic display:** Following Lecture 4, the "right" point estimate depends on the loss function. We expose a `Conservative / Expected / Optimistic` toggle — posterior 25%-quantile, mean, and 75%-quantile respectively. Default is `Expected`.

**Posterior hypothesis test:** On the compare view, `P(Prof A > Prof B)` is computed directly from their two Beta posteriors (seeded Monte Carlo; a closed-form check for small shapes runs in the test suite). No null hypothesis, no p-value — you get an actual probability statement.

**Posterior-predictive moderation on fit scores:** Each category of sentiment is turned into a Beta posterior with a weak prior; the fit score is the weighted expectation of those posteriors, with variance propagated into a credible band. Thin-data categories don't pull the score confidently in any direction.

**Per-tag Beta-Binomial:** Each tag's count is turned into a posterior with a fixed weak prior centered at the global tag base-rate. Small-n tags show visibly wider bars so users can see what's confident and what isn't.

**Naive Bayes sentiment:** Reviews are classified into five categories (lectures, grading, workload, approachability, exams) using a bag-of-words Naive Bayes model trained semi-supervised on the full review corpus.

**Gaussian Process Regression:** Rating timestamps are modeled as a GP with an RBF kernel to detect trends. The model outputs a smooth prediction curve with credible bands, showing whether a professor is improving, declining, or stable over time.

All Bayesian primitives live in `bayesian_calibration.py` and have 60+ doctests + property tests (`tests/test_bayesian_calibration.py`). See `LIVE_GUIDE/` for the full concept-by-concept mapping from class lectures to pipeline code.

## Disclaimer

ProfInsight is an independent, non-commercial academic project. Not affiliated with or endorsed by RateMyProfessors or any university. Professor coverage varies by school. All verdicts and predictions are computed estimates based on publicly available review data.

## License

MIT

## Author

Built by [Sanat Gupta](https://thesanatgupta.com) · [LinkedIn](https://linkedin.com/in/sanat-gupta)
