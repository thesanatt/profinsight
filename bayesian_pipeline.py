"""
ProfInsight - Bayesian ML Pipeline
===================================
Three Bayesian models that turn raw RMP reviews into actionable insights:

1. Beta-Binomial Rating Model   → honest rating posteriors with uncertainty
2. Naive Bayes Classifier       → categorize review text into topics
3. Gaussian Process Regression  → rating trends over time with confidence bands

Usage:
    python ml/bayesian_pipeline.py --input data/umich_test.json --output data/umich_analyzed.json
"""

import json
import math
import re
import argparse
import os
from collections import Counter, defaultdict
from datetime import datetime
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════════════
# MODEL 1: Beta-Binomial Rating Posterior
# ═══════════════════════════════════════════════════════════════════════════════
#
# Instead of showing "3.7/5" as a point estimate, we model the posterior
# distribution of the true quality using a Beta distribution.
#
# Key insight from EECS 498: A professor with 3 reviews averaging 5.0 should
# look VERY different from one with 300 reviews averaging 4.2. The Beta
# posterior captures this uncertainty naturally.
#
# We convert 1-5 star ratings to binary (good/not good threshold) and compute
# Beta(alpha, beta) posterior. We also compute posteriors at multiple
# thresholds and for sub-ratings (clarity, helpfulness, difficulty).

class BetaBinomialModel:
    """
    Beta-Binomial model for professor ratings.

    Prior: Beta(alpha_0, beta_0) - weakly informative, centered at population mean.
    Likelihood: Binomial (rating >= threshold counts as success).
    Posterior: Beta(alpha_0 + successes, beta_0 + failures).
    """

    def __init__(self, prior_alpha: float = 2.0, prior_beta: float = 2.0):
        """
        Args:
            prior_alpha: Prior successes (higher = stronger prior toward good).
            prior_beta: Prior failures (higher = stronger prior toward bad).
            Default Beta(2,2) is weakly informative, centered at 0.5.
        """
        self.prior_alpha = prior_alpha
        self.prior_beta = prior_beta

    def compute_posterior(self, ratings: list, threshold: float = 3.5) -> dict:
        """
        Compute Beta posterior for P(true_quality >= threshold).

        Args:
            ratings: List of numeric ratings (1-5 scale).
            threshold: What counts as "good" (default 3.5).

        Returns:
            Dict with posterior parameters and summary statistics.
        """
        if not ratings:
            return {
                "alpha": self.prior_alpha,
                "beta": self.prior_beta,
                "mean": self.prior_alpha / (self.prior_alpha + self.prior_beta),
                "variance": self._beta_variance(self.prior_alpha, self.prior_beta),
                "ci_lower": 0.0,
                "ci_upper": 1.0,
                "n_ratings": 0,
                "n_above_threshold": 0,
                "threshold": threshold,
            }

        successes = sum(1 for r in ratings if r >= threshold)
        failures = len(ratings) - successes

        alpha_post = self.prior_alpha + successes
        beta_post = self.prior_beta + failures

        mean = alpha_post / (alpha_post + beta_post)
        variance = self._beta_variance(alpha_post, beta_post)

        # 95% credible interval using normal approximation
        # (exact would use scipy.stats.beta.ppf, but we avoid the dependency)
        std = math.sqrt(variance)
        ci_lower = max(0.0, mean - 1.96 * std)
        ci_upper = min(1.0, mean + 1.96 * std)

        return {
            "alpha": alpha_post,
            "beta": beta_post,
            "mean": round(mean, 4),
            "variance": round(variance, 6),
            "std": round(std, 4),
            "ci_lower": round(ci_lower, 4),
            "ci_upper": round(ci_upper, 4),
            "n_ratings": len(ratings),
            "n_above_threshold": successes,
            "threshold": threshold,
        }

    def compute_multi_threshold(self, ratings: list) -> dict:
        """Compute posteriors at multiple thresholds for richer insight."""
        thresholds = {
            "excellent": 4.5,
            "good": 3.5,
            "acceptable": 2.5,
        }
        return {
            name: self.compute_posterior(ratings, thresh)
            for name, thresh in thresholds.items()
        }

    def compute_sub_rating_posteriors(self, reviews: list) -> dict:
        """Compute posteriors for each sub-rating dimension."""
        dimensions = {
            "clarity": [r["clarity_rating"] for r in reviews if r.get("clarity_rating")],
            "helpfulness": [r["helpful_rating"] for r in reviews if r.get("helpful_rating")],
            "difficulty": [r["difficulty_rating"] for r in reviews if r.get("difficulty_rating")],
        }

        results = {}
        for dim_name, dim_ratings in dimensions.items():
            if dim_ratings:
                # For difficulty, invert: low difficulty = good
                if dim_name == "difficulty":
                    # Threshold: difficulty < 3.5 means "not too hard"
                    results[dim_name] = self.compute_posterior(
                        [5 - r for r in dim_ratings],  # invert scale
                        threshold=1.5,
                    )
                    results[dim_name]["raw_mean"] = round(
                        sum(dim_ratings) / len(dim_ratings), 2
                    )
                else:
                    results[dim_name] = self.compute_posterior(dim_ratings, threshold=3.5)
                    results[dim_name]["raw_mean"] = round(
                        sum(dim_ratings) / len(dim_ratings), 2
                    )
        return results

    @staticmethod
    def _beta_variance(alpha: float, beta: float) -> float:
        return (alpha * beta) / ((alpha + beta) ** 2 * (alpha + beta + 1))


# ═══════════════════════════════════════════════════════════════════════════════
# MODEL 2: Naive Bayes Review Classifier
# ═══════════════════════════════════════════════════════════════════════════════
#
# Classifies each review into topic categories using Multinomial Naive Bayes.
# P(category | words) ∝ P(words | category) * P(category)
#
# Categories: grading, lectures, workload, approachability, exams, overall
#
# We use a keyword-seeded approach: manually seed category word lists,
# then use Bayes' theorem to classify. No LLM needed.

class NaiveBayesClassifier:
    """
    Multinomial Naive Bayes for review topic classification.

    Seeded with domain-specific keyword priors, then classifies
    each review into one or more topic categories.
    """

    # Keyword seeds for each category (domain knowledge as prior)
    CATEGORY_SEEDS = {
        "grading": [
            "grade", "grades", "grading", "graded", "grader", "curve", "curved",
            "curving", "gpa", "rubric", "points", "deductions", "harsh", "lenient",
            "fair", "unfair", "partial credit", "extra credit", "regrade",
            "generous", "strict", "tough grader", "easy grader", "a+", "a-", "b+",
            "b-", "c+", "c-", "d", "f", "pass", "fail", "credit",
        ],
        "lectures": [
            "lecture", "lectures", "lecturing", "lecturer", "class", "teaching",
            "taught", "teach", "explains", "explanation", "clear", "confusing",
            "boring", "engaging", "interesting", "slides", "notes", "powerpoint",
            "presentation", "understand", "clarity", "organized", "disorganized",
            "monotone", "enthusiastic", "passionate", "dry", "pace", "fast", "slow",
            "examples", "concepts", "material", "content",
        ],
        "workload": [
            "homework", "hw", "assignments", "assignment", "workload", "work",
            "reading", "readings", "pages", "hours", "time", "busy", "heavy",
            "light", "manageable", "overwhelming", "problem sets", "psets", "lab",
            "labs", "project", "projects", "paper", "papers", "essay", "essays",
            "weekly", "daily", "nightly",
        ],
        "approachability": [
            "office hours", "office", "hours", "helpful", "help", "available",
            "email", "responsive", "approachable", "friendly", "nice", "kind",
            "caring", "supportive", "rude", "mean", "intimidating", "cold",
            "dismissive", "patient", "understanding", "accessible", "welcoming",
            "encouraging", "mentor",
        ],
        "exams": [
            "exam", "exams", "test", "tests", "midterm", "midterms", "final",
            "finals", "quiz", "quizzes", "study", "studying", "review",
            "practice", "multiple choice", "free response", "open book",
            "closed book", "cheat sheet", "proctored", "tricky", "straightforward",
            "memorization", "conceptual", "application",
        ],
    }

    def __init__(self, smoothing: float = 1.0):
        """
        Args:
            smoothing: Laplace smoothing parameter (alpha in add-alpha smoothing).
        """
        self.smoothing = smoothing
        self.vocab = set()
        self.category_word_counts = {}
        self.category_total_words = {}
        self.category_prior = {}
        self._build_from_seeds()

    def _build_from_seeds(self):
        """Initialize model from keyword seeds."""
        for category, words in self.CATEGORY_SEEDS.items():
            word_counts = Counter()
            for w in words:
                for token in w.lower().split():
                    word_counts[token] += 3  # boost seed words
                    self.vocab.add(token)
            self.category_word_counts[category] = word_counts
            self.category_total_words[category] = sum(word_counts.values())

        # Uniform prior over categories
        n_cats = len(self.CATEGORY_SEEDS)
        self.category_prior = {cat: 1.0 / n_cats for cat in self.CATEGORY_SEEDS}

    def _tokenize(self, text: str) -> list:
        """Simple whitespace + punctuation tokenizer."""
        text = text.lower()
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        tokens = text.split()
        # Remove very short tokens and stopwords
        stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "shall", "can", "to", "of", "in", "for",
            "on", "with", "at", "by", "from", "as", "into", "through", "during",
            "before", "after", "above", "below", "between", "out", "off", "over",
            "under", "again", "further", "then", "once", "here", "there", "when",
            "where", "why", "how", "all", "each", "every", "both", "few", "more",
            "most", "other", "some", "such", "no", "nor", "not", "only", "own",
            "same", "so", "than", "too", "very", "just", "because", "but", "and",
            "or", "if", "while", "about", "up", "it", "its", "this", "that",
            "i", "me", "my", "we", "our", "you", "your", "he", "she", "they",
            "his", "her", "him", "them", "their", "what", "which", "who",
        }
        return [t for t in tokens if len(t) > 1 and t not in stopwords]

    def classify(self, text: str) -> dict:
        """
        Classify a review into topic categories.

        Returns dict mapping category -> posterior probability.
        Uses log probabilities to avoid underflow.
        """
        tokens = self._tokenize(text)
        if not tokens:
            # Return uniform if no useful tokens
            n = len(self.CATEGORY_SEEDS)
            return {cat: round(1.0 / n, 4) for cat in self.CATEGORY_SEEDS}

        vocab_size = len(self.vocab) + 1000  # buffer for unseen words

        log_posteriors = {}
        for category in self.CATEGORY_SEEDS:
            # Log prior
            log_p = math.log(self.category_prior[category])

            # Log likelihood: P(words | category)
            total = self.category_total_words[category]
            word_counts = self.category_word_counts[category]

            for token in tokens:
                count = word_counts.get(token, 0)
                # Laplace smoothed probability
                log_p += math.log((count + self.smoothing) / (total + self.smoothing * vocab_size))

            log_posteriors[category] = log_p

        # Convert log posteriors to probabilities (log-sum-exp trick)
        max_log = max(log_posteriors.values())
        exp_posteriors = {
            cat: math.exp(lp - max_log) for cat, lp in log_posteriors.items()
        }
        total_exp = sum(exp_posteriors.values())

        posteriors = {
            cat: round(exp_p / total_exp, 4)
            for cat, exp_p in exp_posteriors.items()
        }

        return posteriors

    def classify_top_categories(self, text: str, threshold: float = 0.25) -> list:
        """Return categories with posterior probability above threshold."""
        posteriors = self.classify(text)
        return sorted(
            [(cat, prob) for cat, prob in posteriors.items() if prob >= threshold],
            key=lambda x: -x[1],
        )

    def train_on_reviews(self, reviews: list):
        """
        Update word counts from actual review data (semi-supervised).
        Uses the seed-based classification to label, then adds those
        words back to strengthen the model.
        """
        for review in reviews:
            comment = review.get("comment", "")
            if not comment:
                continue

            tokens = self._tokenize(comment)
            posteriors = self.classify(comment)
            top_cat = max(posteriors, key=posteriors.get)

            # Only update if reasonably confident
            if posteriors[top_cat] > 0.35:
                for token in tokens:
                    self.category_word_counts[top_cat][token] += 1
                    self.category_total_words[top_cat] += 1
                    self.vocab.add(token)

    def get_sentiment_by_category(self, reviews: list) -> dict:
        """
        For each category, compute average rating of reviews that
        belong to that category. This gives per-topic sentiment.
        """
        category_ratings = defaultdict(list)

        for review in reviews:
            comment = review.get("comment", "")
            if not comment:
                continue

            top_cats = self.classify_top_categories(comment, threshold=0.25)
            # Use clarity + helpfulness average as the sentiment score
            clarity = review.get("clarity_rating")
            helpful = review.get("helpful_rating")
            scores = [s for s in [clarity, helpful] if s is not None]
            if not scores:
                continue
            avg_score = sum(scores) / len(scores)

            for cat, prob in top_cats:
                category_ratings[cat].append(avg_score)

        results = {}
        for cat, ratings in category_ratings.items():
            if ratings:
                mean = sum(ratings) / len(ratings)
                results[cat] = {
                    "mean_sentiment": round(mean, 2),
                    "n_reviews": len(ratings),
                    "pct_positive": round(
                        sum(1 for r in ratings if r >= 3.5) / len(ratings) * 100, 1
                    ),
                }
        return results


# ═══════════════════════════════════════════════════════════════════════════════
# MODEL 3: Gaussian Process Regression (Lightweight)
# ═══════════════════════════════════════════════════════════════════════════════
#
# Models rating trends over time with uncertainty quantification.
# Uses the RBF (squared exponential) kernel.
#
# Key EECS 498 connection: GP gives us a posterior distribution over functions,
# not just a single trend line. The confidence band widens where we have
# fewer data points - honest about uncertainty.
#
# This is a pure NumPy implementation to avoid heavy dependencies.

class GaussianProcessRegression:
    """
    Gaussian Process Regression with RBF kernel.

    Given (time, rating) observations, predicts the rating trend
    at any time point with uncertainty (mean ± std).
    """

    def __init__(
        self,
        length_scale: float = 1.0,
        signal_variance: float = 1.0,
        noise_variance: float = 0.5,
    ):
        """
        RBF kernel: k(x, x') = signal_var * exp(-||x-x'||^2 / (2 * length_scale^2))

        Args:
            length_scale: How smooth the trend is (larger = smoother).
            signal_variance: Overall amplitude of variation.
            noise_variance: Observation noise (rating noise).
        """
        self.length_scale = length_scale
        self.signal_variance = signal_variance
        self.noise_variance = noise_variance

    def _rbf_kernel(self, x1: list, x2: list) -> list:
        """Compute RBF kernel matrix between x1 and x2."""
        n1, n2 = len(x1), len(x2)
        K = [[0.0] * n2 for _ in range(n1)]
        for i in range(n1):
            for j in range(n2):
                sq_dist = (x1[i] - x2[j]) ** 2
                K[i][j] = self.signal_variance * math.exp(
                    -sq_dist / (2 * self.length_scale ** 2)
                )
        return K

    def _add_noise(self, K: list) -> list:
        """Add noise to diagonal."""
        n = len(K)
        result = [row[:] for row in K]
        for i in range(n):
            result[i][i] += self.noise_variance
        return result

    def _cholesky(self, A: list) -> Optional[list]:
        """Cholesky decomposition A = LL^T. Returns L or None if not PD."""
        n = len(A)
        L = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1):
                s = sum(L[i][k] * L[j][k] for k in range(j))
                if i == j:
                    val = A[i][i] - s
                    if val <= 0:
                        # Add jitter and retry
                        return None
                    L[i][j] = math.sqrt(val)
                else:
                    L[i][j] = (A[i][j] - s) / L[j][j]
        return L

    def _solve_triangular_lower(self, L: list, b: list) -> list:
        """Solve Lx = b where L is lower triangular."""
        n = len(b)
        x = [0.0] * n
        for i in range(n):
            x[i] = (b[i] - sum(L[i][j] * x[j] for j in range(i))) / L[i][i]
        return x

    def _solve_triangular_upper(self, L: list, b: list) -> list:
        """Solve L^T x = b where L is lower triangular."""
        n = len(b)
        x = [0.0] * n
        for i in range(n - 1, -1, -1):
            x[i] = (b[i] - sum(L[j][i] * x[j] for j in range(i + 1, n))) / L[i][i]
        return x

    def predict(self, x_train: list, y_train: list, x_test: list) -> dict:
        """
        GP prediction at test points.

        Args:
            x_train: Training inputs (time values, e.g., months since first review).
            y_train: Training outputs (ratings).
            x_test: Test inputs (points to predict at).

        Returns:
            Dict with "mean" and "std" lists for each test point.
        """
        if len(x_train) < 2:
            # Not enough data for GP - return prior
            prior_mean = sum(y_train) / len(y_train) if y_train else 3.0
            return {
                "mean": [prior_mean] * len(x_test),
                "std": [math.sqrt(self.signal_variance)] * len(x_test),
            }

        n = len(x_train)

        # Compute kernel matrices
        K = self._rbf_kernel(x_train, x_train)
        K_noisy = self._add_noise(K)
        K_star = self._rbf_kernel(x_test, x_train)
        K_star_star = self._rbf_kernel(x_test, x_test)

        # Cholesky decomposition of K + noise*I
        L = self._cholesky(K_noisy)
        if L is None:
            # Add more jitter
            for i in range(n):
                K_noisy[i][i] += 0.1
            L = self._cholesky(K_noisy)
            if L is None:
                prior_mean = sum(y_train) / len(y_train)
                return {
                    "mean": [prior_mean] * len(x_test),
                    "std": [1.0] * len(x_test),
                }

        # Solve for alpha = (K + noise*I)^{-1} * y
        alpha_intermediate = self._solve_triangular_lower(L, y_train)
        alpha = self._solve_triangular_upper(L, alpha_intermediate)

        # Predictive mean: K_star @ alpha
        m = len(x_test)
        pred_mean = [0.0] * m
        for i in range(m):
            pred_mean[i] = sum(K_star[i][j] * alpha[j] for j in range(n))

        # Predictive variance
        pred_std = [0.0] * m
        for i in range(m):
            v = self._solve_triangular_lower(L, K_star[i])
            var = K_star_star[i][i] - sum(vj ** 2 for vj in v)
            pred_std[i] = math.sqrt(max(var, 1e-6))

        return {
            "mean": [round(m, 3) for m in pred_mean],
            "std": [round(s, 3) for s in pred_std],
        }

    def fit_professor_trend(self, reviews: list, n_prediction_points: int = 20) -> dict:
        """
        Fit a GP to a professor's rating history.

        Args:
            reviews: List of review dicts with "date" and rating fields.
            n_prediction_points: Number of evenly-spaced points to predict at.

        Returns:
            Dict with time points, predicted means, and confidence bands.
        """
        # Extract (time, rating) pairs
        data_points = []
        for r in reviews:
            date_str = r.get("date", "")
            clarity = r.get("clarity_rating")
            helpful = r.get("helpful_rating")
            scores = [s for s in [clarity, helpful] if s is not None]
            if not scores or not date_str:
                continue

            try:
                # Parse the date (RMP format: "2026-01-07 16:23:26 +0000 UTC")
                dt = datetime.strptime(date_str[:19], "%Y-%m-%d %H:%M:%S")
                avg_score = sum(scores) / len(scores)
                data_points.append((dt, avg_score))
            except (ValueError, IndexError):
                continue

        if len(data_points) < 2:
            return {"insufficient_data": True, "n_reviews_with_dates": len(data_points)}

        # Sort by date
        data_points.sort(key=lambda x: x[0])

        # Convert dates to months since first review
        first_date = data_points[0][0]
        x_train = []
        y_train = []
        dates_raw = []
        for dt, score in data_points:
            months = (dt - first_date).days / 30.44
            x_train.append(months)
            y_train.append(score)
            dates_raw.append(dt.strftime("%Y-%m"))

        # Prediction grid
        x_min, x_max = min(x_train), max(x_train)
        span = x_max - x_min
        if span < 1:
            span = 12  # at least show 1 year

        x_test = [
            x_min + i * span / (n_prediction_points - 1)
            for i in range(n_prediction_points)
        ]

        # Convert test points back to dates for the frontend
        test_dates = []
        for x in x_test:
            days_offset = x * 30.44
            from datetime import timedelta
            test_dt = first_date + timedelta(days=days_offset)
            test_dates.append(test_dt.strftime("%Y-%m"))

        # Fit GP
        result = self.predict(x_train, y_train, x_test)

        return {
            "insufficient_data": False,
            "train_dates": dates_raw,
            "train_ratings": [round(y, 2) for y in y_train],
            "pred_dates": test_dates,
            "pred_mean": result["mean"],
            "pred_std": result["std"],
            "pred_ci_lower": [
                round(max(1.0, m - 1.96 * s), 3)
                for m, s in zip(result["mean"], result["std"])
            ],
            "pred_ci_upper": [
                round(min(5.0, m + 1.96 * s), 3)
                for m, s in zip(result["mean"], result["std"])
            ],
            "n_data_points": len(data_points),
            "date_range": f"{dates_raw[0]} to {dates_raw[-1]}",
        }


# ═══════════════════════════════════════════════════════════════════════════════
# ANALYSIS PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_professor(prof: dict, bb_model, nb_model, gp_model) -> dict:
    """Run all three Bayesian models on a single professor."""
    reviews = prof.get("reviews", [])

    # --- Beta-Binomial ---
    # Overall rating posterior
    overall_ratings = [
        (r.get("clarity_rating", 0) + r.get("helpful_rating", 0)) / 2
        for r in reviews
        if r.get("clarity_rating") and r.get("helpful_rating")
    ]
    rating_posterior = bb_model.compute_multi_threshold(overall_ratings)
    sub_rating_posteriors = bb_model.compute_sub_rating_posteriors(reviews)

    # Would-take-again posterior
    wta_values = [r["would_take_again"] for r in reviews if r.get("would_take_again") is not None]
    # would_take_again: 1 = yes, 0 = no, -1 = N/A
    wta_yes = sum(1 for v in wta_values if v == 1)
    wta_no = sum(1 for v in wta_values if v == 0)
    wta_total = wta_yes + wta_no
    if wta_total > 0:
        wta_posterior = bb_model.compute_posterior(
            [5.0] * wta_yes + [1.0] * wta_no, threshold=3.0
        )
    else:
        wta_posterior = None

    # --- Naive Bayes ---
    category_sentiment = nb_model.get_sentiment_by_category(reviews)

    # Classify each review
    review_categories = []
    for r in reviews:
        comment = r.get("comment", "")
        if comment:
            cats = nb_model.classify_top_categories(comment, threshold=0.25)
            review_categories.append({
                "review_id": r.get("id"),
                "top_categories": [{"category": c, "probability": p} for c, p in cats],
            })

    # --- Gaussian Process ---
    gp_trend = gp_model.fit_professor_trend(reviews)

    # --- Grade Distribution ---
    grade_counts = Counter()
    for r in reviews:
        grade = r.get("grade")
        if grade and grade not in ("Not sure yet", "Rather not say", "Incomplete", "Drop/Withdrawal", "Audit/No Grade", "N/A"):
            grade_counts[grade] += 1

    # --- Grade Probabilities (student-friendly) ---
    grade_total = sum(grade_counts.values())
    grade_groups = {"A range": 0, "B range": 0, "C range": 0, "D/F": 0}
    for g, c in grade_counts.items():
        if g.startswith("A"):
            grade_groups["A range"] += c
        elif g.startswith("B"):
            grade_groups["B range"] += c
        elif g.startswith("C"):
            grade_groups["C range"] += c
        else:
            grade_groups["D/F"] += c
    grade_probabilities = {
        k: round(v / grade_total * 100, 1) if grade_total > 0 else 0
        for k, v in grade_groups.items()
    }

    # --- Review Highlights (top 3 most useful) ---
    scored_reviews = []
    for r in reviews:
        comment = r.get("comment", "").strip()
        if not comment or len(comment) < 30:
            continue
        # Score: upvotes + length bonus + recency bonus
        score = (r.get("thumbs_up", 0) - r.get("thumbs_down", 0))
        score += min(len(comment) / 200, 2.0)  # length bonus, capped
        try:
            dt = datetime.strptime(r.get("date", "")[:10], "%Y-%m-%d")
            years_ago = (datetime.now() - dt).days / 365
            score += max(0, 3 - years_ago)  # recency bonus
        except (ValueError, TypeError):
            pass
        scored_reviews.append({
            "comment": comment[:500],  # cap length
            "class_name": r.get("class_name", ""),
            "grade": r.get("grade", ""),
            "date": r.get("date", "")[:10],
            "clarity": r.get("clarity_rating"),
            "helpful": r.get("helpful_rating"),
            "difficulty": r.get("difficulty_rating"),
            "score": score,
        })
    scored_reviews.sort(key=lambda x: -x["score"])
    review_highlights = scored_reviews[:5]

    # --- Trend Summary (plain English from GP) ---
    trend_summary = "Not enough data"
    if not gp_trend.get("insufficient_data") and len(gp_trend.get("pred_mean", [])) >= 4:
        means = gp_trend["pred_mean"]
        first_quarter = sum(means[:len(means)//4]) / max(len(means)//4, 1)
        last_quarter = sum(means[-(len(means)//4):]) / max(len(means)//4, 1)
        diff = last_quarter - first_quarter
        recent_mean = means[-1]

        if abs(diff) < 0.3:
            if recent_mean >= 4.0:
                trend_summary = "Consistently highly rated"
            elif recent_mean >= 3.0:
                trend_summary = "Stable, middle-of-the-road ratings"
            else:
                trend_summary = "Consistently low rated"
        elif diff > 0.5:
            trend_summary = "Significantly improving over time"
        elif diff > 0.3:
            trend_summary = "Trending upward recently"
        elif diff < -0.5:
            trend_summary = "Declining over time"
        elif diff < -0.3:
            trend_summary = "Trending downward recently"

    # --- Confidence Level (plain English from Beta-Binomial) ---
    n = len(overall_ratings)
    good_post = rating_posterior.get("good", {})
    ci_width = (good_post.get("ci_upper", 1) - good_post.get("ci_lower", 0))
    if n >= 100 and ci_width < 0.15:
        confidence_level = "Very high"
        confidence_detail = f"Based on {n} reviews, this is a reliable picture"
    elif n >= 30 and ci_width < 0.30:
        confidence_level = "High"
        confidence_detail = f"Based on {n} reviews, fairly reliable"
    elif n >= 10:
        confidence_level = "Moderate"
        confidence_detail = f"Based on {n} reviews, decent sample but could shift with more data"
    else:
        confidence_level = "Low"
        confidence_detail = f"Only {n} reviews so far, take these numbers with a grain of salt"

    # --- Verdict (the headline) ---
    good_prob = good_post.get("mean", 0.5)
    difficulty = prof.get("avg_difficulty", 3.0) or 3.0
    wta_pct = prof.get("would_take_again_pct")
    if wta_pct and wta_pct < 0:
        wta_pct = None

    if good_prob >= 0.85 and difficulty <= 2.5:
        verdict = "Highly rated with a manageable workload"
        verdict_emoji = "great"
    elif good_prob >= 0.85:
        verdict = "Tough course, but students consistently rate the teaching highly"
        verdict_emoji = "great"
    elif good_prob >= 0.65 and difficulty <= 3.0:
        verdict = "Well liked with reasonable difficulty"
        verdict_emoji = "good"
    elif good_prob >= 0.65:
        verdict = "Good teaching but expect to put in the work"
        verdict_emoji = "good"
    elif good_prob >= 0.45:
        verdict = "Mixed reviews. Student experiences vary quite a bit"
        verdict_emoji = "mixed"
    elif good_prob >= 0.30:
        verdict = "Below average reviews. Worth checking if this fits your learning style"
        verdict_emoji = "caution"
    else:
        verdict = "Most students had a tough time. Look into alternatives if you can"
        verdict_emoji = "poor"

    # Adjust verdict with trend info
    if "improving" in trend_summary.lower():
        verdict += ", but ratings have been improving recently"
    elif "declining" in trend_summary.lower():
        verdict += ", and ratings have been declining"

    # --- Class-specific breakdown ---
    class_data = defaultdict(lambda: {"ratings": [], "grades": [], "count": 0})
    for r in reviews:
        cls = r.get("class_name", "").strip()
        if not cls:
            continue
        class_data[cls]["count"] += 1
        scores = [s for s in [r.get("clarity_rating"), r.get("helpful_rating")] if s]
        if scores:
            class_data[cls]["ratings"].append(sum(scores) / len(scores))
        if r.get("grade"):
            class_data[cls]["grades"].append(r["grade"])

    class_breakdown = []
    for cls, info in sorted(class_data.items(), key=lambda x: -x[1]["count"]):
        if info["count"] < 2:
            continue
        avg_r = round(sum(info["ratings"]) / len(info["ratings"]), 1) if info["ratings"] else None
        class_breakdown.append({
            "class_name": cls,
            "num_reviews": info["count"],
            "avg_rating": avg_r,
            "grades": dict(Counter(info["grades"]).most_common(5)),
        })

    return {
        "professor_id": prof["id"],
        "legacy_id": prof.get("legacy_id"),
        "name": f"{prof['first_name']} {prof['last_name']}",
        "department": prof.get("department", "Unknown"),
        "summary": {
            "avg_rating": prof.get("avg_rating"),
            "avg_difficulty": prof.get("avg_difficulty"),
            "num_ratings": prof.get("num_ratings"),
            "would_take_again_pct": prof.get("would_take_again_pct"),
        },
        # Student-friendly layer
        "verdict": verdict,
        "verdict_emoji": verdict_emoji,
        "confidence_level": confidence_level,
        "confidence_detail": confidence_detail,
        "trend_summary": trend_summary,
        "grade_probabilities": grade_probabilities,
        "review_highlights": review_highlights,
        "class_breakdown": class_breakdown,
        # Bayesian layer (for the nerds / expandable section)
        "bayesian_analysis": {
            "rating_posteriors": rating_posterior,
            "sub_rating_posteriors": sub_rating_posteriors,
            "would_take_again_posterior": wta_posterior,
        },
        "category_sentiment": category_sentiment,
        "gp_trend": gp_trend,
        "grade_distribution": dict(grade_counts.most_common()),
        "top_tags": prof.get("top_tags", []),
    }


def run_pipeline(input_path: str, output_path: str):
    """Run the full Bayesian analysis pipeline."""
    print(f"Loading data from {input_path}...")
    with open(input_path, "r") as f:
        data = json.load(f)

    professors = data.get("professors", [])
    print(f"Found {len(professors)} professors.")

    # Initialize models
    bb_model = BetaBinomialModel(prior_alpha=2.0, prior_beta=2.0)
    nb_model = NaiveBayesClassifier(smoothing=1.0)
    gp_model = GaussianProcessRegression(
        length_scale=6.0,       # smooth over ~6 months
        signal_variance=1.0,
        noise_variance=0.8,     # ratings are noisy
    )

    # Optional: train NB on the actual review data first (semi-supervised)
    all_reviews = [r for p in professors for r in p.get("reviews", [])]
    print(f"Training Naive Bayes on {len(all_reviews)} reviews...")
    nb_model.train_on_reviews(all_reviews)

    # Analyze each professor
    print("Running Bayesian analysis...")
    results = []
    for i, prof in enumerate(professors):
        name = f"{prof['first_name']} {prof['last_name']}"
        print(f"  [{i+1}/{len(professors)}] {name}...")
        analysis = analyze_professor(prof, bb_model, nb_model, gp_model)
        results.append(analysis)

    output = {
        "metadata": data.get("metadata", {}),
        "analysis": results,
    }
    output["metadata"]["analyzed_at"] = datetime.now().isoformat()

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nAnalysis saved to {output_path}")
    print(f"  Professors analyzed: {len(results)}")

    # Quick summary
    for r in results:
        name = r["name"]
        good = r["bayesian_analysis"]["rating_posteriors"]["good"]
        print(f"  {name}: P(good) = {good['mean']:.2f} [{good['ci_lower']:.2f}, {good['ci_upper']:.2f}] (n={good['n_ratings']})")


def main():
    parser = argparse.ArgumentParser(description="ProfInsight Bayesian ML Pipeline")
    parser.add_argument("--input", type=str, required=True, help="Input JSON from scraper")
    parser.add_argument("--output", type=str, required=True, help="Output analyzed JSON")
    args = parser.parse_args()
    run_pipeline(args.input, args.output)


if __name__ == "__main__":
    main()
