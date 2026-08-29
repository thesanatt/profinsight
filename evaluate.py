"""
ProfInsight evaluation harness.

Every number in README.md and METRICS.md comes from this script. Run it after
any model change:

    python evaluate.py                    # full run, ~1-2 minutes on 65 schools, writes metrics/latest.json + .md
    python evaluate.py --quick            # 6 schools, ~20s
    python evaluate.py --skip-gp          # skip the O(n^3) GP hold-out
    python evaluate.py --gp-max-profs 0   # no GP sampling cap

What it measures (all pure Python, no numpy/scipy):

1. Dataset scale: schools, professors, reviews, words, departments, courses, dates.
2. Shrinkage hold-out. For each professor with >= 4 usable reviews, sort by date,
   train on the first half, test on the second half. Compare the predicted
   success probability against held-out outcomes for: raw mean, school pooled
   mean, fixed Beta(2,2), empirical Bayes by naive method of moments (the old
   estimator), empirical Bayes by type-II maximum likelihood (shipped), and the
   recency-weighted posterior. Metrics: log-loss, Brier score, per-professor
   MAE, stratified by training-set size. Coverage of 80/90/95% Beta-Binomial
   posterior-predictive intervals on the held-out success count.
3. GP trend hold-out. For professors with >= 8 dated reviews, fit on the first
   70% and predict the mean rating of the last 30%. Compare the shipped GP
   (centered, length-scale by marginal likelihood) with the old zero-mean GP,
   a fixed-scale centered GP, the training mean and the last-5 mean.
4. Topic classifier. Reviews whose RMP tags map to exactly one topic are weak
   labels. Schools are split alternately by slug; the classifier trains on one
   half and is scored on the other. Variants: keyword seeds, seeds plus the old
   self-training step, supervised NB with empirical priors (shipped), supervised
   NB with uniform priors.
5. Grade-inflation slope stability: beta fit on odd vs even professors.

Protocol note: department priors in the harness are fit on the training halves
of professors with >= 4 usable reviews (>= 10 such professors per department);
the pipeline fits them on every professor in the department. The harness is
therefore slightly conservative about how much pooling is available.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from bayesian_advanced import recency_weighted_counts  # noqa: E402
from bayesian_calibration import (  # noqa: E402
    BetaPrior,
    _log_beta,
    fit_empirical_bayes_beta,
)
from bayesian_honest import fit_grade_inflation_beta  # noqa: E402
from bayesian_pipeline import GaussianProcessRegression, NaiveBayesClassifier, letter_grade, summarize_trend  # noqa: E402
from train_classifier import raw_school_files, weak_label  # noqa: E402

DATA_DIR = os.path.join(ROOT, "data")
METRICS_DIR = os.path.join(ROOT, "metrics")
EPS = 1e-3
KAPPA_SWEEP = (1, 2, 4, 8, 16, 32)
QUICK_SCHOOLS = ["umich", "berkeley", "mit", "nyu", "purdue", "uga"]
CATS = ["grading", "lectures", "workload", "approachability", "exams"]


# ───────────────────────────── helpers ─────────────────────────────

def parse_date(s: str | None) -> datetime | None:
    s = s or ""
    for fmt, width in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d", 10)):
        try:
            return datetime.strptime(s[:width], fmt)
        except ValueError:
            continue
    return None


def outcome_take_again(r: dict) -> int | None:
    v = r.get("would_take_again")
    return 1 if v == 1 else (0 if v == 0 else None)


def outcome_good(r: dict) -> int | None:
    c, h = r.get("clarity_rating"), r.get("helpful_rating")
    if c is None or h is None:
        return None
    return 1 if (c + h) / 2 >= 3.5 else 0


def rating_of(r: dict) -> float | None:
    c, h = r.get("clarity_rating"), r.get("helpful_rating")
    if c is None or h is None:
        return None
    return (c + h) / 2


def bb_pmf(k: int, m: int, a: float, b: float) -> float:
    return math.exp(math.lgamma(m + 1) - math.lgamma(k + 1) - math.lgamma(m - k + 1)
                    + _log_beta(k + a, m - k + b) - _log_beta(a, b))


def bb_interval(m: int, a: float, b: float, level: float) -> tuple[int, int]:
    tail = (1 - level) / 2
    cum, lo, hi = 0.0, None, m
    for k in range(m + 1):
        cum += bb_pmf(k, m, a, b)
        if lo is None and cum > tail:
            lo = k
        if cum >= 1 - tail:
            hi = k
            break
    return (lo if lo is not None else 0), hi


def load_schools(files: list[str]) -> dict[str, dict]:
    out = {}
    for f in files:
        slug = os.path.basename(f).replace(".json", "")
        with open(f) as fh:
            out[slug] = json.load(fh)
    return out


# ───────────────────────────── 1. dataset ─────────────────────────────

def dataset_stats(schools: dict[str, dict]) -> dict:
    n_profs = n_reviews = n_comments = n_words = n_tagged = n_graded = 0
    depts, courses = set(), set()
    dates = []
    per_school = {}
    reviews_per_prof = []
    for slug, d in schools.items():
        profs = d.get("professors", [])
        sr = 0
        for p in profs:
            depts.add((slug, (p.get("department") or "Unknown").strip()))
            rs = p.get("reviews", [])
            reviews_per_prof.append(len(rs))
            for r in rs:
                sr += 1
                c = (r.get("comment") or "").strip()
                if c:
                    n_comments += 1
                    n_words += len(c.split())
                if (r.get("rating_tags") or "").strip():
                    n_tagged += 1
                if letter_grade(r.get("grade")):
                    n_graded += 1
                if r.get("class_name"):
                    courses.add((slug, r["class_name"].strip().upper()))
                dt = parse_date(r.get("date"))
                if dt:
                    dates.append(dt)
        n_profs += len(profs)
        n_reviews += sr
        per_school[slug] = {"name": d.get("metadata", {}).get("school_name"), "professors": len(profs), "reviews": sr}
    dates.sort()
    return {
        "schools": len(schools),
        "professors": n_profs,
        "reviews": n_reviews,
        "reviews_with_comment": n_comments,
        "review_words": n_words,
        "reviews_with_tags": n_tagged,
        "reviews_with_grade": n_graded,
        "departments": len(depts),
        "courses": len(courses),
        "median_reviews_per_professor": statistics.median(reviews_per_prof) if reviews_per_prof else None,
        "earliest_review": dates[0].date().isoformat() if dates else None,
        "latest_review": dates[-1].date().isoformat() if dates else None,
        "reviews_since_2024": sum(1 for d in dates if d.year >= 2024),
        "per_school": per_school,
    }


# ───────────────────────────── 2. shrinkage ─────────────────────────────

def shrinkage_holdout(schools: dict[str, dict], outcome_fn, label: str) -> dict:
    t0 = time.time()
    metrics = defaultdict(lambda: defaultdict(float))
    counts = defaultdict(lambda: defaultdict(int))
    coverage = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    clamped = {"eb_mom": [0, 0], "eb_ml": [0, 0]}
    n_profs = n_test = 0
    levels = (0.80, 0.90, 0.95)

    for slug, d in schools.items():
        recs = []
        for p in d.get("professors", []):
            rows = []
            for r in p.get("reviews", []):
                y = outcome_fn(r)
                dt = parse_date(r.get("date"))
                if y is None or dt is None:
                    continue
                rows.append((dt, y, r))
            if len(rows) < 4:
                continue
            rows.sort(key=lambda t: t[0])
            h = len(rows) // 2
            train, test = rows[:h], rows[h:]
            split_date = train[-1][0]
            stamped = [{"date": r.get("date", ""), "y": y} for _, y, r in train]
            rs, rt = recency_weighted_counts(stamped, "y", now=split_date,
                                             success_values={1}, non_success_values={0})
            recs.append({
                "dept": (p.get("department") or "Unknown").strip() or "Unknown",
                "x": sum(y for _, y, _ in train), "n": len(train),
                "kt": sum(y for _, y, _ in test), "m": len(test),
                "rs": rs, "rt": rt,
            })
        if len(recs) < 3:
            continue
        n_profs += len(recs)
        n_test += sum(r["m"] for r in recs)

        school_pairs = [(r["x"], r["n"]) for r in recs]
        pooled = sum(x for x, _ in school_pairs) / sum(n for _, n in school_pairs)
        school_fit = {
            "eb_mom": fit_empirical_bayes_beta(school_pairs, method="mom"),
            "eb_ml": fit_empirical_bayes_beta(school_pairs, method="ml"),
        }
        by_dept = defaultdict(list)
        for r in recs:
            by_dept[r["dept"]].append((r["x"], r["n"]))
        dept_fit = {}
        for dept, pairs in by_dept.items():
            if len(pairs) < 10:
                continue
            dept_fit[dept] = {
                "eb_mom": fit_empirical_bayes_beta(pairs, method="mom"),
                "eb_ml": fit_empirical_bayes_beta(pairs, method="ml"),
            }
            for k in clamped:
                clamped[k][1] += 1
                if abs(dept_fit[dept][k].concentration - 2.0) < 1e-9:
                    clamped[k][0] += 1

        for r in recs:
            x, n, kt, m = r["x"], r["n"], r["kt"], r["m"]
            fit = dept_fit.get(r["dept"], school_fit)
            preds = {"raw_mle": x / n, "school_mean": pooled, "fixed_beta22": (2 + x) / (4 + n)}
            posts = {"fixed_beta22": (2.0 + x, 2.0 + n - x)}
            for k in ("eb_mom", "eb_ml"):
                pr = fit[k]
                posts[k] = (pr.alpha + x, pr.beta + n - x)
                preds[k] = posts[k][0] / (posts[k][0] + posts[k][1])
            pr = fit["eb_ml"]
            preds["eb_ml_recency"] = (pr.alpha + r["rs"]) / (pr.alpha + pr.beta + r["rt"]) if r["rt"] > 0 else pr.mean
            posts["eb_ml_recency"] = (pr.alpha + r["rs"], pr.beta + max(0.0, r["rt"] - r["rs"]))
            # Prior-strength sweep: keep the EB mean, vary concentration.
            for kappa in KAPPA_SWEEP:
                a0, b0 = kappa * pr.mean, kappa * (1 - pr.mean)
                preds[f"kappa_{kappa}"] = (a0 + x) / (kappa + n)
            bucket = "2-4" if n <= 4 else "5-9" if n <= 9 else "10-29" if n <= 29 else "30+"
            for est, p in preds.items():
                pc = min(max(p, EPS), 1 - EPS)
                ll = -(kt * math.log(pc) + (m - kt) * math.log(1 - pc))
                br = kt * (1 - p) ** 2 + (m - kt) * p ** 2
                for b_ in ("all", bucket):
                    metrics[est][("ll", b_)] += ll
                    metrics[est][("brier", b_)] += br
                    metrics[est][("mae", b_)] += abs(p - kt / m)
                    counts[est][("reviews", b_)] += m
                    counts[est][("profs", b_)] += 1
            for est, (a, b) in posts.items():
                for lv in levels:
                    lo, hi = bb_interval(m, a, b, lv)
                    coverage[est][lv][0] += 1 if lo <= kt <= hi else 0
                    coverage[est][lv][1] += 1

    out = {"outcome": label, "professors": n_profs, "held_out_reviews": n_test,
           "seconds": round(time.time() - t0, 1), "by_bucket": {}, "coverage": {},
           "dept_priors_at_floor": {k: {"clamped": v[0], "total": v[1],
                                        "pct": round(100 * v[0] / v[1], 1) if v[1] else None}
                                    for k, v in clamped.items()}}
    ests = ["raw_mle", "school_mean", "fixed_beta22", "eb_mom", "eb_ml", "eb_ml_recency"] + [f"kappa_{k}" for k in KAPPA_SWEEP]
    for b_ in ("all", "2-4", "5-9", "10-29", "30+"):
        rows = {}
        for est in ests:
            nr = counts[est][("reviews", b_)]
            npf = counts[est][("profs", b_)]
            if not nr:
                continue
            rows[est] = {"logloss": round(metrics[est][("ll", b_)] / nr, 4),
                         "brier": round(metrics[est][("brier", b_)] / nr, 4),
                         "prof_mae": round(metrics[est][("mae", b_)] / npf, 4)}
        out["by_bucket"][b_] = {"professors": counts["raw_mle"][("profs", b_)],
                                "reviews": counts["raw_mle"][("reviews", b_)], "estimators": rows}
    for est, lv_map in coverage.items():
        out["coverage"][est] = {f"{int(lv * 100)}%": round(100 * hit / tot, 1)
                                for lv, (hit, tot) in lv_map.items() if tot}
    return out


# ───────────────────────────── 3. GP ─────────────────────────────

class _ZeroMeanGP(GaussianProcessRegression):
    """The pre-fix behaviour: no mean function, fixed 6-month length-scale."""

    def predict(self, x_train, y_train, x_test, counts=None):
        L = self._factor(x_train, counts)
        if L is None:
            mu = sum(y_train) / len(y_train)
            return {"mean": [mu] * len(x_test), "std": [1.0] * len(x_test)}
        alpha = self._solve_triangular_upper(L, self._solve_triangular_lower(L, y_train))
        K_star = self._rbf_kernel(x_test, x_train)
        n = len(x_train)
        return {"mean": [sum(K_star[i][j] * alpha[j] for j in range(n)) for i in range(len(x_test))],
                "std": [1.0] * len(x_test)}


def gp_holdout(schools: dict[str, dict], max_profs: int) -> dict:
    t0 = time.time()
    err = defaultdict(float)
    sq = defaultdict(float)
    n = 0
    below_old = below_new = 0
    label_changed = 0
    label_pairs = Counter()
    ls_hist = Counter()
    old = _ZeroMeanGP(length_scale=6.0, signal_variance=1.0, noise_variance=0.8)
    fixed = GaussianProcessRegression(length_scale=6.0, signal_variance=1.0, noise_variance=0.8)
    shipped = GaussianProcessRegression(length_scale=6.0, signal_variance=1.0, noise_variance=0.8)

    candidates = []
    for slug, d in schools.items():
        for p in d.get("professors", []):
            rows = [(parse_date(r.get("date")), rating_of(r)) for r in p.get("reviews", [])]
            rows = [(dt, y) for dt, y in rows if dt is not None and y is not None]
            if len(rows) >= 8:
                candidates.append(rows)
    total_eligible = len(candidates)
    if max_profs and total_eligible > max_profs:
        step = total_eligible / max_profs
        candidates = [candidates[int(i * step)] for i in range(max_profs)]

    for rows in candidates:
        rows.sort(key=lambda t: t[0])
        k = int(len(rows) * 0.7)
        train, test = rows[:k], rows[k:]
        if len(test) < 2:
            continue
        t_first = train[0][0]
        raw_y = [y for _, y in train]
        # Same monthly binning the pipeline uses, so every GP variant sees
        # identical inputs and heavily reviewed professors stay tractable.
        xt, yt, ct, _ = GaussianProcessRegression.bin_by_month(train)
        x_test = [(dt - t_first).days / 30.44 for dt, _ in test]
        x_mid = sum(x_test) / len(x_test)
        y_true = sum(y for _, y in test) / len(test)
        grid = [min(xt) + i * (max(xt) - min(xt)) / 19 for i in range(20)]

        preds = {"train_mean": sum(raw_y) / len(raw_y), "last5_mean": sum(raw_y[-5:]) / len(raw_y[-5:])}
        preds["gp_old_zero_mean"] = min(5.0, max(1.0, old.predict(xt, yt, [x_mid], ct)["mean"][0]))
        old_curve = old.predict(xt, yt, grid, ct)["mean"]
        if min(old_curve) < 1.0:
            below_old += 1
        preds["gp_centered_fixed_ls"] = fixed.predict(xt, yt, [x_mid], ct)["mean"][0]
        ls, _ = shipped.select_length_scale(xt, yt, ct)
        ls_hist[ls] += 1
        shipped.length_scale = ls
        preds["gp_shipped"] = min(5.0, max(1.0, shipped.predict(xt, yt, [x_mid], ct)["mean"][0]))
        new_curve = shipped.predict(xt, yt, grid, ct)["mean"]
        if min(new_curve) < 1.0:
            below_new += 1
        shipped.length_scale = 6.0
        old_label = summarize_trend([min(5.0, max(1.0, m)) for m in old_curve])
        new_label = summarize_trend([min(5.0, max(1.0, m)) for m in new_curve])
        if old_label != new_label:
            label_changed += 1
            label_pairs[(old_label, new_label)] += 1
        for kname, v in preds.items():
            err[kname] += abs(v - y_true)
            sq[kname] += (v - y_true) ** 2
        n += 1

    return {
        "professors_eligible": total_eligible,
        "professors_evaluated": n,
        "seconds": round(time.time() - t0, 1),
        "curve_below_1_star_pct": {"old_zero_mean": round(100 * below_old / n, 1) if n else None,
                                   "shipped": round(100 * below_new / n, 1) if n else None},
        "next_period_error": {k: {"mae": round(err[k] / n, 4), "rmse": round(math.sqrt(sq[k] / n), 4)}
                              for k in err} if n else {},
        "chosen_length_scale_months": {str(k): v for k, v in sorted(ls_hist.items())},
        "trend_label_changed_pct": round(100 * label_changed / n, 1) if n else None,
        "trend_label_changes_top": [{"from": a, "to": b, "count": c} for (a, b), c in label_pairs.most_common(8)],
    }


# ───────────────────────────── 4. topic classifier ─────────────────────────────

def _self_train(model: NaiveBayesClassifier, reviews: list[dict]) -> None:
    """The removed self-training step, reproduced here only for the benchmark."""
    for review in reviews:
        comment = review.get("comment", "")
        if not comment:
            continue
        tokens = model._tokenize(comment)
        posteriors = model.classify(comment)
        top = max(posteriors, key=posteriors.get)
        if posteriors[top] > 0.35:
            for tok in tokens:
                model.category_word_counts[top][tok] += 1
                model.category_total_words[top] += 1
                model.vocab.add(tok)


def _score(pred: list[str], gold: list[str]) -> dict:
    acc = sum(1 for p, g in zip(pred, gold) if p == g) / len(gold)
    per_class = {}
    for c in CATS:
        tp = sum(1 for p, g in zip(pred, gold) if p == c and g == c)
        fp = sum(1 for p, g in zip(pred, gold) if p == c and g != c)
        fn = sum(1 for p, g in zip(pred, gold) if p != c and g == c)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        per_class[c] = {"precision": round(prec, 3), "recall": round(rec, 3),
                        "f1": round(2 * prec * rec / (prec + rec), 3) if prec + rec else 0.0}
    return {"accuracy": round(100 * acc, 1),
            "macro_f1": round(sum(v["f1"] for v in per_class.values()) / len(CATS), 3),
            "per_class": per_class}


def classifier_eval(schools: dict[str, dict]) -> dict:
    t0 = time.time()
    slugs = sorted(schools)
    train_slugs = slugs[0::2]
    test_slugs = slugs[1::2]
    gold, texts_test, test_reviews_by_school = [], [], {}
    for slug in test_slugs:
        rs = [r for p in schools[slug].get("professors", []) for r in p.get("reviews", [])]
        test_reviews_by_school[slug] = rs
        for r in rs:
            g = weak_label(r)
            if g is not None:
                gold.append(g)
                texts_test.append(r["comment"])
    if not gold:
        return {"error": "no weak labels in test schools"}
    majority = Counter(gold).most_common(1)[0]

    def top1(model, texts):
        return [max(model.classify(t).items(), key=lambda kv: kv[1])[0] for t in texts]

    results = {}
    seeds = NaiveBayesClassifier()
    results["keyword_seeds"] = _score(top1(seeds, texts_test), gold)

    # Old behaviour: seeds + per-school self-training, scored per school
    pred_st = []
    for slug in test_slugs:
        m = NaiveBayesClassifier()
        _self_train(m, test_reviews_by_school[slug])
        pred_st.extend(top1(m, [r["comment"] for r in test_reviews_by_school[slug] if weak_label(r) is not None]))
    results["seeds_plus_self_training_old"] = _score(pred_st, gold)

    texts_tr, labels_tr = [], []
    for slug in train_slugs:
        for p in schools[slug].get("professors", []):
            for r in p.get("reviews", []):
                g = weak_label(r)
                if g is not None:
                    texts_tr.append(r["comment"])
                    labels_tr.append(g)
    sup = NaiveBayesClassifier()
    sup.fit(texts_tr, labels_tr)
    results["supervised_empirical_prior_shipped"] = _score(top1(sup, texts_test), gold)
    sup_u = NaiveBayesClassifier()
    sup_u.fit(texts_tr, labels_tr, uniform_prior=True)
    results["supervised_uniform_prior"] = _score(top1(sup_u, texts_test), gold)

    return {
        "train_schools": train_slugs, "test_schools": test_slugs,
        "train_weak_labels": len(labels_tr), "test_weak_labels": len(gold),
        "test_label_distribution": dict(Counter(gold)),
        "majority_class": {"label": majority[0], "accuracy": round(100 * majority[1] / len(gold), 1)},
        "variants": results,
        "seconds": round(time.time() - t0, 1),
    }


# ───────────────────────────── 5. grade inflation ─────────────────────────────

def grade_inflation_stability(schools: dict[str, dict]) -> dict:
    per_school = {}
    for slug, d in schools.items():
        profs = d.get("professors", [])
        b_all = fit_grade_inflation_beta(profs)
        b_odd = fit_grade_inflation_beta(profs[0::2])
        b_even = fit_grade_inflation_beta(profs[1::2])
        per_school[slug] = {"beta": round(b_all, 4), "beta_odd_half": round(b_odd, 4), "beta_even_half": round(b_even, 4)}
    betas = [v["beta"] for v in per_school.values()]
    gaps = [abs(v["beta_odd_half"] - v["beta_even_half"]) for v in per_school.values()]
    return {
        "schools": len(per_school),
        "beta_median": round(statistics.median(betas), 4) if betas else None,
        "beta_min": round(min(betas), 4) if betas else None,
        "beta_max": round(max(betas), 4) if betas else None,
        "split_half_abs_gap_median": round(statistics.median(gaps), 4) if gaps else None,
        "per_school": per_school,
    }


# ───────────────────────────── report ─────────────────────────────

def _pct_drop(a: float, b: float) -> str:
    return f"{100 * (a - b) / a:.1f}%" if a else "n/a"


def to_markdown(m: dict) -> str:
    ds = m["dataset"]
    lines = [
        "# ProfInsight metrics",
        "",
        f"Generated {m['generated_at']} by `python evaluate.py` in {m['total_seconds']}s "
        f"(schools: {', '.join(m['schools_evaluated'])}).",
        "",
        "## Dataset",
        "",
        f"- {ds['schools']} schools, {ds['professors']:,} professors, {ds['reviews']:,} reviews "
        f"({ds['review_words']:,} words of review text)",
        f"- {ds['departments']:,} school-department pairs, {ds['courses']:,} distinct course codes",
        f"- {ds['reviews_with_tags']:,} reviews carry tags, {ds['reviews_with_grade']:,} report a grade",
        f"- Reviews span {ds['earliest_review']} to {ds['latest_review']}; {ds['reviews_since_2024']:,} since 2024",
        f"- Median reviews per professor: {ds['median_reviews_per_professor']}",
        "",
    ]
    for key in ("take_again", "good_rating"):
        s = m["shrinkage"][key]
        lines += [f"## Shrinkage hold-out: {key}", "",
                  f"{s['professors']:,} professors, {s['held_out_reviews']:,} held-out reviews "
                  f"(train = first half of each professor's reviews by date).", "",
                  "| training n | professors | estimator | log-loss | Brier | prof MAE |",
                  "|---|---|---|---|---|---|"]
        for b_, row in s["by_bucket"].items():
            for est, v in row["estimators"].items():
                lines.append(f"| {b_} | {row['professors']:,} | {est} | {v['logloss']} | {v['brier']} | {v['prof_mae']} |")
        allrow = s["by_bucket"]["all"]["estimators"]
        small = s["by_bucket"].get("2-4", {}).get("estimators", {})
        if "raw_mle" in allrow and "eb_ml" in allrow:
            lines += ["", f"Log-loss reduction, eb_ml vs raw_mle: {_pct_drop(allrow['raw_mle']['logloss'], allrow['eb_ml']['logloss'])} overall"
                      + (f", {_pct_drop(small['raw_mle']['logloss'], small['eb_ml']['logloss'])} for training n <= 4." if small else ".")]
        lines += ["", "Posterior-predictive interval coverage of the held-out success count:", ""]
        for est, cov in s["coverage"].items():
            lines.append(f"- {est}: " + ", ".join(f"{k} nominal -> {v}%" for k, v in cov.items()))
        sweep = {k: v for k, v in allrow.items() if k.startswith("kappa_")}
        if sweep:
            lines += ["", "Prior-strength sweep (EB mean fixed, concentration alpha+beta varied), log-loss all / n<=4: "
                      + ", ".join(f"{k.split('_')[1]}: {v['logloss']} / {small.get(k, {}).get('logloss', 'n/a')}" for k, v in sweep.items())]
        fl = s["dept_priors_at_floor"]
        lines += ["", f"Department priors at the concentration floor: eb_mom {fl['eb_mom']['pct']}%, eb_ml {fl['eb_ml']['pct']}% "
                  f"(of {fl['eb_ml']['total']} fits).", ""]
    if m.get("gp"):
        g = m["gp"]
        lines += ["## GP trend hold-out", "",
                  f"{g['professors_evaluated']:,} of {g['professors_eligible']:,} eligible professors (>= 8 dated reviews), "
                  "fit on first 70%, predict mean rating of the last 30%.", "",
                  "| predictor | MAE | RMSE |", "|---|---|---|"]
        for k, v in g["next_period_error"].items():
            lines.append(f"| {k} | {v['mae']} | {v['rmse']} |")
        lines += ["", f"Trend curves dipping below 1 star: old zero-mean GP {g['curve_below_1_star_pct']['old_zero_mean']}%, "
                  f"shipped {g['curve_below_1_star_pct']['shipped']}%.",
                  f"Length-scales chosen by marginal likelihood (months): {g['chosen_length_scale_months']}",
                  f"Trend label (first quarter vs last quarter of the curve) changes between the old and shipped GP: {g['trend_label_changed_pct']}% of professors. "
                  + "; ".join(f"{d['from']} -> {d['to']}: {d['count']}" for d in g["trend_label_changes_top"][:4]), ""]
    c = m["classifier"]
    if "variants" in c:
        lines += ["## Topic classifier (tag weak labels, cross-school)", "",
                  f"Train: {c['train_weak_labels']:,} weak labels from {len(c['train_schools'])} schools. "
                  f"Test: {c['test_weak_labels']:,} from {len(c['test_schools'])} other schools. "
                  f"Majority class {c['majority_class']['label']} = {c['majority_class']['accuracy']}%.", "",
                  "| variant | accuracy | macro-F1 |", "|---|---|---|"]
        for k, v in c["variants"].items():
            lines.append(f"| {k} | {v['accuracy']}% | {v['macro_f1']} |")
        lines.append("")
    gi = m["grade_inflation"]
    lines += ["## Grade-inflation slope", "",
              f"Median beta across {gi['schools']} schools: {gi['beta_median']} rating points per grade point "
              f"(min {gi['beta_min']}, max {gi['beta_max']}); median split-half gap {gi['split_half_abs_gap_median']}.", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default=DATA_DIR)
    ap.add_argument("--schools", default="", help="Comma-separated slugs (default: all)")
    ap.add_argument("--quick", action="store_true", help=f"Use {len(QUICK_SCHOOLS)} schools")
    ap.add_argument("--skip-gp", action="store_true")
    ap.add_argument("--gp-max-profs", type=int, default=3000,
                    help="Evenly sample this many professors for the GP hold-out (0 = all)")
    ap.add_argument("--output", default=os.path.join(METRICS_DIR, "latest"))
    args = ap.parse_args()

    files = raw_school_files(args.data_dir)
    keep = set(QUICK_SCHOOLS) if args.quick else {s.strip() for s in args.schools.split(",") if s.strip()}
    if keep:
        files = [f for f in files if os.path.basename(f).replace(".json", "") in keep]
    t0 = time.time()
    schools = load_schools(files)
    print(f"Loaded {len(schools)} schools in {time.time() - t0:.1f}s")

    m = {"generated_at": datetime.now().isoformat(timespec="seconds"), "schools_evaluated": sorted(schools)}
    m["dataset"] = dataset_stats(schools)
    print(f"Dataset: {m['dataset']['professors']:,} professors, {m['dataset']['reviews']:,} reviews")
    m["shrinkage"] = {
        "take_again": shrinkage_holdout(schools, outcome_take_again, "take_again"),
        "good_rating": shrinkage_holdout(schools, outcome_good, "good_rating"),
    }
    for k, v in m["shrinkage"].items():
        print(f"Shrinkage {k}: {v['professors']:,} profs, {v['held_out_reviews']:,} held-out reviews, {v['seconds']}s")
    if args.skip_gp:
        m["gp"] = None
        print("GP hold-out skipped")
    else:
        m["gp"] = gp_holdout(schools, args.gp_max_profs)
        print(f"GP: {m['gp']['professors_evaluated']:,}/{m['gp']['professors_eligible']:,} profs, {m['gp']['seconds']}s"
              + (f" (sampled; pass --gp-max-profs 0 for all)" if m['gp']['professors_evaluated'] < m['gp']['professors_eligible'] else ""))
    m["classifier"] = classifier_eval(schools)
    if "variants" in m["classifier"]:
        print(f"Classifier: {m['classifier']['test_weak_labels']:,} test labels, {m['classifier']['seconds']}s")
    m["grade_inflation"] = grade_inflation_stability(schools)
    m["total_seconds"] = round(time.time() - t0, 1)

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output + ".json", "w") as f:
        json.dump(m, f, indent=1)
    md = to_markdown(m)
    with open(args.output + ".md", "w") as f:
        f.write(md + "\n")
    print(md)
    print(f"\nWrote {args.output}.json and {args.output}.md in {m['total_seconds']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
