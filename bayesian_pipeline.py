"""
ProfInsight - Bayesian ML Pipeline
===================================
Turns one school's raw RMP reviews into per-professor posteriors:

1. Beta-Binomial rating model with empirical-Bayes priors (bayesian_calibration)
2. Naive Bayes topic classifier trained on tag weak labels (train_classifier.py)
3. Gaussian process on monthly-binned rating history with credible bands
plus grade forecast, recency weighting, outlier flagging (bayesian_advanced)
and grade-inflation adjustment, teaching attributes (bayesian_honest).
Every model has a held-out number in metrics/latest.md (evaluate.py).

Usage:
    python bayesian_pipeline.py --input data/umich.json --output data/umich_analyzed.json.gz
"""

import json
import math
import re
import argparse
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from bayesian_calibration import (
    BetaPrior,
    DEFAULT_PRIOR_ALPHA,
    DEFAULT_PRIOR_BETA,
    beta_credible_interval,
    build_good_rating_pairs,
    build_take_again_pairs,
    decision_summary,
    fit_empirical_bayes_beta,
    group_by_department,
    posterior_from_counts,
)
from bayesian_advanced import (
    flag_outlier_reviews,
    personal_grade_forecast,
    recency_vs_plain_delta,
    recency_weighted_counts,
)
from bayesian_honest import (
    extract_teaching_attributes,
    fit_grade_inflation_beta,
    grade_adjusted_quality,
)
from datafiles import dump_json, load_json


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
            variance = self._beta_variance(self.prior_alpha, self.prior_beta)
            lo, hi = beta_credible_interval(self.prior_alpha, self.prior_beta, 0.95)
            return {
                "alpha": self.prior_alpha,
                "beta": self.prior_beta,
                "mean": round(self.prior_alpha / (self.prior_alpha + self.prior_beta), 4),
                "variance": round(variance, 6),
                "std": round(math.sqrt(variance), 4),
                "ci_lower": round(lo, 4),
                "ci_upper": round(hi, 4),
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
        std = math.sqrt(variance)

        # Exact equal-tailed 95% credible interval via numerical CDF inversion.
        # Previously this used a normal approximation, which overflows [0, 1]
        # and is wrong for skewed Betas (small n or extreme ratings).
        ci_lower, ci_upper = beta_credible_interval(alpha_post, beta_post, 0.95)

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

    # NOTE: an earlier version "self-trained" the seed model on its own
    # predictions. Scored against tag-derived weak labels, that step pushed
    # top-1 accuracy below the majority-class baseline, so it was removed.
    # Current numbers: metrics/latest.md (evaluate.py, classifier section).

    def fit(self, texts: list, labels: list, uniform_prior: bool = False):
        """
        Supervised multinomial NB fit from (text, category) pairs.

        Replaces the seed counts entirely. Class priors are the empirical
        label frequencies unless uniform_prior=True.
        """
        cats = list(self.CATEGORY_SEEDS)
        self.vocab = set()
        self.category_word_counts = {c: Counter() for c in cats}
        self.category_total_words = {c: 0 for c in cats}
        label_counts = Counter()
        for text, label in zip(texts, labels):
            if label not in self.category_word_counts:
                continue
            tokens = self._tokenize(text)
            self.category_word_counts[label].update(tokens)
            self.category_total_words[label] += len(tokens)
            self.vocab.update(tokens)
            label_counts[label] += 1
        n = sum(label_counts.values()) or 1
        if uniform_prior:
            self.category_prior = {c: 1.0 / len(cats) for c in cats}
        else:
            # Laplace-smoothed so an unseen class never gets log(0)
            self.category_prior = {c: (label_counts[c] + 1) / (n + len(cats)) for c in cats}
        self.n_training_docs = n

    def to_dict(self) -> dict:
        return {
            "version": 1,
            "smoothing": self.smoothing,
            "n_training_docs": getattr(self, "n_training_docs", 0),
            "category_prior": self.category_prior,
            "category_word_counts": {c: dict(wc) for c, wc in self.category_word_counts.items()},
        }

    @classmethod
    def from_dict(cls, d: dict) -> "NaiveBayesClassifier":
        model = cls(smoothing=d.get("smoothing", 1.0))
        model.category_word_counts = {c: Counter(wc) for c, wc in d["category_word_counts"].items()}
        model.category_total_words = {c: sum(wc.values()) for c, wc in model.category_word_counts.items()}
        model.category_prior = dict(d["category_prior"])
        model.vocab = set()
        for wc in model.category_word_counts.values():
            model.vocab.update(wc)
        model.n_training_docs = d.get("n_training_docs", 0)
        return model

    def save(self, path: str):
        with open(path, "w") as f:
            json.dump(self.to_dict(), f)

    @classmethod
    def load(cls, path: str) -> "NaiveBayesClassifier":
        with open(path) as f:
            return cls.from_dict(json.load(f))

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
# Pure Python (lists of lists); no NumPy so the Render free tier stays light.

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

    def _add_noise(self, K: list, counts: Optional[list] = None) -> list:
        """Add observation noise to the diagonal. When `counts` is given each
        point is the mean of that many ratings, so its noise is
        noise_variance / count (heteroscedastic)."""
        n = len(K)
        result = [row[:] for row in K]
        for i in range(n):
            c = counts[i] if counts else 1
            result[i][i] += self.noise_variance / max(1, c)
        return result

    # Cap on GP training points. Reviews are binned by calendar month (mean
    # rating, count as weight); if a professor spans more months than this the
    # bin widens to 2, 3, 6 or 12 months. A pure-Python O(n^3) solve is fine at
    # a few hundred points and hopeless at 6,000 (BYU's most-reviewed
    # professor), which is why this exists.
    MAX_GP_POINTS = 240

    @classmethod
    def bin_by_month(cls, points: list, max_points: Optional[int] = None) -> tuple[list, list, list, int]:
        """
        Aggregate (datetime, rating) pairs into time bins.

        Returns (x_months, y_mean, counts, bin_width_months) where x is months
        since the first observation (bin centre = mean date of its ratings).

        >>> from datetime import datetime
        >>> pts = [(datetime(2020, 1, 5), 5.0), (datetime(2020, 1, 20), 3.0), (datetime(2020, 3, 1), 4.0)]
        >>> x, y, c, w = GaussianProcessRegression.bin_by_month(pts)
        >>> (len(x), y, c, w)
        (2, [4.0, 4.0], [2, 1], 1)
        """
        max_points = max_points or cls.MAX_GP_POINTS
        if not points:
            return [], [], [], 1
        points = sorted(points, key=lambda t: t[0])
        first = points[0][0]
        for width in (1, 2, 3, 6, 12, 24):
            bins: dict = {}
            for dt, y in points:
                key = ((dt.year - first.year) * 12 + (dt.month - first.month)) // width
                b = bins.setdefault(key, [0.0, 0, 0.0])
                b[0] += y
                b[1] += 1
                b[2] += (dt - first).days / 30.44
            if len(bins) <= max_points or width == 24:
                break
        xs, ys, cs = [], [], []
        for key in sorted(bins):
            total, n, months = bins[key]
            xs.append(months / n)
            ys.append(total / n)
            cs.append(n)
        return xs, ys, cs, width

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

    def _factor(self, x_train: list, counts: Optional[list] = None) -> Optional[list]:
        """Cholesky factor of K(x, x) + noise, with one jitter retry."""
        K_noisy = self._add_noise(self._rbf_kernel(x_train, x_train), counts)
        L = self._cholesky(K_noisy)
        if L is None:
            for i in range(len(x_train)):
                K_noisy[i][i] += 0.1
            L = self._cholesky(K_noisy)
        return L

    def log_marginal_likelihood(self, x_train: list, y_train: list, counts: Optional[list] = None) -> float:
        """
        Log marginal likelihood log p(y | x, hyperparameters) of the centered
        observations. Used for type-II maximum-likelihood selection of the
        length-scale in fit_professor_trend.

        log p(y) = -1/2 y^T (K + S)^{-1} y - sum log L_ii - n/2 log 2 pi
        """
        if len(x_train) < 2:
            return float("-inf")
        mu = sum(y_train) / len(y_train)
        y = [v - mu for v in y_train]
        L = self._factor(x_train, counts)
        if L is None:
            return float("-inf")
        alpha = self._solve_triangular_upper(L, self._solve_triangular_lower(L, y))
        n = len(y)
        return (
            -0.5 * sum(yi * ai for yi, ai in zip(y, alpha))
            - sum(math.log(L[i][i]) for i in range(n))
            - 0.5 * n * math.log(2.0 * math.pi)
        )

    def predict(self, x_train: list, y_train: list, x_test: list, counts: Optional[list] = None) -> dict:
        """
        GP prediction at test points.

        The GP is fit to observations centered on their mean (a constant mean
        function equal to the professor's average rating) and the mean is added
        back to the predictions. Without this, a zero-mean GP on a 1-5 rating
        scale reverts toward 0 in any gap wider than the length-scale; before
        centering, about half of all fitted trends dipped below the 1-star
        floor (metrics/latest.md, GP section).

        Args:
            x_train: Training inputs (time values, e.g., months since first review).
            y_train: Training outputs (ratings, or bin means).
            x_test: Test inputs (points to predict at).
            counts: Optional number of ratings behind each training point.

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
        if counts:
            mu = sum(y * c for y, c in zip(y_train, counts)) / sum(counts)
        else:
            mu = sum(y_train) / n
        y_centered = [y - mu for y in y_train]

        K_star = self._rbf_kernel(x_test, x_train)
        K_star_star = self._rbf_kernel(x_test, x_test)

        L = self._factor(x_train, counts)
        if L is None:
            return {
                "mean": [mu] * len(x_test),
                "std": [1.0] * len(x_test),
            }

        # Solve for alpha = (K + noise*I)^{-1} * (y - mu)
        alpha_intermediate = self._solve_triangular_lower(L, y_centered)
        alpha = self._solve_triangular_upper(L, alpha_intermediate)

        # Predictive mean: mu + K_star @ alpha
        m = len(x_test)
        pred_mean = [0.0] * m
        for i in range(m):
            pred_mean[i] = mu + sum(K_star[i][j] * alpha[j] for j in range(n))

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

    # Candidate length-scales (months) for type-II ML selection. Spans "one
    # semester" to "four years" so both fast swings and slow drifts are
    # representable; the marginal likelihood picks per professor.
    LENGTH_SCALE_GRID = (3.0, 6.0, 12.0, 24.0, 48.0)

    def select_length_scale(self, x_train: list, y_train: list, counts: Optional[list] = None) -> tuple[float, float]:
        """Pick the length-scale (months) with the highest log marginal likelihood.
        Returns (length_scale, log_marginal_likelihood)."""
        best_ls, best_ll = self.length_scale, float("-inf")
        original = self.length_scale
        for ls in self.LENGTH_SCALE_GRID:
            self.length_scale = ls
            ll = self.log_marginal_likelihood(x_train, y_train, counts)
            if ll > best_ll:
                best_ll, best_ls = ll, ls
        self.length_scale = original
        return best_ls, best_ll

    def fit_professor_trend(self, reviews: list, n_prediction_points: int = 20) -> dict:
        """
        Fit a GP to a professor's rating history.

        The length-scale is chosen per professor by maximizing the log marginal
        likelihood over LENGTH_SCALE_GRID (type-II maximum likelihood); the
        noise and signal variances stay fixed.

        Args:
            reviews: List of review dicts with "date" and rating fields.
            n_prediction_points: Number of evenly-spaced points to predict at.

        Returns:
            Dict with time points, predicted means, and credible bands.
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
        first_date = data_points[0][0]
        last_date = data_points[-1][0]

        # Bin by calendar month: mean rating per bin, count as weight. Keeps
        # the O(n^3) solve at a few hundred points for heavily reviewed profs.
        x_train, y_train, counts, bin_width = self.bin_by_month(data_points)
        dates_raw = [
            (first_date + timedelta(days=x * 30.44)).strftime("%Y-%m") for x in x_train
        ]

        # Prediction grid over the observed span
        x_min, x_max = 0.0, (last_date - first_date).days / 30.44
        span = x_max - x_min
        if span < 1:
            span = 12  # at least show 1 year

        x_test = [
            x_min + i * span / (n_prediction_points - 1)
            for i in range(n_prediction_points)
        ]

        # Convert test points back to dates for the frontend
        test_dates = [
            (first_date + timedelta(days=x * 30.44)).strftime("%Y-%m") for x in x_test
        ]

        # Fit GP with the length-scale chosen by marginal likelihood
        length_scale, lml = self.select_length_scale(x_train, y_train, counts)
        original = self.length_scale
        self.length_scale = length_scale
        try:
            result = self.predict(x_train, y_train, x_test, counts)
        finally:
            self.length_scale = original
        pred_mean = [round(min(5.0, max(1.0, m)), 3) for m in result["mean"]]

        return {
            "insufficient_data": False,
            "train_dates": dates_raw,
            "train_ratings": [round(y, 2) for y in y_train],
            "train_counts": counts,
            "bin_width_months": bin_width,
            "pred_dates": test_dates,
            "pred_mean": pred_mean,
            "pred_std": result["std"],
            "pred_ci_lower": [
                round(max(1.0, m - 1.96 * s), 3)
                for m, s in zip(pred_mean, result["std"])
            ],
            "pred_ci_upper": [
                round(min(5.0, m + 1.96 * s), 3)
                for m, s in zip(pred_mean, result["std"])
            ],
            "n_data_points": len(data_points),
            "date_range": f"{dates_raw[0]} to {dates_raw[-1]}",
            "length_scale_months": length_scale,
            "log_marginal_likelihood": round(lml, 3) if lml != float("-inf") else None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# MODEL 4: Empirical-Bayes calibration layer
# ═══════════════════════════════════════════════════════════════════════════════
#
# Lectures 2-4 (especially Lecture 2 p.3 on pseudocounts) motivate *where*
# the prior comes from. Instead of a fixed Beta(2, 2) for every professor
# regardless of school or department, we fit α, β by method of moments from
# the population of professors themselves.
#
# This is the fix for the "5.0 rating from 2 reviews" artifact: a small-n
# professor's posterior is now pulled toward their department's (or school's)
# observed mean, with the strength of pooling automatically determined by
# the between-professor variance.

def build_calibration_priors(professors: list) -> dict:
    """
    Fit school-level and per-department empirical-Bayes Beta priors.

    Returns:
        {
          "school":     {"good_rating": BetaPrior, "take_again": BetaPrior},
          "department": {<dept>: {"good_rating": BetaPrior, "take_again": BetaPrior}},
        }
    """
    # School-level priors
    school_good_pairs = build_good_rating_pairs(professors, threshold=3.5)
    school_wta_pairs = build_take_again_pairs(professors)
    school_priors = {
        "good_rating": fit_empirical_bayes_beta(school_good_pairs),
        "take_again": fit_empirical_bayes_beta(school_wta_pairs),
    }

    # Per-department priors (falls back to school prior if the department has
    # too few professors for a stable moment match).
    dept_priors: dict = {}
    for dept, profs in group_by_department(professors).items():
        if len(profs) < 10:
            # Too few to trust; use school prior
            dept_priors[dept] = school_priors
            continue
        good_pairs = build_good_rating_pairs(profs, threshold=3.5)
        wta_pairs = build_take_again_pairs(profs)
        dept_priors[dept] = {
            "good_rating": fit_empirical_bayes_beta(good_pairs),
            "take_again": fit_empirical_bayes_beta(wta_pairs),
        }

    return {"school": school_priors, "department": dept_priors}


def _pick_prior(priors: dict, department: str, key: str) -> BetaPrior:
    dept_map = priors["department"].get(department)
    if dept_map and key in dept_map:
        return dept_map[key]
    return priors["school"][key]


def _calibrated_block(professor: dict, priors: dict) -> dict:
    """
    Compute the calibrated posteriors + decision summaries for a single
    professor. Shape is stable so the frontend can rely on all subfields
    existing (with None where the underlying data is absent).
    """
    reviews = professor.get("reviews", [])
    dept = (professor.get("department") or "Unknown").strip() or "Unknown"

    # --- Good-rating posterior (rating ≥ 3.5 as "good") ---
    good_pairs = build_good_rating_pairs([professor], threshold=3.5)
    good_pair = good_pairs[0] if good_pairs else (0, 0)
    good_prior = _pick_prior(priors, dept, "good_rating")
    good_post = posterior_from_counts(good_pair[0], good_pair[1], good_prior)

    # --- Would-take-again posterior ---
    wta_pairs = build_take_again_pairs([professor])
    wta_prior = _pick_prior(priors, dept, "take_again")
    if wta_pairs:
        wta_post = posterior_from_counts(wta_pairs[0][0], wta_pairs[0][1], wta_prior)
    else:
        # No usable take-again data — degenerate to pure prior
        wta_post = posterior_from_counts(0, 0, wta_prior)

    return {
        "version": 1,
        "department_used": dept,
        "priors": {
            "good_rating": good_prior.as_dict(),
            "take_again": wta_prior.as_dict(),
        },
        "good_rating": {
            **good_post.as_dict(),
            "decision": decision_summary(good_post).as_dict(),
        },
        "take_again": {
            **wta_post.as_dict(),
            "decision": decision_summary(wta_post).as_dict(),
        },
    }


def _tag_posteriors(professor: dict, tag_base_rate: float = 0.2, concentration: float = 5.0) -> list:
    """
    Per-tag Beta-Binomial posterior.

    Each tag's (count, num_ratings) is treated as (successes, trials) against a
    mild Beta(α, β) prior centered at a `tag_base_rate`. This produces
    shrinkage-aware per-tag probabilities with honest credible bands — so tags
    from 3-review professors don't get confidently listed as "this prof is
    definitely a tough grader".

    We use a fixed weakly-informative prior here rather than a per-tag empirical
    Bayes fit because the cross-professor distribution of tags is extremely
    zero-inflated (most profs don't have most tags), which breaks the MoM fit.
    """
    num_ratings = max(0, int(professor.get("num_ratings") or 0))
    tag_alpha = concentration * tag_base_rate
    tag_beta = concentration * (1.0 - tag_base_rate)
    prior = BetaPrior(tag_alpha, tag_beta, source="fixed_tag_prior")

    rows = []
    for entry in (professor.get("top_tags") or []):
        name = entry.get("tag") or entry.get("name")
        count = int(entry.get("count") or 0)
        if not name:
            continue
        # Guard: some data has more tag applications than num_ratings (RMP
        # sometimes lets a reviewer pick multiple tags). Cap at num_ratings
        # so the posterior interpretation stays clean.
        cap = max(count, num_ratings)
        post = posterior_from_counts(count, cap, prior)
        rows.append({
            "tag": name,
            "count": count,
            "n": cap,
            "mean": round(post.mean, 4),
            "ci_lower": round(post.credible_interval(0.95)[0], 4),
            "ci_upper": round(post.credible_interval(0.95)[1], 4),
            "shrinkage": round(post.shrinkage_toward_prior(), 4),
        })
    rows.sort(key=lambda r: -r["mean"])
    return rows


# ═══════════════════════════════════════════════════════════════════════════════
# Essentials layer helpers — grade forecast baseline, recency-weighted read,
# outlier flagging. See bayesian_advanced.py for the underlying math.
# ═══════════════════════════════════════════════════════════════════════════════

def _grade_forecast_block(grade_probabilities: dict, n_graded_reviews: int) -> dict:
    """Base-rate forecast (no student GPA) in a frontend-friendly shape.

    The frontend's "Your probable grade" card takes these base-rate fields and
    re-runs the forecast client-side (or via API) once a student enters their
    GPA. Embedding the baseline makes first-paint cheap and gives downstream
    callers a sane default when the student skips the input.
    """
    if not grade_probabilities or not any(grade_probabilities.values()):
        return None
    forecast = personal_grade_forecast(
        grade_probabilities,
        student_gpa=None,
        n_reviews=int(n_graded_reviews),
    )
    return forecast.as_dict()


_LETTER_GRADES = {"A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F"}


def letter_grade(raw) -> Optional[str]:
    """
    Normalize a self-reported grade to a letter grade, or None for anything
    that is not one (blank, 'Not sure yet', 'Not_Sure_Yet', 'Pass', 'Audit', ...).

    >>> letter_grade("A-"), letter_grade(" b+ "), letter_grade("Not_Sure_Yet"), letter_grade("Pass")
    ('A-', 'B+', None, None)
    """
    if not raw:
        return None
    g = str(raw).strip().replace("_", " ").upper()
    return g if g in _LETTER_GRADES else None


def derive_top_tags(reviews: list, limit: int = 10) -> list:
    """
    Count the tags reviewers attached ('Tough grader--Caring--...') and return
    [{'tag': name, 'count': n}, ...] sorted by count. The scraper's professor
    search does not return tag totals, so this is where top_tags comes from.

    >>> derive_top_tags([{"rating_tags": "Caring--Tough grader"}, {"rating_tags": "Caring"}])
    [{'tag': 'Caring', 'count': 2}, {'tag': 'Tough grader', 'count': 1}]
    """
    counts = Counter()
    for r in reviews:
        for t in (r.get("rating_tags") or "").split("--"):
            t = t.strip()
            if t:
                counts[t] += 1
    return [{"tag": t, "count": c} for t, c in counts.most_common(limit)]


def _recency_block(prof: dict, priors: dict, now: Optional[datetime] = None) -> dict:
    """Recency-weighted view of the two headline posteriors (good-rating and
    take-again). Each observation contributes exponentially-decaying pseudocount
    mass so a prof who *used* to be great but has been slipping shows the
    slippage on the headline number, not just in the GP trend chart.

    `plain_mean` is the posterior mean under the same prior with unweighted
    counts, so the two numbers differ only by the recency weighting.
    """
    reviews = prof.get("reviews", [])
    if not reviews:
        return None

    dept = (prof.get("department") or "Unknown").strip() or "Unknown"
    good_prior = _pick_prior(priors, dept, "good_rating")
    wta_prior = _pick_prior(priors, dept, "take_again")

    # Stamp each review with its average-score "good" bit (threshold 3.5)
    stamped = []
    for r in reviews:
        c = r.get("clarity_rating")
        h = r.get("helpful_rating")
        if c is None or h is None:
            continue
        avg = (c + h) / 2
        stamped.append({
            "date": r.get("date") or "",
            "good": avg >= 3.5,
            "take_again": r.get("would_take_again"),
        })

    good_s, good_t = recency_weighted_counts(stamped, "good", now=now)
    wta_s, wta_t = recency_weighted_counts(
        stamped, "take_again", now=now,
        success_values={1}, non_success_values={0},
    )

    # Fractional posterior update — Beta(α + Σw·x, β + Σw·(1-x))
    good_mean = (good_prior.alpha + good_s) / (good_prior.alpha + good_prior.beta + good_t) if good_t > 0 else good_prior.mean
    wta_mean = (wta_prior.alpha + wta_s) / (wta_prior.alpha + wta_prior.beta + wta_t) if wta_t > 0 else wta_prior.mean

    # Same prior, unweighted counts: the only difference is the recency weighting.
    good_n = sum(1 for s in stamped)
    good_x = sum(1 for s in stamped if s["good"])
    wta_n = sum(1 for s in stamped if s["take_again"] in (0, 1))
    wta_x = sum(1 for s in stamped if s["take_again"] == 1)
    plain_good = (good_prior.alpha + good_x) / (good_prior.alpha + good_prior.beta + good_n) if good_n else None
    plain_wta = (wta_prior.alpha + wta_x) / (wta_prior.alpha + wta_prior.beta + wta_n) if wta_n else None

    return {
        "good_rating_recent": {
            "mean": round(good_mean, 4),
            "effective_n": round(good_t, 2),
            "plain_mean": round(plain_good, 4) if plain_good is not None else None,
            "note": recency_vs_plain_delta(good_mean, plain_good) if plain_good is not None else None,
        },
        "take_again_recent": {
            "mean": round(wta_mean, 4),
            "effective_n": round(wta_t, 2),
            "plain_mean": round(plain_wta, 4) if plain_wta is not None else None,
            "note": recency_vs_plain_delta(wta_mean, plain_wta) if plain_wta is not None else None,
        },
        "half_life_days": int(3 * 365.25),
    }


def prof_good_plain(prof: dict, threshold: float = 3.5) -> Optional[float]:
    """Unweighted MLE for "fraction of reviews with avg ≥ threshold"."""
    ok, total = 0, 0
    for r in prof.get("reviews", []):
        c = r.get("clarity_rating")
        h = r.get("helpful_rating")
        if c is None or h is None:
            continue
        total += 1
        if (c + h) / 2 >= threshold:
            ok += 1
    return ok / total if total else None


def prof_wta_plain(prof: dict) -> Optional[float]:
    """Unweighted MLE for take-again proportion."""
    yes = sum(1 for r in prof.get("reviews", []) if r.get("would_take_again") == 1)
    no = sum(1 for r in prof.get("reviews", []) if r.get("would_take_again") == 0)
    return yes / (yes + no) if (yes + no) else None


def _review_quality_block(reviews: list) -> dict:
    """Flag reviews whose sentiment is inconsistent with the rest (potential
    trolls or malicious downvotes). Returned as per-review probabilities so
    the frontend can choose to dim, move, or hide them."""
    if not reviews:
        return None
    out = flag_outlier_reviews(reviews)
    # Attach review_id for stable referencing (the frontend uses ids in review_highlights).
    ids = [r.get("id") for r in reviews]
    return {
        "n_reviews": len(reviews),
        "n_flagged": out["n_flagged"],
        "flagged_ids": [ids[i] for i in out["flagged_indices"] if i < len(ids)],
        "per_review_probabilities": out["per_review"],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ANALYSIS PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

def summarize_trend(pred_mean: list) -> str:
    """
    Plain-English label for a GP trend curve: compare the mean of the first
    quarter of the prediction grid to the last quarter.

    >>> summarize_trend([4.5] * 20)
    'Consistently highly rated'
    >>> summarize_trend([4.0] * 10 + [3.0] * 10)
    'Declining over time'
    >>> summarize_trend([3.0, 3.1])
    'Not enough data'
    """
    if len(pred_mean) < 4:
        return "Not enough data"
    q = len(pred_mean) // 4
    first_quarter = sum(pred_mean[:q]) / q
    last_quarter = sum(pred_mean[-q:]) / q
    diff = last_quarter - first_quarter
    recent_mean = pred_mean[-1]
    if abs(diff) < 0.3:
        if recent_mean >= 4.0:
            return "Consistently highly rated"
        if recent_mean >= 3.0:
            return "Stable, middle-of-the-road ratings"
        return "Consistently low rated"
    if diff > 0.5:
        return "Significantly improving over time"
    if diff > 0.3:
        return "Trending upward recently"
    if diff < -0.5:
        return "Declining over time"
    return "Trending downward recently"


def analyze_professor(
    prof: dict,
    bb_model,
    nb_model,
    gp_model,
    priors: Optional[dict] = None,
    grade_inflation_beta: float = 0.0,
    now: Optional[datetime] = None,
) -> dict:
    """Run all three Bayesian models on a single professor.

    `now` anchors the recency weighting and the highlight recency bonus. The
    pipeline passes the scrape timestamp so re-running on the same input gives
    byte-identical output; it defaults to the wall clock for ad-hoc calls.
    """
    if now is None:
        now = datetime.now()
    reviews = prof.get("reviews", [])
    # The scraper's search index does not return tag totals; count them from
    # the reviews themselves so per-tag posteriors have data.
    top_tags = prof.get("top_tags") or derive_top_tags(reviews)

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

    # --- Gaussian Process ---
    gp_trend = gp_model.fit_professor_trend(reviews)

    # --- Grade Distribution (letter grades only) ---
    grade_counts = Counter()
    for r in reviews:
        grade = letter_grade(r.get("grade"))
        if grade:
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
    # Build highlights — and filter out reviews the outlier detector flagged,
    # so we never surface a likely troll as "what students say".
    review_quality = _review_quality_block(reviews)
    _flagged_ids_set = set((review_quality or {}).get("flagged_ids", []))
    scored_reviews = []
    for r in reviews:
        comment = (r.get("comment") or "").strip()
        if not comment or len(comment) < 30:
            continue
        if r.get("id") in _flagged_ids_set:
            continue
        # Score: upvotes + length bonus + recency bonus
        score = ((r.get("thumbs_up") or 0) - (r.get("thumbs_down") or 0))
        score += min(len(comment) / 200, 2.0)  # length bonus, capped
        try:
            dt = datetime.strptime((r.get("date") or "")[:10], "%Y-%m-%d")
            years_ago = (now - dt).days / 365
            score += max(0, 3 - years_ago)  # recency bonus
        except (ValueError, TypeError):
            pass
        scored_reviews.append({
            "id": r.get("id"),
            "comment": comment[:500],  # cap length
            "class_name": r.get("class_name") or "",
            "grade": letter_grade(r.get("grade")) or "",
            "date": (r.get("date") or "")[:10],
            "clarity": r.get("clarity_rating"),
            "helpful": r.get("helpful_rating"),
            "difficulty": r.get("difficulty_rating"),
            "score": score,
        })
    # Stable order: score desc, then id, so identical input gives identical output.
    scored_reviews.sort(key=lambda x: (-x["score"], str(x["id"])))
    review_highlights = scored_reviews[:5]

    # --- Trend Summary (plain English from GP) ---
    trend_summary = (
        "Not enough data" if gp_trend.get("insufficient_data")
        else summarize_trend(gp_trend.get("pred_mean", []))
    )

    # --- Calibrated (empirical-Bayes) posteriors; the headline numbers use
    # these when priors are available, else the fixed Beta(2,2) posterior.
    calibrated = _calibrated_block(prof, priors) if priors is not None else None
    quality_adjusted = grade_adjusted_quality(prof, grade_inflation_beta)

    # --- Confidence Level (plain English from Beta-Binomial) ---
    n = len(overall_ratings)
    good_post = calibrated["good_rating"] if calibrated else rating_posterior.get("good", {})
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
        cls = (r.get("class_name") or "").strip()
        if not cls:
            continue
        class_data[cls]["count"] += 1
        scores = [s for s in [r.get("clarity_rating"), r.get("helpful_rating")] if s]
        if scores:
            class_data[cls]["ratings"].append(sum(scores) / len(scores))
        g = letter_grade(r.get("grade"))
        if g:
            class_data[cls]["grades"].append(g)

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
        # Calibrated layer (empirical-Bayes priors + decision-theoretic summaries)
        # Stable v1 shape so the frontend can rely on subfields; absent when
        # priors aren't passed in (e.g. callers using the pre-calibration path).
        "calibrated_analysis": calibrated,
        "tag_posteriors": _tag_posteriors({**prof, "top_tags": top_tags, "num_ratings": len(reviews)}),
        # Essentials layer (personal grade forecast baseline, recency read,
        # outlier flags). Purely additive — frontend falls back when absent.
        "grade_forecast": _grade_forecast_block(grade_probabilities, grade_total),
        "recency": _recency_block(prof, priors, now=now) if priors is not None else None,
        "review_quality": review_quality,
        # Honest-signals layer: grade-inflation-adjusted quality (separates
        # teaching from grade generosity) + concrete teaching-style attributes
        # extracted from review text (slides online, attendance, exam format).
        "quality_adjusted": (quality_adjusted.as_dict() if quality_adjusted is not None else None),
        "attributes": [s.as_dict() for s in extract_teaching_attributes(reviews)],
        "category_sentiment": category_sentiment,
        "gp_trend": gp_trend,
        "grade_distribution": dict(grade_counts.most_common()),
        "top_tags": top_tags,
    }


DEFAULT_NB_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "nb_topic_model.json")


def run_pipeline(input_path: str, output_path: str, nb_model_path: str = DEFAULT_NB_MODEL_PATH):
    """Run the full Bayesian analysis pipeline."""
    print(f"Loading data from {input_path}...")
    data = load_json(input_path)

    professors = data.get("professors", [])
    print(f"Found {len(professors)} professors.")

    # Initialize models
    bb_model = BetaBinomialModel(prior_alpha=2.0, prior_beta=2.0)
    gp_model = GaussianProcessRegression(
        length_scale=6.0,       # starting point; per-professor selection in fit_professor_trend
        signal_variance=1.0,
        noise_variance=0.8,     # ratings are noisy
    )

    # Topic classifier: the supervised model trained by train_classifier.py on
    # tag-weak-labeled reviews (cross-school accuracy in metrics/latest.md).
    # Falls back to the keyword-seed model if the artifact is missing.
    if os.path.exists(nb_model_path):
        nb_model = NaiveBayesClassifier.load(nb_model_path)
        print(f"Loaded topic classifier from {nb_model_path} "
              f"({nb_model.n_training_docs} training reviews, {len(nb_model.vocab)} vocab)")
    else:
        nb_model = NaiveBayesClassifier(smoothing=1.0)
        print(f"WARNING: {nb_model_path} not found; using keyword-seed classifier. "
              f"Run train_classifier.py to build it.")

    # Fit empirical-Bayes priors across the whole school (and per department).
    # This is the Lecture-2-p.3 pseudocount framing operationalized: the
    # strength of pooling is inferred from the between-professor variance
    # rather than being hand-picked.
    print("Fitting empirical-Bayes priors...")
    priors = build_calibration_priors(professors)
    school_good = priors["school"]["good_rating"]
    school_wta = priors["school"]["take_again"]
    print(f"  school good-rating prior: Beta({school_good.alpha:.2f}, {school_good.beta:.2f}) [{school_good.source}]")
    print(f"  school take-again prior:  Beta({school_wta.alpha:.2f}, {school_wta.beta:.2f}) [{school_wta.source}]")
    print(f"  per-department priors fit: {len(priors['department'])} departments")

    # Fit the school-wide grade-inflation slope β. Pooled fixed-effects OLS on
    # (rating, grade) pairs across every professor; captures how much of a
    # student's rating is explained by the grade they received rather than the
    # prof's teaching. Reused across every prof in this school.
    print("Fitting school-wide grade-inflation slope...")
    grade_inflation_beta = fit_grade_inflation_beta(professors)
    print(f"  β = {grade_inflation_beta:+.3f}  "
          f"(students who got one GP higher rated this prof {grade_inflation_beta:+.2f} points higher on avg)")

    # Anchor "now" to the scrape time so output is deterministic per input.
    now = None
    scraped_at = (data.get("metadata") or {}).get("scraped_at")
    if scraped_at:
        try:
            now = datetime.fromisoformat(scraped_at.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            now = None
    if now is None:
        now = datetime.now()

    # Analyze each professor
    print("Running Bayesian analysis...")
    results = []
    for i, prof in enumerate(professors):
        name = f"{prof['first_name']} {prof['last_name']}"
        print(f"  [{i+1}/{len(professors)}] {name}...")
        analysis = analyze_professor(
            prof, bb_model, nb_model, gp_model,
            priors=priors,
            grade_inflation_beta=grade_inflation_beta,
            now=now,
        )
        results.append(analysis)

    output = {
        "metadata": data.get("metadata", {}),
        "analysis": results,
        "calibration": {
            "school_priors": {
                "good_rating": school_good.as_dict(),
                "take_again": school_wta.as_dict(),
            },
            "n_departments": len(priors["department"]),
            "grade_inflation_beta": round(grade_inflation_beta, 4),
        },
    }
    output["metadata"]["analyzed_at"] = datetime.now(timezone.utc).isoformat()

    # Gzipped when the path ends in .gz (the deploy format); plain otherwise.
    dump_json(output, output_path, indent=None if output_path.endswith(".gz") else 2)

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
    parser.add_argument("--nb-model", type=str, default=DEFAULT_NB_MODEL_PATH,
                        help="Path to the trained topic-classifier JSON (see train_classifier.py)")
    args = parser.parse_args()
    run_pipeline(args.input, args.output, nb_model_path=args.nb_model)


if __name__ == "__main__":
    main()
