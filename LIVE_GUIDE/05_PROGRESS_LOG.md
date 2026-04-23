# Progress Log (append-only)

Format: `[YYYY-MM-DD HH:MM local] — what happened`.

## 2026-04-23
- Session start. Initialized LIVE_GUIDE.
- Top-level survey: api.py (680), bayesian_pipeline.py (917), bulk_update.py (237), deep_scrape.py (356), rmp_scraper.py (498). Frontend components: CompareMode, FitQuiz, Landing, ProfessorDetail, ProfessorList, ScheduleHelper, SemesterOptimizer. 24 class PDFs + 1 notebook (Lecture 18).
- Dispatched parallel agents: (a) Explore — audit current Bayesian pipeline + API + frontend; (b) general-purpose — read all class PDFs and extract ranked concept inventory.
- Wrote deploy.sh (setup/analyze/build/dev/serve/scrape/refresh/status/deploy). Sanity check passes.
- Agents returned: 01_CURRENT_STATE.md (916 lines, grounded) and 02_CLASS_CONCEPTS.md (213 lines, tiered).
- Wrote 03_GAP_ANALYSIS.md (9 gaps, ranked) and 04_PLAN.md (G1–G6 + rename sweep as v1).
- Built bayesian_calibration.py (427 lines, pure Python): regularized incomplete Beta, exact credible intervals, empirical-Bayes method-of-moments, Monte Carlo + closed-form P(A>B), decision-theoretic summary, posterior-predictive match scoring.
- Tests: 42 doctests + 20 pytest property tests, all green.
- Extended bayesian_pipeline.py: exact CIs (replaced normal approx in place), `build_calibration_priors` for school + per-department empirical-Bayes priors, `_calibrated_block` and `_tag_posteriors` per professor. Backward compatible — `bayesian_analysis` block unchanged.
- Regenerated all 29 schools' analyzed JSON (3 parallel batches). Every file now has a `calibration` root block and a `calibrated_analysis` + `tag_posteriors` block per professor.
- Extended api.py: new `/api/{school}/head_to_head` endpoint; `/api/{school}/fit` upgraded to posterior-predictive moderation with a `match_posterior` credible band in every result.
- Frontend: ProfessorDetail now has a `CalibratedCard` (Conservative/Expected/Optimistic toggle driven by Beta quantiles) and a `CalibratedTags` card (credible bands per tag). CompareMode now fetches `/head_to_head` for two-prof pairs and shows P(A > B) with verdict. FitQuiz shows the 95% credible band next to each match. Label "confidence interval" → "95% credible" wherever the math is Bayesian.
- Vite build clean (837 modules). End-to-end smoke test: GET /schools (29), GET /professors (shape stable), GET /head_to_head (sensible P(A>B) + verdict), GET /fit (match_posterior populated).
- Tasks 1–8 complete.
