# ProfInsight: Current System State & Architecture

**Last Updated:** 2026-04-23  
**Scope:** Complete audit of production system (scrapers → pipeline → API → frontend)

---

## Executive Summary

1. **Three-stage pipeline:** RateMyProfessor GraphQL scraper → Bayesian ML analysis → FastAPI REST backend
2. **Bayesian core:** Beta-Binomial rating posteriors (with thresholds), Naive Bayes topic classification, lightweight Gaussian Process trends
3. **Uncertainty quantification:** CI's on posterior probabilities flow to frontend, displayed in detail cards; credible intervals widen with sparse data
4. **No Bayesian hierarchy or empirical Bayes yet:** Priors are fixed population-level (Beta(2,2)); no school/department shrinkage
5. **Sentiment by category:** Six topics (grading, lectures, workload, approachability, exams, overall); Naive Bayes assigns reviews to categories
6. **Grade distribution & course-level breakdown:** Per-professor and per-course statistics; grade probabilities binned into A/B/C/D-F ranges
7. **Student-facing layer:** Verdict (text + emoji), confidence level, trend summary, red flags; comparison/fit/optimizer tools for course selection
8. **Data shape:** ~400–650 professors/school, ~10k–15k reviews; analyzed JSON is 20–40 MB
9. **Frontend architecture:** React SPA, multi-school support, hash-based routing; 7 main UI modes (browse, detail, fit quiz, compare, schedule, optimize)
10. **No active calibration or external validation:** System is deterministic Bayesian; no feedback loop or online learning

---

## Architecture Overview

```
rmp_scraper.py     → data/{school}.json              (raw reviews + metadata)
    ↓
bayesian_pipeline.py → data/{school}_analyzed.json   (Bayesian posteriors + verdicts)
    ↓
api.py              → /api/{school}/...              (FastAPI REST endpoints)
    ↓
frontend/src        → React SPA                       (browser UI)
```

---

## 1. Data Sources & Scrapers

### 1.1 `rmp_scraper.py` (Primary Scraper)
**Purpose:** Fetch professor profiles and reviews from RateMyProfessors GraphQL API.

**Key Details:**
- Uses public RMP GraphQL endpoint: `https://www.ratemyprofessors.com/graphql`
- Auth: Basic token `dGVzdDp0ZXN0` (public, embedded in RMP frontend JS)
- Searches 1-letter + 2-letter combinations to discover professors (lines 234–286)
- Fetches up to 20 reviews per professor, paginated
- Parallel fetch: 2 workers max to respect rate limits
- Returns schema (lines 396–416):
  ```
  {
    "professor_id": str (base64 encoded),
    "legacy_id": int,
    "first_name": str, "last_name": str,
    "department": str,
    "avg_rating": float, "avg_difficulty": float, "num_ratings": int,
    "would_take_again_pct": float (−1 = unknown),
    "top_tags": [{tag, count}],
    "reviews": [{
      "id", "class_name", "date", "comment",
      "helpful_rating" (1–5), "clarity_rating" (1–5), "difficulty_rating" (1–5),
      "would_take_again" (1=yes, 0=no, −1=N/A), "grade",
      "is_online", "is_for_credit", "attendance_mandatory",
      "thumbs_up", "thumbs_down"
    }]
  }
  ```
- Output: `data/{school}.json` with metadata (school_name, total_professors, total_reviews, scraped_at)

### 1.2 `deep_scrape.py` (Exhaustive Secondary Scraper)
**Purpose:** Deep scrape a single school incrementally for maximum coverage.

**Key Details:**
- Resumes from existing `data/{school}.json` to avoid re-fetching
- Discovers professors via 1-letter + 2-letter combos (line 110)
- Fetches reviews for professors missing them (rate-limited recovery)
- Pushes to GitHub optionally (line 347–351)
- Used for initial seeding and periodic updates

### 1.3 `bulk_update.py` (Orchestrator)
**Purpose:** Scrape and analyze multiple schools in one command.

**Key Details:**
- 28 default schools (line 25–56): MIT, Stanford, Berkeley, CMU, UMich, etc.
- Calls `rmp_scraper.py` → `bayesian_pipeline.py` for each school
- Supports `--all`, `--refresh`, `--schools`, `--add` modes
- Reports final status per school (professors, reviews, analysis status)

---

## 2. Bayesian Analysis Pipeline

**File:** `bayesian_pipeline.py` (917 lines)  
**Purpose:** Transform raw review data into student-friendly insights with statistical rigor.

### 2.1 Model 1: Beta-Binomial Rating Posterior (lines 39–153)

**Class:** `BetaBinomialModel`

**Prior:**
- Hyperparameters: α₀ = 2.0, β₀ = 2.0 (line 48, 866)
- Distribution: Beta(2, 2) = weakly informative, symmetric, centered at 0.5
- **No justification in code for these values** — appears chosen for weak informativeness

**Likelihood:**
- Binomial: counts ratings ≥ threshold as successes
- Three thresholds applied (line 110–120):
  - "excellent" (≥4.5): P(rating is excellent)
  - "good" (≥3.5): P(rating is good) — **primary metric used in UI**
  - "acceptable" (≥2.5): P(rating is acceptable)

**Posterior:**
- Formula: Beta(α = α₀ + successes, β = β₀ + failures)
- Mean: α/(α+β) = point estimate of P(good)
- Variance: αβ/[(α+β)²(α+β+1)] (line 151)
- 95% CI via normal approximation: mean ± 1.96·std (lines 93–95)

**Sub-rating Posteriors (lines 122–148):**
- Three dimensions: clarity, helpfulness, difficulty (inverted: 5−rating)
- Also thresholded at 3.5 (good)
- **Output:** Raw mean + posterior for each dimension

**Example Output (data/umich_analyzed.json, lines 109–146):**
```json
"rating_posteriors": {
  "good": {
    "alpha": 16.0,
    "beta": 7.0,
    "mean": 0.6957,
    "variance": 0.008822,
    "std": 0.0939,
    "ci_lower": 0.5116,
    "ci_upper": 0.8797,
    "n_ratings": 19,
    "n_above_threshold": 14,
    "threshold": 3.5
  }
}
```
→ With 19 reviews (14 ≥3.5), posterior P(good) = 69.6% [51%, 88%]

### 2.2 Model 2: Naive Bayes Review Classifier (lines 167–374)

**Class:** `NaiveBayesClassifier`

**Approach:**
- Multinomial Naive Bayes: P(category | words) ∝ P(words | category) · P(category)
- **Seed-based:** 6 categories with hand-crafted keyword lists (lines 176–213):
  - grading (25 keywords): grade, curve, harsh, lenient, etc.
  - lectures (30 keywords): teach, clear, boring, engaging, pace, etc.
  - workload (20 keywords): homework, assignment, reading, overwhelming, etc.
  - approachability (18 keywords): office hours, helpful, friendly, rude, etc.
  - exams (18 keywords): exam, midterm, final, quiz, study, etc.
  - ~~overall~~ (no explicit seed; uniform prior used)

**Training (lines 317–337):**
- Builds initial word counts from seeds (line 227–240)
- Semi-supervised update (line 317–337): classifies each review to top category, adds observed words if confidence > 0.35
- **Smoothing:** Laplace (add-α = 1.0, line 215)

**Classification (lines 264–307):**
- Tokenizes: lowercase, strip punctuation, remove 41 stopwords (lines 248–261)
- Log-sum-exp trick for numerical stability (line 296–305)
- Returns posterior probability per category (0–1)

**Aggregated Sentiment by Category (lines 339–374):**
- For each review, identifies top categories (posterior ≥ 0.25)
- Computes average clarity+helpfulness score across reviews in that category
- **Output:**
  ```json
  "category_sentiment": {
    "grading": {
      "mean_sentiment": 3.5,
      "n_reviews": 12,
      "pct_positive": 66.7  # % of reviews with clarity/helpful ≥ 3.5
    }
  }
  ```
- **Used in API for FitQuiz (api.py line 379–407) and CompareMode visualization**

### 2.3 Model 3: Gaussian Process Regression (lines 390–618)

**Class:** `GaussianProcessRegression`

**Kernel:** RBF (squared exponential)
- Formula: k(x, x') = σ² exp(−‖x−x'‖² / (2ℓ²))
- Hyperparameters (line 868–872):
  - length_scale = 6.0 (smooth over ~6 months)
  - signal_variance = 1.0 (amplitude)
  - noise_variance = 0.8 (observation noise)
- **No prior optimization; fixed hyperparameters**

**Training Data:**
- Extracts (date, rating) pairs from reviews (line 545–560)
- Parses RMP date format, converts to months since first review
- **Requires ≥2 data points with dates** (line 481–487)

**Prediction:**
- Predicts at 20 evenly-spaced time points (line 585–588)
- Returns mean + std for each point
- 95% CI: mean ± 1.96·std (lines 608–615)
- **Output:**
  ```json
  "gp_trend": {
    "pred_dates": ["2023-01", "2023-02", ...],
    "pred_mean": [3.2, 3.3, 3.5, ...],
    "pred_std": [0.4, 0.35, 0.3, ...],
    "pred_ci_lower": [2.4, 2.62, ...],
    "pred_ci_upper": [4.0, 3.98, ...],
    "n_data_points": 42,
    "date_range": "2023-01 to 2025-12"
  }
  ```

**Trend Summary (lines 721–744):**
- Plain English description based on first vs. last quarter means:
  - Δ > 0.5: "Significantly improving"
  - 0.5 ≥ Δ > 0.3: "Trending upward recently"
  - etc.

### 2.4 Analysis Pipeline (lines 625–853)

**Main Function:** `analyze_professor(prof, bb_model, nb_model, gp_model)`

**Processing Steps:**

1. **Rating Summary (lines 630–650):**
   - Computes overall rating = (clarity + helpfulness) / 2
   - Applies Beta-Binomial at three thresholds
   - Would-take-again posterior from {1, 0, −1} values

2. **Category Sentiment (lines 652–664):**
   - Classifies reviews, builds sentiment by category

3. **Grade Probabilities (lines 669–691):**
   - Counts self-reported grades, bins into A/B/C/D-F ranges
   - Outputs percentages (sum to 100%)

4. **Review Highlights (lines 693–719):**
   - Scores reviews by: upvotes − downvotes + length bonus + recency bonus
   - Returns top 5 (capped at 500 chars each)

5. **Verdict (lines 762–796):**
   - Decision tree on P(good) and difficulty:
     - P(good) ≥ 0.85 && diff ≤ 2.5 → "Highly rated with manageable workload" (great)
     - P(good) ≥ 0.85 → "Tough but excellent" (great)
     - P(good) ≥ 0.65 && diff ≤ 3.0 → "Well liked, reasonable" (good)
     - P(good) ≥ 0.65 → "Good teaching, hard work" (good)
     - P(good) ≥ 0.45 → "Mixed reviews" (mixed)
     - P(good) ≥ 0.30 → "Below average" (caution)
     - else → "Most had tough time" (poor)
   - Appends trend info if improving/declining

6. **Confidence Level (lines 746–761):**
   - Based on n and CI width:
     - n ≥ 100 && CI < 0.15 → "Very high"
     - n ≥ 30 && CI < 0.30 → "High"
     - n ≥ 10 → "Moderate"
     - else → "Low"

7. **Class Breakdown (lines 798–821):**
   - Per-course avg rating + grade distribution (top 5)
   - Only includes courses with ≥2 reviews

**Output Schema (lines 823–853):**
```json
{
  "professor_id": str,
  "legacy_id": int,
  "name": str,
  "department": str,
  "summary": {
    "avg_rating": float,
    "avg_difficulty": float,
    "num_ratings": int,
    "would_take_again_pct": float
  },
  "verdict": str,
  "verdict_emoji": str (great/good/mixed/caution/poor),
  "confidence_level": str,
  "confidence_detail": str,
  "trend_summary": str,
  "grade_probabilities": {A range, B range, C range, D/F},
  "review_highlights": [{comment, class, grade, date, clarity, helpful, difficulty}],
  "class_breakdown": [{class_name, num_reviews, avg_rating, grades}],
  "bayesian_analysis": {
    "rating_posteriors": {excellent, good, acceptable},
    "sub_rating_posteriors": {clarity, helpfulness, difficulty},
    "would_take_again_posterior": {alpha, beta, mean, variance, ...}
  },
  "category_sentiment": {grading, lectures, workload, approachability, exams},
  "gp_trend": {pred_dates, pred_mean, pred_std, pred_ci_lower, pred_ci_upper, ...},
  "grade_distribution": {A+, A, A−, B+, ...},
  "top_tags": [{tag, count}]
}
```

### 2.5 Pipeline Execution (lines 856–900)

**Command:** `python bayesian_pipeline.py --input data/umich.json --output data/umich_analyzed.json`

**Steps:**
1. Loads raw JSON from scraper
2. Initializes three models with fixed hyperparameters
3. Trains NaiveBayes on all reviews (semi-supervised)
4. Analyzes each professor
5. Saves analyzed JSON + metadata (analyzed_at timestamp)
6. Prints summary: each prof's P(good) + 95% CI

---

## 3. FastAPI Backend (`api.py`)

**Framework:** FastAPI 0.3.0  
**Port:** 8000 (local) / Render (prod)

### 3.1 Infrastructure

**Rate Limiting (lines 39–85):**
- 60 requests/minute per IP
- Health checks exempt
- Cache headers: 3600s for professor data, 300s for school list, 600s default

**CORS (lines 87–94):**
- Allows `localhost:3000`, `localhost:5173`, `*.vercel.app`
- Only GET requests

**Keep-Alive (lines 24–37):**
- Daemon thread pings `/api/health` every 10 min (prevent Render free tier sleep)

### 3.2 Data Loading

**LRU Cache (lines 98–166):**
- In-memory cache of 10 school datasets max
- Lazy metadata parse (first 5000 chars) for school discovery

**School Discovery (lines 106–143):**
- Scans `data/*_analyzed.json` files
- Returns: slug, name, professor count, review count

---

### 3.3 API Endpoints

| Method | Path | Params | Returns |
|--------|------|--------|---------|
| GET | `/` | — | `{service, schools: count}` |
| GET | `/api/health` | — | `{status: "ok"}` |
| GET | `/api/schools` | — | `{schools: [{slug, name, professors, reviews}]}` |
| GET | `/api/{school}/professors` | `search`, `department`, `sort_by` (rating/difficulty/num_ratings/name), `limit` | `{count, professors: [...]}` with `bayesian_good_prob`, `confidence_level`, `trend_summary`, `verdict`, `verdict_emoji`, `grade_probabilities`, `top_tags` |
| GET | `/api/{school}/professors/{professor_id}` | — | Full professor object (entire analyzed JSON entry) |
| GET | `/api/{school}/departments` | — | `{departments: [{name, professor_count, avg_rating}]}` |
| GET | `/api/{school}/stats` | — | `{school, total_professors, total_reviews, avg_rating, avg_difficulty, departments}` |
| GET | `/api/{school}/compare` | `ids` (comma-separated) | `{professors: [...]}` (full profiles) |
| GET | `/api/{school}/fit` | `difficulty`, `grading`, `lectures`, `approachability`, `workload` (1–5), `department` (opt), `limit` | `{count, preferences: {...}, results: [...]}` with `fit_score` (0–100), `fit_reasons` (list), verdict, grade_probs, bayesian_good_prob |
| GET | `/api/{school}/courses` | `search` (opt) | `{courses: [{name, professors: [...], total_reviews}]}` |
| GET | `/api/{school}/schedule` | `courses` (comma-separated codes) | `{courses: [...], results: {course: [{id, name, department, verdict, verdict_emoji, avg_rating, avg_difficulty, would_take_again_pct, bayesian_good_prob, grade_probabilities, course_specific: {avg_rating, num_reviews, grades}}]}}` |
| GET | `/api/{school}/optimize` | `courses`, `preference` (balanced/easy/challenge) | `{courses: [...], preference: str, recommended: {course: prof}, alternatives: {course: [profs]}, semester_prediction: {avg_difficulty, avg_quality, estimated_gpa, difficulty_label, ...}, warnings: [...]}` |

### 3.4 Complex Endpoint Details

#### `/api/{school}/fit` (Fit Quiz, lines 317–476)

**Fit Score Algorithm (lines 357–424):**
1. **Difficulty match (weight 2.0):**
   - pref 1–2: rewards low difficulty (score = (5−diff)/4 · 100)
   - pref 4–5: rewards high difficulty (score = diff/5 · 100)
   - pref 3: neutral, rewards diff ≈ 3.0
2. **Category sentiment matches (weight 1.5–2.5):**
   - For each of {grading, lectures, approachability, workload}:
     - Looks up category_sentiment pct_positive
     - Importance = pref_val / 5.0
     - If pref ≥ 4: weight 2.5, penalize low scores by 0.6×
     - If pref ≤ 2: weight 0.5
     - Else: weight 1.5
3. **Quality bonus (weight 1.5):** rating/5 · 100
4. **Would-take-again bonus (weight 1.0):** wta%
5. **Normalize to 0–100 and apply confidence penalty:**
   - n < 10: −15%
   - n < 20: −8%

**Output Fields (lines 454–469):**
- `fit_score` (0–100)
- `fit_reasons` (up to 3 explanations)
- verdict, verdict_emoji, confidence_level
- grade_probabilities, bayesian_good_prob, avg_rating, avg_difficulty, num_ratings, would_take_again_pct

#### `/api/{school}/optimize` (Semester Optimizer, lines 549–680)

**For Each Course (lines 562–615):**
- Finds all professors teaching that course
- Computes composite score based on preference:
  - **Easy:** (rating/5)×0.2 + (1−diff/5)×0.35 + A%×0.25 + wta_score×0.2
  - **Challenge:** (rating/5)×0.4 + P(good)×0.3 + wta_score×0.2 + (diff/5)×0.1
  - **Balanced:** (rating/5)×0.3 + P(good)×0.25 + A%×0.2 + wta_score×0.15 + (1−diff/5)×0.1
- Confidence penalty: n<5 → ×0.8, n<10 → ×0.9
- Rank by score

**Semester Prediction (lines 636–649):**
- Average difficulty/rating across recommended professors
- Estimated GPA from grade_probabilities (A=3.8, B=3.0, C=2.0, D/F=0.8)
- Difficulty label: "Very heavy" (≥4.0), "Challenging" (≥3.5), "Manageable" (≥2.5), "Light" (<2.5)

**Warnings (lines 619–633):**
- Difficulty ≥ 4.0
- would_take_again_pct < 40%
- bayesian_good_prob < 0.4
- No professor data

---

## 4. Frontend Architecture

**Technology:** React 18 (Vite), Recharts for charts, Tailwind CSS  
**Routing:** Hash-based, no React Router

### 4.1 App Layout

**File:** `frontend/src/App.jsx` (191 lines)

**Route Modes:**
- (empty) → Landing page
- `/school/{slug}` → Browse mode (list, filters, sort)
- `/school/{slug}/prof/{id}` → Detail mode
- `/school/{slug}/quiz` → Fit Quiz
- `/school/{slug}/compare` → Compare Mode
- `/school/{slug}/schedule` → Schedule Helper
- (no `/optimize` route; integrated into SemesterOptimizer)

**State Management:**
- `schools` (array)
- `professors` (paginated list)
- `departments` (dropdown)
- `stats` (school-level)
- `profDetail` (full professor object)
- `search`, `deptFilter`, `sortBy`

**Lifecycle:**
- Fetch schools on mount
- Fetch professors/departments/stats when school changes
- Keep-alive ping every 10 min (line 46–51)

### 4.2 Component Hierarchy

#### Landing (`Landing.jsx`, 104 lines)
**Props:** `schools: []`, `onSelectSchool: (slug) → void`  
**Displays:**
- Hero copy: "Know your professor before you register"
- School search + dropdown
- Feature badges: Confidence ratings, Grade predictions, Semester optimizer, etc.
- Default sort: UMich first, then A–Z

#### ProfessorList (`ProfessorList.jsx`, 103 lines)
**Props:** `professors: []`, `loading`, `onSelect`  
**Displays (per professor):**
- Badge with Bayesian "grade" (A+/A/B+/B/C+/C/D based on `bayesian_good_prob` thresholds)
- Name, department
- Verdict excerpt (first sentence)
- Red flags (if would_take_again < 35%, avg_rating < 2.5, difficulty ≥ 4.5, declining)
- Stats (hidden on mobile): avg_rating, difficulty label, % get A, % would retake, review count

#### ProfessorDetail (`ProfessorDetail.jsx`, 357 lines)
**Props:** `professor` (full analyzed object)  
**Components:**
1. **VerdictBanner:** Verdict text, confidence level, trend, red flags (colored by emoji)
2. **BottomLine:** 2×2 grid of Quality/Difficulty/Your grade/Would retake
3. **ProfVibe (category sentiment):** Bar charts for each category with % positive
4. **ReviewHighlights:** Up to 3 highest-scored reviews with class, grade, date
5. **TrendChart (GP):** Area chart of pred_dates/pred_mean with confidence band (ci_range)
6. **GradeChart:** Bar chart of grade distribution (A+, A, A−, B+, ...) with color coding
7. **CourseBreakdown:** Top 8 courses with avg_rating + review count
8. **Tags:** Student-generated tags with frequency weighting
9. **BayesianDetails (collapsed):** Shows all three posterior thresholds (excellent/good/acceptable) with CI's in plain text

#### FitQuiz (`FitQuiz.jsx`, 134 lines)
**Props:** `school`, `departments`, `onSelect`, `onClose`  
**Quiz Questions:** 5 sliders (difficulty, grading, lectures, approachability, workload), each 1–5  
**Department Filter:** Optional  
**Results:**
- Ranked list of professors by fit_score (0–100)
- FitRing visualization (circular progress bar, color-coded by score)
- Fit reasons (e.g., "Low difficulty matches your preference")
- Quick stats: avg_rating, avg_difficulty, num_ratings

#### CompareMode (`CompareMode.jsx`, ~200 lines)
**Props:** `school`, `professors`, `onSelect`, `onClose`  
**Features:**
- Search to add 2–4 professors
- Side-by-side comparison table (rows for each stat)
- Radar chart of category sentiment (5 dimensions)
- Highlights best in each stat with ★

#### ScheduleHelper (`ScheduleHelper.jsx`, ~250 lines)
**Props:** `school`, `onSelect`, `onClose`  
**Features:**
- Course code input with autocomplete
- Per-course professor ranking
- Displays best professor (★), then alternates, with verdict emoji + course-specific rating

#### SemesterOptimizer (`SemesterOptimizer.jsx`, ~250 lines)
**Props:** `school`, `onSelect`, `onClose`  
**Features:**
- Multi-course input
- Preference selector: Easy / Balanced / Challenge
- Semester prediction card (avg_difficulty, avg_quality, est_gpa, difficulty_label)
- Warnings list
- Alternative professors per course
- "Build a schedule" with visual selection

---

## 5. Data Flow & Schema

### 5.1 Raw Data Shape (`data/umich.json`)

Example: one professor + 2 reviews
```json
{
  "metadata": {
    "school_name": "University of Michigan",
    "school_id": "U2Nob29sLTEyNTg=",
    "city": "Ann Arbor Charter Twp",
    "state": "MI",
    "total_professors": 426,
    "total_reviews": 13846,
    "scraped_at": "2026-03-29T05:15:10.719186+00:00"
  },
  "professors": [
    {
      "id": "VGVhY2hlci0zMDY5MTA3",
      "legacy_id": 3069107,
      "first_name": "Salam",
      "last_name": "Aboulhassan",
      "department": "Sociology",
      "avg_rating": 4.1,
      "avg_difficulty": 2.3,
      "num_ratings": 19,
      "would_take_again_pct": 73.6842,
      "top_tags": [{"tag": "Clear", "count": 8}, {"tag": "Lecture notes", "count": 5}],
      "reviews": [
        {
          "id": "123abc",
          "class_name": "SOC100",
          "date": "2025-12-10",
          "comment": "The content isn't hard, but the tests are difficult...",
          "helpful_rating": 3,
          "clarity_rating": 3,
          "difficulty_rating": 3,
          "would_take_again": 1,
          "grade": "A-",
          "is_online": false,
          "is_for_credit": true,
          "attendance_mandatory": false,
          "thumbs_up": 5,
          "thumbs_down": 1
        }
      ]
    }
  ]
}
```
**File size:** 20–40 MB for 400–650 profs × 20–40 reviews each

### 5.2 Analyzed Data Shape (`data/umich_analyzed.json`)

**Structure (see lines 1–357 of ProfessorDetail.jsx for UI consumption):**
- `metadata` (added `analyzed_at`)
- `analysis` (array of professors)
  - Each professor has all fields from raw + Bayesian results
  - Bayesian results added by analyze_professor() (lines 823–853)

**Key Derived Fields:**
- `verdict`, `verdict_emoji`, `confidence_level`, `confidence_detail` (from decision tree)
- `trend_summary` (from GP)
- `grade_probabilities` (A/B/C/D-F percentages)
- `review_highlights` (scored subset of reviews)
- `bayesian_analysis` (posteriors + sub-ratings + would_take_again)
- `category_sentiment` (grading/lectures/workload/approachability/exams)
- `gp_trend` (time series + CI bands)
- `grade_distribution` (full histogram A+...F)
- `top_tags` (from RMP)
- `class_breakdown` (per-course stats)

**Example (umich_analyzed.json excerpt):**
```json
{
  "professor_id": "VGVhY2hlci0zMDY5MTA3",
  "name": "Salam Aboulhassan",
  "summary": {"avg_rating": 4.1, "avg_difficulty": 2.3, "num_ratings": 19, "would_take_again_pct": 73.6842},
  "verdict": "Well liked with reasonable difficulty",
  "verdict_emoji": "good",
  "confidence_level": "Moderate",
  "confidence_detail": "Based on 19 reviews, decent sample but could shift with more data",
  "bayesian_analysis": {
    "rating_posteriors": {
      "good": {
        "alpha": 16.0,
        "beta": 7.0,
        "mean": 0.6957,
        "variance": 0.008822,
        "std": 0.0939,
        "ci_lower": 0.5116,
        "ci_upper": 0.8797,
        "n_ratings": 19,
        "n_above_threshold": 14,
        "threshold": 3.5
      }
    }
  }
}
```

---

## 6. Uncertainty Quantification & UI Integration

### 6.1 Where Uncertainty Appears in UI

**ProfessorDetail:**
1. **Verdict Banner (line 38–55):**
   - Shows confidence_level (Very High / High / Moderate / Low)
   - Shows confidence_detail (e.g., "Based on 19 reviews, decent sample...")
   - Red flags displayed below

2. **Bayesian Details (collapsed, lines 278–309):**
   - Shows all three posteriors (excellent/good/acceptable)
   - Displays 95% credible intervals as `[ci_lower%, ci_upper%]`
   - Text: "These are Beta-Binomial posterior probabilities"

3. **TrendChart (lines 163–193):**
   - Plots `pred_mean` as line
   - Area under `pred_ci_range` as confidence band
   - Widens/narrows with data sparsity

### 6.2 No Explicit UI for Other Uncertainty Sources

- **Sub-rating posteriors (clarity/helpful/difficulty):** Stored in JSON but not visualized
- **Would-take-again posterior:** Used internally in verdict but CI not displayed
- **Naive Bayes category probabilities:** Only `pct_positive` shown, not full posterior
- **GP standard deviations:** Used for CI but not shown as separate bars

---

## 7. Currently Missing: Bayesian Hierarchy & Shrinkage

### 7.1 What's NOT Implemented

1. **No hierarchical model:** Each professor analyzed independently
2. **No empirical Bayes:** Priors are fixed, not learned from data
3. **No department-level shrinkage:** No Beta(α_dept, β_dept) that borrows strength across department
4. **No school-level borrowing:** No hierarchical model across schools
5. **No calibration:** No validation that 95% CI's actually contain the "true" rating 95% of the time
6. **No feedback loop:** No online learning as new reviews arrive

### 7.2 Opportunities for Bayesian Expansion

- **Hierarchical Beta-Binomial:** Estimate per-department priors, shrink individuals toward department mean
- **Empirical Bayes:** Use marginal likelihood or moment matching to learn α₀, β₀ from data
- **Cross-school borrowing:** Model school effects if same professors teach at multiple schools
- **Calibration testing:** Evaluate whether CI's have correct coverage on held-out test sets
- **Active learning:** Prioritize data collection for high-variance professors

---

## 8. Sentiment & Topic Processing

### 8.1 Sentiment Aggregation (category_sentiment)

**Pipeline:**
1. Each review is classified by NaiveBayes to top 1–N categories (threshold 0.25)
2. Per category, average the clarity + helpful ratings
3. Compute % of reviews in that category with (clarity or helpful) ≥ 3.5
4. **Result:** `{grading: {mean_sentiment, n_reviews, pct_positive}, ...}`

**Usage:**
- API `/fit` endpoint uses `pct_positive` to score category preferences (line 386)
- ProfVibe component (line 108–133) visualizes as bar chart
- CompareMode radar chart (line 69–73) uses category_sentiment values

### 8.2 Tag Processing

- **Source:** RMP's teacherRatingTags (scraped in rmp_scraper.py line 79–82)
- **Storage:** `top_tags: [{tag, count}]`
- **UI:** Tags component (line 249–268) shows tags with opacity scaled by count

**Not Processed:**
- ratingTags per review (scraped but not analyzed)
- No topic model beyond Naive Bayes categories
- No word embeddings or modern NLP

---

## 9. Grade Distribution & Prediction

### 9.1 Grade Collection

**Source:** Review grade field (self-reported)  
**Processing (lines 669–691):**
- Filters out: "Not sure yet", "Rather not say", "Incomplete", "Drop/Withdrawal", "Audit/No Grade", "N/A"
- Counts remaining, groups into 4 buckets:
  - A range: A+, A, A−
  - B range: B+, B, B−
  - C range: C+, C, C−
  - D/F: D+, D, D−, F
- Outputs percentage for each bucket

**Usage:**
- ProfessorList (line 45–46): Maps `bayesian_good_prob` to color-coded letter grade (A/B+/B/C+/C/D)
- BottomLine (line 80–83): Shows "% get an A" and prediction (Likely A / Probably B+ / etc.)
- FitQuiz bonus (line 417–449): Adds reasoning if grading pref matches A%
- SemesterOptimizer GPA estimation (line 642–649): Maps grade letter to GPA (A=3.8, B=3.0, etc.)

---

## 10. Course-Specific Breakdown

**Processing (lines 798–821):**
- Aggregates by class_name from reviews
- Filters: only courses with ≥2 reviews
- Computes avg_rating + top 5 grades per course

**UI:**
- CourseBreakdown component (line 224–245): Displays top 8 courses with rating + review count
- ScheduleHelper (line 122–150): Shows course-specific avg_rating + grades for each professor option
- SemesterOptimizer: Allows filtering by course if desired

---

## 11. API Security & Infrastructure

### 11.1 Authentication
- **None.** Public API, rate-limited by IP.

### 11.2 Rate Limiting
- 60 req/min/IP (line 44)
- Health checks exempted

### 11.3 Cache Headers
- Professor data: 3600s (1 hour)
- School list: 300s (5 min)
- Other: 600s

### 11.4 CORS
- Allows: localhost dev + *.vercel.app
- GET only

### 11.5 Security Headers
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- Referrer-Policy: strict-origin-when-cross-origin

---

## 12. Known Limitations

### Data
1. **Coverage:** Not all professors at each school (only ~400–650 per school with ≥3 reviews)
2. **Recency:** Stale if not re-scraped; no real-time updates
3. **Selection bias:** RateMyProfessors users ≠ random sample of all students
4. **Self-reported grades:** Unreliable (students may exaggerate)

### Models
1. **Fixed hyperparameters:** No hyperparameter tuning
2. **No calibration:** Unknown whether 95% CI's have correct coverage
3. **Weak priors:** Beta(2,2) is arbitrary; no sensitivity analysis
4. **Naive Bayes assumes word independence:** Unrealistic for natural language
5. **GP time scale:** Fixed 6-month length scale; no adaptation to individual trends

### Inference
1. **No multivariate model:** Ratings treated independently; no correlation structure
2. **No missing-data handling:** Incomplete reviews filtered out
3. **No outlier detection:** All reviews weighted equally

### UI
1. **No confidence intervals displayed** except in collapsed Bayesian details
2. **Fit score heuristic-based:** No Bayesian model of student-prof compatibility
3. **No uncertainty propagation:** Semester optimizer doesn't account for Professor uncertainty

---

## 13. Deployment & Operations

### 13.1 Backend Deployment
- **Host:** Render (free tier, sleeps after inactivity)
- **Keep-alive:** Self-ping every 10 min via daemon thread
- **Process:** `uvicorn api:app --reload --port 8000`

### 13.2 Frontend Deployment
- **Host:** Vercel
- **Build:** Vite SPA, static output
- **API routing:** Dev: Vite proxy → localhost:8000; Prod: direct to Render backend

### 13.3 Data Pipeline
- **Manual:** Run `bulk_update.py --all` to scrape + analyze all schools
- **Or incremental:** `deep_scrape.py --school umich --push` to deep scrape + push to GitHub

---

## 14. Configuration

### config.js (Frontend)
```javascript
export const API_BASE = import.meta.env.VITE_API_URL || ''
```
- In dev: empty (Vite proxy handles `/api` → localhost:8000)
- In prod: set to Render backend URL via `.env`

### Environment Variables (Not Captured)
- None in code; RMP API uses public auth token embedded in frontend JS

---

## 15. Files Not Yet Analyzed (Out of Scope)

- Frontend styling (CSS/Tailwind config)
- Build configuration (Vite, package.json)
- Exact GitHub workflow / CI-CD setup
- Database layer (none; JSON-based)

---

## 16. Entry Points for Bayesian Expansion

### Immediate Wins (Low Complexity)
1. **Sensitivity analysis:** Vary α₀, β₀; show impact on verdicts
2. **Calibration plot:** Compute empirical coverage of 95% CI's
3. **Prior visualization:** Show prior vs. posterior in detail view
4. **Missing data:** Imputation for incomplete reviews

### Medium Complexity
1. **Department-level empirical Bayes:** Learn α_dept, β_dept from data
2. **Robust posterior:** Student-t or Laplace likelihood instead of binomial
3. **Multi-year trend:** Model rating change + volatility separately

### High Complexity
1. **Hierarchical Bayesian regression:** Model rating ~ difficulty + class size + year (fixed effects) + prof (random effect)
2. **Item-response theory:** Model review quality/informativeness, downweight spam
3. **Collaborative filtering:** Predict missing reviews using professor similarity
4. **Online learning:** Update posteriors incrementally as new reviews arrive

---

## Appendix: Sample API Responses

### GET /api/schools
```json
{
  "schools": [
    {"slug": "umich", "name": "University of Michigan", "professors": 426, "reviews": 13846},
    {"slug": "mit", "name": "Massachusetts Institute of Technology", "professors": 145, "reviews": 9823}
  ]
}
```

### GET /api/umich/professors?sort_by=rating&limit=3
```json
{
  "count": 3,
  "professors": [
    {
      "id": "abc123",
      "name": "John Smith",
      "department": "EECS",
      "avg_rating": 4.7,
      "avg_difficulty": 3.2,
      "num_ratings": 87,
      "would_take_again_pct": 92.5,
      "verdict": "Highly rated with a manageable workload",
      "verdict_emoji": "great",
      "confidence_level": "Very high",
      "trend_summary": "Consistently highly rated",
      "grade_probabilities": {"A range": 95.0, "B range": 4.8, "C range": 0.2, "D/F": 0.0},
      "bayesian_good_prob": 0.96,
      "bayesian_ci_lower": 0.93,
      "bayesian_ci_upper": 0.98,
      "top_tags": [{"tag": "Clear", "count": 45}, {"tag": "Engaging", "count": 32}]
    }
  ]
}
```

### GET /api/umich/fit?difficulty=4&grading=2&lectures=5&approachability=3&workload=4
```json
{
  "count": 20,
  "preferences": {
    "difficulty": 4,
    "grading": 2,
    "lectures": 5,
    "approachability": 3,
    "workload": 4
  },
  "results": [
    {
      "id": "xyz789",
      "name": "Jane Doe",
      "department": "MATH",
      "fit_score": 89.3,
      "fit_reasons": [
        "Challenging, as you prefer",
        "Strong lectures (87% positive)",
        "72% chance of A"
      ],
      "verdict": "Tough course, but students consistently rate the teaching highly",
      "avg_rating": 4.5,
      "avg_difficulty": 4.1,
      "grade_probabilities": {"A range": 72.0, "B range": 22.0, "C range": 6.0, "D/F": 0.0},
      "bayesian_good_prob": 0.88,
      "confidence_level": "High"
    }
  ]
}
```

---

**End of Audit Document**
