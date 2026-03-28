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
- Beta-Binomial posteriors for confidence-aware quality ratings
- Naive Bayes classifier for multi-category sentiment analysis (lectures, grading, workload, approachability, exams)
- Gaussian Process Regression for rating trend detection with uncertainty bands
- Grade probability estimation from self-reported grade distributions
- No LLM APIs. All analysis is original statistical modeling in pure Python.

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

# Backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn api:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

## Adding a new school

```bash
python rmp_scraper.py --school "Harvard University" --max-professors 500 --output data/harvard.json
python bayesian_pipeline.py --input data/harvard.json --output data/harvard_analyzed.json
```

The API auto-discovers new `*_analyzed.json` files. Refresh the browser and the school appears.

To add it to the weekly auto-update, add an entry to `DEFAULT_SCHOOLS` in `bulk_update.py`.

## How the ML works

**Beta-Binomial model:** Instead of just averaging ratings, we model each professor's quality as a Beta distribution. The posterior probability P(good) represents how likely it is that a randomly selected student would rate them above a threshold, with credible intervals that shrink as more reviews come in. A professor with 4.5/5 from 3 reviews gets wide intervals (low confidence). The same rating from 200 reviews gets tight intervals (high confidence).

**Naive Bayes sentiment:** Reviews are classified into five categories (lectures, grading, workload, approachability, exams) using a bag-of-words Naive Bayes model trained on the full review corpus. Each category gets a positive/negative ratio that feeds into the professor profile.

**Gaussian Process Regression:** Rating timestamps are modeled as a GP with an RBF kernel to detect trends. The model outputs a smooth prediction curve with uncertainty bands, showing whether a professor is improving, declining, or stable over time.

## Disclaimer

ProfInsight is an independent, non-commercial academic project. Not affiliated with or endorsed by RateMyProfessors or any university. Professor coverage varies by school. All verdicts and predictions are computed estimates based on publicly available review data.

## License

MIT

## Author

Built by [Sanat Gupta](https://thesanatgupta.com) · [LinkedIn](https://linkedin.com/in/sanat-gupta)
