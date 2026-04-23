# 03 — Gap Analysis: What the class teaches vs. what the product does

Every row is a concept from `02_CLASS_CONCEPTS.md` × a gap in `01_CURRENT_STATE.md`. Sorted by impact-per-hour.

| # | Concept (class cite) | What the product does today | Gap / opportunity | Impact | Effort |
|---|----------------------|------------------------------|-------------------|--------|--------|
| G1 | Hierarchical / empirical-Bayes shrinkage (L2 p.3) | Fixed `Beta(2, 2)` prior for every professor (`bayesian_pipeline.py:48-56`). No pooling by department or school. | A prof with 2 five-star reviews can top the list. Fit `(α, β)` from the department's aggregate would-take-again and overall-rating-is-good rates; every professor's posterior then shrinks toward its peers automatically. | **Huge** — fixes the flagship "tiny-n artifact" bug | Low. Pure Python. One new class + one call per professor. |
| G2 | Credible-interval reporting, with correct naming (L3 p.4–5) | CI is computed per the audit but exposed only inside the collapsed "Bayesian details" drawer. Point estimates dominate the UI. | Put `±` credible bands next to every headline stat on `ProfessorDetail`; use overlap-of-bands visualization in `CompareMode`; label them "credible interval" everywhere (L3 p.5 Morey et al. is emphatic). | **High** — directly communicates confidence | Low (pipeline already has the bands; it's mostly wiring + one rename sweep). |
| G3 | Posterior hypothesis testing: `P(θ_A > θ_B)` (L3 p.1–2; L4 p.5) | `CompareMode` shows raw averages side-by-side. | Compute Monte-Carlo `P(Prof A > Prof B)` from their Beta posteriors and display as the headline statement. Far more intuitive than two numbers. | **Huge** — reframes the whole compare UX | Low. Few lines of code + one Monte Carlo loop. |
| G4 | Per-tag Beta-Binomial (L2 p.2–4) | `top_tags` is a raw count list. "Tough grader (3)" vs "Tough grader (3) out of 200 reviews" are displayed identically. | Each tag gets its own Beta posterior: `Beta(α + tag_count, β + n_reviews − tag_count)` with `(α, β)` learned from the school's tag base-rate. Each tag then has a posterior mean + CI. | **High** — unlocks honest tag comparison | Low. Same pattern as the existing pipeline. |
| G5 | Bayesian decision theory / loss-function choice (L4 p.1–4) | Default display = posterior mean. No alternative. | Offer a "display mode" — `Conservative` (lower 25% credible bound), `Expected` (mean), `Optimistic` (upper 25% credible bound). Default `Conservative` for would-take-again since over-claiming hurts students more than under-claiming. | **Medium** — principled differentiation | Low. Just alternative summaries of the same posterior. |
| G6 | Posterior predictive + moderation for FitQuiz (L8 p.3–4) | `FitQuiz` score likely hard-weights quiz answers against prof features. Thin-n profs get confidently-wrong match scores. | Use a Bayesian-logistic / posterior-predictive match score. Profs with few reviews naturally regress toward 50%. Concretely: a 1–5 rating-agreement match runs through the Beta posterior before being combined with other factors. | **High** — the quiz is a core feature | Medium. Needs refactor of the fit-scoring logic. |
| G7 | Bayesian linear regression on features (L6 + L7) | No such model. | "What drives this prof's rating" card: fit BLR `rating ~ tag_counts + difficulty + department_dummy + log_n_reviews`, display posterior-weighted tag contributions with CIs. Use ridge-as-MAP then Laplace for CIs (L8 p.1–2). | **Medium** — an "insight" surface | Medium. ~100 lines, needs matrix ops in pure Python. |
| G8 | ARD kernel for "what matters at this school" (L14 p.3–4) | No per-school explainability. | Fit per-school ARD-RBF GP on (rating → features). Long length-scales → irrelevant features. Output as an insight card. | **Low-Medium** — niche wow-factor | Higher (needs GP with learned length-scales — heavy in pure Python). |
| G9 | Expectation Propagation for bounded scores ([Bonus] EP p.1–2) | N/A | Only matters once we have a bounded-latent-score quantity that Laplace handles poorly. Defer. | **Low** | Higher (EP iterations). |

## What I'll build in v1

Ship **G1–G6** and the rename sweep. This is the set where the math is within the class's coverage, the payoff is user-visible, and every step can be added in pure-Python without new dependencies (keeping the existing "no sklearn / scipy" constraint from README p.56).

G7 is a stretch goal. G8, G9 are explicit future work.

## Things I am NOT inventing

- No hierarchical *parametric* Bayes with hyperpriors — the class doesn't teach it by name. I use empirical-Bayes (method-of-moments) for the `(α, β)` at department/school level, which is a faithful operationalization of the L2 p.3 pseudocount framing.
- No MCMC. Class covers it only briefly in L23; our posteriors are conjugate so we don't need it.
- No LDA / mixture models. Class doesn't cover them. The existing Naive-Bayes topic classifier stays.
- No VI by name. Class uses EP/ADF/Laplace as the approximation family; we stay in that family when needed.

## Naming the feature set

I'll refer to the bundled v1 as **"Bayesian Calibration Pass"**: every user-facing number becomes a properly-shrunk posterior with honest credible bounds, and the compare / fit / display surfaces switch to posterior-native operations.
