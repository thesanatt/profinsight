# 04 — Implementation Plan

Scope: ship G1–G6 + rename sweep from `03_GAP_ANALYSIS.md` as a single "Bayesian Calibration Pass." Keep the pure-Python constraint (no sklearn/scipy).

## Code architecture

New module: `bayesian_calibration.py` (pure Python). Houses the new primitives. Imported by `bayesian_pipeline.py` (which already exports Beta-Binomial machinery). The pipeline continues to be the single analyzed-JSON producer, so the API + frontend read it without changes to the data-loading layer.

```
bayesian_pipeline.py  (existing)
  ├─ uses → bayesian_calibration.py  (new)
  │         ├─ EmpiricalBayesBeta       (G1, G4)  — fit α,β by method-of-moments from a set of (x,n) pairs
  │         ├─ credible_interval(...)    (G2)     — equal-tailed CI from a Beta posterior (exact via regularized incomplete Beta)
  │         ├─ prob_a_greater_b(...)    (G3)     — P(θ_A > θ_B) via analytic-approx or MC
  │         ├─ loss_summary(...)         (G5)     — mean / median / mode / asymmetric-loss point estimate
  │         └─ posterior_predictive_match (G6)  — fit-quiz moderation
  └─ emits → data/{school}_analyzed.json
              additional fields per professor:
                - quality_posterior:   {alpha, beta, mean, ci_low, ci_high, shrunk_toward_dept_mean: bool}
                - take_again_posterior: {...}
                - tags: [{name, count, n, posterior: {mean, ci_low, ci_high}}]
                - display: {conservative, expected, optimistic}
                - dept_prior: {alpha, beta, source: "empirical_bayes_mom"}
                - school_prior: {alpha, beta}
```

New API endpoints:
- `GET /api/{school}/compare?a=<prof_id>&b=<prof_id>` — returns `P(A > B)` on overall, take-again, and per-matched-tag dimensions.
- `POST /api/{school}/fit` — returns posterior-predictive match scores with CIs.

Frontend:
- `ProfessorDetail.jsx`: swap scalar stats → `<StatWithCI />`; add display-mode toggle.
- `CompareMode.jsx`: show `P(A > B)` banner + overlap-of-CI visual.
- `FitQuiz.jsx`: pass fit scores through the posterior-predictive moderation; show CI on the match %.
- Rename "confidence" → "credible" anywhere the bands are Bayesian.

Tests: `tests/` (new). `pytest` over pure-math functions; doesn't require FastAPI/React.

## Order of work

1. [DONE] Deploy script.
2. Read `bayesian_pipeline.py` end-to-end to know the exact seams.
3. Create `bayesian_calibration.py` with the five primitives. Unit tests inline via doctest + a `tests/test_calibration.py`.
4. Wire into `bayesian_pipeline.py`. Make sure analyzed JSON stays backward compatible — new fields only, no removals.
5. Re-run pipeline over `data/*.json` to regenerate analyzed JSON.
6. Extend `api.py` with `/compare` and update `/fit`. Keep old endpoints working.
7. Frontend changes (component at a time, verified in the browser).
8. Rename sweep: "confidence" → "credible" in the frontend strings where the underlying math is Bayesian.
9. Ship docs updates (README mention of the calibration pass, but keep the marketing tone).
10. Smoke test end-to-end via `./deploy.sh dev`.

## Backward-compatibility commitments

- Every existing JSON field keeps its name and meaning.
- Every existing API endpoint keeps its contract. New info is added.
- `bayesian_pipeline.py` CLI flags unchanged; any new flag is optional with a sane default.

## Risk list

- **Math bugs.** Mitigation: doctests + property tests (e.g. "posterior mean is between prior mean and MLE").
- **Performance.** Empirical-Bayes moment-matching is O(n_professors); negligible.
- **Frontend regressions.** Mitigation: run the existing pages first, then incrementally replace cards.
- **No way to run current pipeline until we know it.** Mitigation: skim the pipeline first, don't change call signatures until after the primitive is tested standalone.
