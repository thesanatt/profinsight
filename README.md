# ProfInsight

Bayesian ML-powered professor analysis. Uses Beta-Binomial posteriors, Naive Bayes classification, and Gaussian Process Regression — no LLM APIs, no monthly costs.

## Setup (Mac)

You need: Python 3.10+, Node.js 18+, and a terminal.

### Step 1 — Project structure

```bash
mkdir -p ~/Projects/profinsight/data
cd ~/Projects/profinsight
```

Move ALL the downloaded files into `~/Projects/profinsight/`. Your folder should look like:

```
profinsight/
├── rmp_scraper.py
├── bayesian_pipeline.py
├── api.py
├── data/
│   └── (empty for now)
└── frontend/
    ├── package.json
    ├── vite.config.js
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── index.html
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── index.css
        └── components/
            ├── StatsBar.jsx
            ├── ProfessorList.jsx
            └── ProfessorDetail.jsx
```

### Step 2 — Python backend setup

```bash
cd ~/Projects/profinsight

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python deps
pip install requests fastapi uvicorn
```

### Step 3 — Scrape + analyze data

```bash
# Scrape UMich professors (start with 50, takes ~2 min)
python rmp_scraper.py --school "University of Michigan" \
  --max-professors 50 --output data/umich.json

# Run Bayesian ML analysis
python bayesian_pipeline.py --input data/umich.json \
  --output data/umich_analyzed.json
```

### Step 4 — Start the API server

```bash
# In one terminal tab:
cd ~/Projects/profinsight
source venv/bin/activate
uvicorn api:app --reload --port 8000
```

Test it: open http://localhost:8000 in your browser. You should see JSON.

### Step 5 — Start the React frontend

```bash
# In a SECOND terminal tab:
cd ~/Projects/profinsight/frontend
npm install
npm run dev
```

Open http://localhost:5173 — you should see the dashboard.

## What you're looking at

- **Professor list** with Bayesian P(good) confidence bars — the dot shows the posterior mean, the shaded area is the 95% credible interval
- **Click any professor** to see:
  - **Rating posteriors** — Beta-Binomial analysis at three quality thresholds
  - **GP trend** — Gaussian Process regression showing rating trajectory with uncertainty
  - **Sentiment radar** — Naive Bayes topic classification showing per-category sentiment
  - **Grade distribution** — Self-reported student grades
  - **Tag cloud** — Most common student tags

## Tech stack

| Layer | Tech |
|-------|------|
| Scraper | Python, requests, RMP GraphQL API |
| ML Pipeline | Pure Python (no sklearn/scipy needed) — Beta-Binomial, Naive Bayes, GP Regression |
| Backend | FastAPI, uvicorn |
| Frontend | React 18, Vite, Tailwind CSS, Recharts |

## Scrape other schools

```bash
python rmp_scraper.py --school "MIT" --max-professors 50 --output data/mit.json
python bayesian_pipeline.py --input data/mit.json --output data/mit_analyzed.json
```

Then update `api.py` line ~30 to load the new file, or rename it to `umich_analyzed.json`.
