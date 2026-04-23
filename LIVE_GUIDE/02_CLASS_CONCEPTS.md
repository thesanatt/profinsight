# 02 — Class Concepts (Bayesian Methods) Applied to ProfInsight

Ranked inventory of concepts from EECS 498-009 lecture notes, evaluated for applicability to a Rate My Professor-style review analyzer. Data already in pipeline: 1–5 ratings, tag counts (e.g. "tough grader", "caring"), review text, difficulty scores, would-take-again %, department, school.

Citations reference the file name in `/Users/sanat/Projects/profinsight/class_content/` and the page (of the PDF).

---

## Tier S — concepts with obvious, high-impact applicability

### S1. Beta-Binomial conjugate model (posterior mean, credible intervals)
- **Citation**: Lecture 2 Notes.pdf pp. 2–4; Lecture 3 Notes.pdf pp. 1–2, 4 (credible intervals).
- **Summary**: For a binary quantity θ ∈ (0,1) with Binomial(n, θ) data, a Beta(α, β) prior yields a Beta(α+x, β+n−x) posterior. α and β act as "pseudocounts" — fake prior successes and failures. The posterior has a closed form mean (α+x)/(α+β+n) and variance that shrinks with n, so confidence tightens as data grows. You can compute P(θ ∈ interval) directly by integrating the posterior.
- **Product hypothesis**: On `ProfessorDetail`, replace the raw "X% would take again" with the posterior mean of a Beta(α, β) fitted from the department's overall take-again rate (or a global prior), and show the 95% credible interval in a small bar beneath the headline number. A prof with "100% (3 reviews)" will now appropriately shrink toward the department mean, while a prof with "72% (200 reviews)" stays close to 72%. Same treatment applies to any binary-ish tag ("tough grader", "caring") by modeling P(tag | prof) as Binomial.
- **Data available**: Yes — `wouldTakeAgainPercent` + `numRatings` gives x and n directly. Department average can be computed from the existing professor list.

### S2. Hierarchical / partial pooling prior (shrinkage toward department mean)
- **Citation**: Lecture 2 Notes.pdf p. 3 ("pseudocounts" interpretation of α, β); Lecture 10 Notes.pdf pp. 1–3 (model evidence + "Occam's razor" motivation); implied throughout Lectures 1–3 by the prior-selection discussion.
- **Summary**: The class doesn't teach hierarchical/multilevel models by name, but the α,β-as-pseudocounts framing in Lecture 2 is exactly empirical-Bayes partial pooling: fit α,β from all professors in a department, then each professor's posterior is a weighted average of their own data and the department prior. Professors with many reviews dominate their own posterior; professors with few reviews get shrunk toward the department mean. This is the formal cure for the "5.0 rating from 2 reviews" problem.
- **Product hypothesis**: In the professor comparison and ranking views, rank by *posterior mean* rather than raw average. A newly added professor with only 3 glowing reviews won't unfairly leapfrog a veteran with 150 mixed reviews. Surface the amount of shrinkage ("this professor's displayed rating is pulled 0.4 points toward the department mean because of small sample size") as a transparency feature.
- **Data available**: Yes — ratings + department + school are all in the pipeline. No new data needed.

### S3. Bayesian decision theory (loss-function-driven summaries)
- **Citation**: Lecture 4 Notes.pdf pp. 1–4 (posterior expected loss; Bayes estimator under squared / absolute / 0–1 loss → posterior mean / median / mode).
- **Summary**: When you need to report a single number to summarize a distribution, the "best" choice depends on your loss function. Squared loss → posterior mean. Absolute loss → median. 0–1 loss → mode. The class explicitly derives these. You can also design custom losses (e.g. asymmetric: over-stating a professor's rating is worse than under-stating it for a student looking to avoid bad classes).
- **Product hypothesis**: Give users a "display mode" toggle on `ProfessorCard` — Expected (mean), Typical (median), Most likely (mode) — and use asymmetric loss to bias the default displayed number conservatively (under-reporting quality is safer than over-reporting for a student deciding whether to take a class). Also drives the choice of which acquisition score to use in the "recommend me a prof" feature.
- **Data available**: Yes — anything downstream of the Beta-Binomial posterior above.

### S4. Credible intervals vs. confidence intervals
- **Citation**: Lecture 3 Notes.pdf pp. 4–5 (definitions, fundamental confidence fallacy, precision fallacy).
- **Summary**: A Bayesian α-credible interval is "there is probability α that θ is in this interval, given the data." A frequentist α-confidence interval is "if we repeated the experiment many times, α% of the intervals would contain θ" — a property of the procedure, not the single interval you're looking at. The lecture is emphatic about this distinction and cites Morey et al. (2015). For a consumer product, credible intervals are the right thing to show because users want "how sure are we about this professor" not "how sure is our procedure over hypothetical other datasets."
- **Product hypothesis**: Every headline stat on `ProfessorDetail` (overall rating, difficulty, would-take-again) gets a small "±" appended that is a 95% credible interval, computed from the posterior. In the comparison view, overlap of credible intervals is the right visual for "are these two professors actually different." Don't call it a confidence interval — the Morey paper cited in Lecture 3 p. 5 explicitly warns against that language.
- **Data available**: Yes.

### S5. Posterior predictive / Bayesian prediction under uncertainty
- **Citation**: Lecture 7 Notes.pdf p. 2 ("Making predictions"); Lecture 8 Notes.pdf pp. 3–4 ("moderation" effect).
- **Summary**: Instead of plugging a point estimate into a prediction, integrate over the full posterior of parameters: p(y* | D) = ∫ p(y* | w) p(w | D) dw. Lecture 8 shows that in Bayesian logistic regression, this has a concrete "moderation" effect — predicted probabilities are pulled toward 0.5 proportional to posterior uncertainty. The key insight: high-confidence predictions require both a high mean *and* low variance.
- **Product hypothesis**: When predicting "will this student enjoy this prof" (e.g. a match score based on student preferences + prof tags), use the posterior predictive distribution rather than MAP. For a prof with 5 reviews the match score should automatically be closer to 50% (moderation). This prevents confident-sounding recommendations based on thin data.
- **Data available**: Yes, though the "match score" feature may not exist yet.

### S6. Model evidence / Bayes factor (Occam's razor built-in)
- **Citation**: Lecture 10 Notes.pdf pp. 1–3 (Bayes factors, Bayes' example with 115/200 coin flips, Occam's razor).
- **Summary**: Given two models M1, M2 for the same data, the Bayes factor is the ratio of marginal likelihoods p(D|M1)/p(D|M2). More complex models automatically pay a complexity penalty because their predictive distribution must spread probability mass over a larger space of datasets. The lecture works through a coin-flip example showing how the simpler fixed-θ=½ model is narrowly favored over the θ∈(0,1) model even when the empirical frequency is not exactly ½.
- **Product hypothesis**: When building per-prof models (e.g. "is the grade distribution easy vs. hard?" or "do tags cluster into 2 or 3 archetypes?"), use marginal likelihood to decide the number of components automatically instead of hand-picking. Also useful for the review-text classifier: pick the complexity of the model based on available review count — profs with 5 reviews get the simple model, profs with 300 get the richer one.
- **Data available**: Yes.

### S7. Bayesian A/B comparison between two professors (hypothesis testing on posteriors)
- **Citation**: Lecture 3 Notes.pdf pp. 1–2 (hypothesis testing as integration over a posterior subset); Lecture 4 Notes.pdf p. 5 (hypothesis testing via Bayesian decision theory).
- **Summary**: A hypothesis is just a subset H ⊆ Θ of parameter space. Bayesian "testing" is computing P(θ ∈ H | D) by integrating the posterior. No null hypothesis, no p-value — you get a direct probability statement. Especially natural for comparisons: P(θ_A > θ_B | D_A, D_B) can be computed from two independent Beta posteriors by Monte Carlo.
- **Product hypothesis**: On the compare-professors page, show "P(Prof A is better rated than Prof B) = 83%" instead of (or alongside) the raw averages. This is far more intuitive to users than a t-test, and it incorporates sample size automatically (two profs with identical averages but different review counts will yield a probability near 50% if both have many reviews, or something further from 50% if one has many more reviews than the other).
- **Data available**: Yes.

---

## Tier A — concepts that would meaningfully improve the product with modest work

### A1. Bayesian linear regression (department-effects, feature-based rating prediction)
- **Citation**: Lecture 6 Notes.pdf pp. 1–3 (OLS + ridge); Lecture 7 Notes.pdf pp. 1–3 (Bayesian formulation, posterior on w, prediction distribution).
- **Summary**: Model a continuous outcome y as y = x⊤w + ε with Gaussian prior on weights. Yields closed-form Gaussian posterior over w and a Gaussian posterior predictive for new y*. Ridge regression is the MAP estimator under a zero-mean Gaussian prior (Lecture 7 p. 3 derives the exact λ = σ²/s² correspondence). Gives you both predictions *and* uncertainty.
- **Product hypothesis**: Fit a regression predicting overall rating from tag counts, difficulty score, department, and review count — this gives you (a) a "tag influence" explainer ("this prof's rating is high primarily because of 'caring' and 'clear'") on `ProfessorDetail`, and (b) an "expected rating at this school/department" baseline for comparing profs. Uncertainty in w translates into honest error bars.
- **Data available**: Yes — ratings, tag counts, difficulty, department all exist. A feature vector per professor is straightforward to construct.

### A2. Laplace approximation for Bayesian classification (tag prediction from review text)
- **Citation**: Lecture 8 Notes.pdf pp. 1–4 (full derivation of Laplace approx to posterior, Gaussian approx centered at MAP with covariance H⁻¹, moderation in predictions).
- **Summary**: When the posterior isn't tractable (logistic regression with Gaussian prior is the canonical example), approximate it with a Gaussian centered at the posterior mode (MAP) with covariance equal to the inverse Hessian of the negative log posterior. Gives approximate credible intervals on weights and a moderated prediction formula (p. 3–4).
- **Product hypothesis**: To auto-predict tags from review text ("did this review express 'tough grader'?"), train a logistic-regression classifier per tag with a Laplace-approximated posterior. The moderation effect means tags predicted from short, ambiguous reviews get scores near 0.5 automatically, so you don't auto-label weakly-signaled reviews. Improves the data-quality of tag counts downstream.
- **Data available**: Yes — review text + manually applied tags already exist as training labels.

### A3. Gaussian Processes for smoothing department/school-level trends
- **Citation**: Lecture 11 Notes.pdf pp. 1–6 (full GP definition, posterior GP, noise handling, hyperparameters, ML-II).
- **Summary**: A GP is an infinite-dimensional Gaussian over functions, specified by a mean µ(x) and kernel k(x, x′). Any finite collection of function values is jointly Gaussian. Conditioning on (noisy) observations yields a closed-form posterior GP. The kernel encodes smoothness assumptions ("profs with similar tag profiles should have similar ratings").
- **Product hypothesis**: Use a GP on the (difficulty, rating) plane (or higher-dim tag space) at the department level to smooth out the "rating landscape" for a department. You can then show a user "for profs with difficulty 3.5 in this department, the typical rating is 4.1 ± 0.3" — giving context for how a specific prof compares. This is a more flexible version of the hierarchical Beta model.
- **Data available**: Yes — all numeric features exist. GP scales O(n³) so you may need per-department models (fine if departments have <10k profs, which they will).

### A4. Covariance function choices & Automatic Relevance Determination (ARD)
- **Citation**: Lecture 14 Notes.pdf pp. 1–9 (Matérn, rational quadratic, ARD pp. 3–4, kernels for discrete data pp. 5–6, combining kernels pp. 5–7, string kernels pp. 7–8).
- **Summary**: Kernel choice encodes assumptions about the modeled function. Matérn kernels have a tunable smoothness ν; ARD kernels give each input dimension its own length scale, so features with very long posterior length scales are "irrelevant." Kernels can be summed or multiplied to compose models (Lecture 14 p. 5–7: Mauna Loa CO2 example combines 4 kernels for long-term, seasonal, medium-term irregular, and short-term). String kernels (p. 7–8) exist for text data.
- **Product hypothesis**: Use an ARD kernel when doing the GP smoothing above — the fitted length scales tell you which features (difficulty? department? review count? specific tags?) actually drive rating variation and which don't. Surface this as a "what matters for ratings at UMich" insight card. A bag-of-words string kernel on review text can underpin a "reviews similar to this one" feature.
- **Data available**: Yes. Free win: lecture notes explicitly describe a bag-of-words string kernel (p. 8) that plugs into any GP classification task.

### A5. GP classification via Assumed Density Filtering (probit regression on reviews)
- **Citation**: Lecture 12-13 Notes.pdf pp. 1–8 (full GP classification + ADF derivation; closed-form moments for probit p. 4–7).
- **Summary**: ADF is a one-pass approximation for non-Gaussian likelihoods: process each one-dimensional likelihood term sequentially, at each step matching the first two moments of the product (previous approx × current likelihood) and replacing with a Gaussian. For probit regression with a Gaussian prior, all site-parameter updates are closed form (Lecture 12-13 pp. 4–7).
- **Product hypothesis**: Classify whether a review is "positive" vs. "negative" (or "tough grader" vs. not) using a GP probit classifier over a text embedding. ADF gives you a fast, deterministic approximation — no MCMC required. Use the posterior variance to flag "uncertain" classifications for manual review or to down-weight them in downstream aggregation.
- **Data available**: Yes. Needs a text embedding step (sentence transformer, etc.) but review text is already stored.

### A6. Expectation Propagation (refinement over ADF)
- **Citation**: [BONUS] Expectation Propagation.pdf pp. 1–2.
- **Summary**: ADF's output depends on term ordering; EP fixes this by iteratively revisiting each site parameter. Form the cavity distribution (all terms except i), multiply by the true ith term to get the tilted distribution, moment-match a new approximate site term against the tilted distribution, repeat. The bonus file shows a specific EP update for truncation of a Gaussian (p. 2). EP is generally more accurate than Laplace for asymmetric/skewed posteriors (Figure 1, p. 1).
- **Product hypothesis**: Upgrade any Laplace or ADF approximation in the pipeline to EP once it's in production and latency allows. Specific application: if you add a "professor quality score" with hard upper/lower bounds (e.g. must be in [1,5]), the bonus file's truncated-Gaussian EP update is exactly the right tool — gives you a smooth, probabilistic enforcement of the bound instead of a hard clip.
- **Data available**: Yes.

### A7. Bayesian A/B testing / decision theory for product features
- **Citation**: Lecture 4 Notes.pdf pp. 2–4 (Bayesian decision theory, Bayes estimator, Bayes risk); Lecture 3 Notes.pdf pp. 1–2 (posterior hypothesis probability).
- **Summary**: Combine a Beta-Binomial model of conversion rate with Bayesian decision theory to choose between two product variants. P(variant A converts better than variant B | data) is directly computable from two Beta posteriors.
- **Product hypothesis**: When A/B testing product variants (e.g. "show credible interval vs. point estimate on professor card"), use Bayesian A/B rather than frequentist — makes the "probability version B is better" statement directly interpretable for non-technical stakeholders, and you can stop the test the moment probability crosses a threshold without p-hacking concerns.
- **Data available**: Yes, once analytics are wired up (Vercel analytics already in the stack per recent commit).

---

## Tier B — concepts that fit but the payoff is smaller

### B1. MAP estimation ("optimization is easier than integration")
- **Citation**: Lecture 4 Notes.pdf p. 3 (MAP as posterior-mode Bayes estimator under relaxed 0–1 loss); Lecture 7 Notes.pdf p. 3 (ridge = MAP under Gaussian prior); Lecture 8 Notes.pdf pp. 1–2 (MAP for logistic regression).
- **Summary**: The MAP estimator is the posterior mode — easier to compute than the full posterior because you only need to optimize, not integrate. Many common regularizers (L² = Gaussian prior, L¹ = Laplace prior) are MAP estimators in disguise.
- **Product hypothesis**: For display latency, compute MAP point estimates on the server for fast page loads, and fall back to full posterior calculation lazily (or in a worker) when the user clicks "show uncertainty." Lets you get the right math without paying the full Bayesian cost on every page view.
- **Data available**: Yes.

### B2. Bayesian Model Averaging
- **Citation**: Lecture 10 Notes.pdf p. 3 ("Bayesian Model Averaging" section).
- **Summary**: Rather than picking one model, weight predictions from multiple models by their posterior probabilities. Fully Bayesian but computationally expensive; the lecture notes explicitly say model selection is more common in practice because of the compute overhead.
- **Product hypothesis**: If you end up with multiple rating prediction models (text-based, tag-based, feature-based), BMA gives you a principled ensemble. Small payoff because (a) you'd need to maintain multiple models, (b) the lectures themselves call out that this is less common than single-model selection.
- **Data available**: Yes, but requires infrastructure for running multiple models concurrently.

### B3. Thompson sampling / bandits for recommendation
- **Citation**: Lecture 19 Notes.pdf pp. 5–6 (Thompson sampling in Bayesian optimization context).
- **Summary**: In a multi-armed-bandit or Bayesian optimization setting, sample one function from the current posterior and greedily pick the arg max. Auto-balances exploration and exploitation. The lecture covers TS in the BO context but the same algorithm applies to any "choose among K alternatives with uncertain reward" problem.
- **Product hypothesis**: If you add a "recommended professor for you" feature that personalizes over time, Thompson sampling over per-user models of prof preference is a clean fit. Smaller payoff than the core Tier-S items because the feature itself is more speculative.
- **Data available**: Partially — would need user-level interaction data (clicks, saves) which may not yet exist.

### B4. Upper Confidence Bound (UCB) for ranking
- **Citation**: Lecture 19 Notes.pdf pp. 3–4 (UCB definition, regret bound p. 5).
- **Summary**: Rank items by µ(x) + β·σ(x) — posterior mean plus β standard deviations. β tunes exploration vs. exploitation. Has provable regret bounds (Srinivas et al. 2010, cited p. 5).
- **Product hypothesis**: An "optimistic" ranking of professors by upper 95% credible bound would systematically surface under-reviewed professors who *might* be great, balancing discovery against popularity. Good for a "hidden gems" feature. Payoff is smaller than the shrinkage ranking because it requires the user to want exploration.
- **Data available**: Yes.

### B5. Expected Improvement for "next professor to review"
- **Citation**: Lecture 15 Notes.pdf pp. 5–6; Lecture 19 Notes.pdf pp. 1–2.
- **Summary**: EI picks the next query by expected marginal gain over the current best: max(0, f(x) − f′). Has a clean closed form under a GP posterior (p. 5 of Lecture 15).
- **Product hypothesis**: In a crowd-sourcing review-collection flow ("help us improve this department's data — please review one of these profs"), EI identifies which professor's review would be most informative about department-level quality. Niche feature.
- **Data available**: Yes but requires building the review-collection flow.

### B6. Active Search for "find all good professors in a department"
- **Citation**: Lecture 17 Notes.pdf pp. 1–4.
- **Summary**: Variant of BO where you want to find as many high-value items as possible instead of one maximum. Myopic policies are provably sub-optimal (p. 2–3); the lecture presents a non-myopic batch-rollout approximation from Jiang et al. 2017.
- **Product hypothesis**: "Find me all the great hidden-gem professors in my department" is exactly active search — rare valuable subset of a large domain. Small payoff because the user base is unlikely to request this phrased this way.
- **Data available**: Yes.

### B7. Cost-aware / multi-fidelity optimization
- **Citation**: Lecture 16 Notes.pdf pp. 1–6.
- **Summary**: Some observations are cheaper than others; trade off cost vs. expected gain. Multi-fidelity extends this to settings with cheap low-quality surrogates and expensive high-quality truth.
- **Product hypothesis**: Review text embeddings are cheap and noisy; full review reads are expensive and high-quality. A multi-fidelity formulation would let you automatically allocate attention. Niche — probably not worth the complexity.
- **Data available**: Yes, modulo building the two-fidelity pipeline.

### B8. Joint GPs / cross-covariance for multi-task learning
- **Citation**: Lecture 16 Notes.pdf pp. 4–5 (joint GP belief, cross-covariance).
- **Summary**: Stack multiple functions into one joint GP with cross-covariance kf g between them. Observations of f inform beliefs about g if the cross-covariance is nonzero.
- **Product hypothesis**: Model overall rating and difficulty as a joint GP with nonzero cross-covariance — then observations of just the rating automatically inform difficulty estimates and vice-versa, which helps when students leave one but not the other. Moderate but real value.
- **Data available**: Yes.

---

## Tier C — concepts taught but not a natural fit here

### C1. Bayesian quadrature (integral estimation)
- **Citation**: Lecture 20 Notes.pdf pp. 1–4.
- **Summary**: Treat the unknown integral of a function as a random variable, place a GP on f, derive a Gaussian posterior on the integral. Reduces to integrating the mean and covariance functions.
- **Why not a fit**: No product feature of a professor-review analyzer is naturally expressed as "estimate this integral." Could be contrived for e.g. total department-wide rating mass but that's not a user need.

### C2. ODE solving / Runge-Kutta / probabilistic IVP solvers
- **Citation**: Lecture 21-22 Notes.pdf pp. 1–8.
- **Summary**: Euler, midpoint, RK4 methods for ODEs; probabilistic (GP-based) analogs. Beautiful material but there is no ODE in professor review data.
- **Why not a fit**: Rate My Professor data isn't dynamical — there's no differential equation to solve.

### C3. Rejection sampling and importance sampling (as presented)
- **Citation**: Lecture 23 Notes.pdf pp. 1–3.
- **Summary**: Basic sampling methods. Rejection sampling wastes most samples (Neal's 1993 Bayesian NN example needed 2.6M proposals for 10 samples); importance sampling degenerates when the proposal is far from the target.
- **Why not a fit**: All the posteriors needed for the product are either conjugate (Beta-Binomial, Gaussian) or approximated via Laplace / ADF / EP, which are closed-form or near-closed-form. Pure rejection/importance sampling would only appear if you needed a posterior that didn't fit into those cases, which isn't currently the case.

### C4. MCMC (Metropolis-Hastings, Gibbs, HMC)
- **Citation**: Lecture 23 Notes.pdf pp. 4–5.
- **Summary**: Markov chains whose stationary distribution is the target posterior. MH proposes then accepts/rejects; Gibbs samples one coordinate at a time; HMC uses gradients of the log posterior for faster mixing.
- **Why not a fit**: Overkill for this product. The posteriors the user-facing features need are Beta-Binomial (closed form) or Gaussian (closed form / Laplace). MCMC would only pay off if you built a complex hierarchical model that exceeded what analytical tools can handle. Worth revisiting if/when you do — but not at product v1.

### C5. Efficient GP inference (Cholesky, CG, inducing points, Nyström)
- **Citation**: Lecture 18 Notebook.ipynb (entire notebook).
- **Summary**: Numerical tricks to scale GPs: Cholesky for stable inversion, rank-one updates for online inference, conjugate gradients for O(n²) approximate inversion, inducing-point sparse GPs via Nyström approx for O(nm²).
- **Why not a fit**: Needed only if you actually deploy GPs at scale. At current professor counts per department, direct GP inference is fine. This becomes Tier B the moment a GP feature ships.

### C6. Kernel trick as an abstract concept
- **Citation**: Lecture 9 Notes.pdf pp. 1–3; Lecture 9 OneNote.pdf (handwritten version of same material).
- **Summary**: Replace inner products in linear models with kernel evaluations to implicitly use high-dim feature spaces. Foundational for GPs but not a standalone feature.
- **Why not a fit (as a standalone concept)**: Relevant only through its use in Tier A's GP applications, where it's already folded in.

### C7. Probit regression specifically (vs. logistic)
- **Citation**: Lecture 7 Notes.pdf p. 4–5; Lecture 8 Notes.pdf pp. 3–4; Lecture 12-13 Notes.pdf pp. 4–7.
- **Summary**: Use the normal CDF Φ(·) as the sigmoid. Has heavier tails than logistic and — crucially — yields analytically-tractable moderation and ADF updates where the logistic function doesn't.
- **Why not a fit as C-tier rather than A-tier**: You *would* use probit specifically inside A5 (GP classification via ADF) — but "probit vs logistic" is a technical choice inside that feature, not a standalone feature. Included here for completeness.

### C8. Frequentist decision theory, risk functions, admissibility, p-values, confidence intervals
- **Citation**: Lecture 3 Notes.pdf pp. 2–5; Lecture 4 Notes.pdf pp. 3–4.
- **Summary**: Class covers these contrastively, to explain what Bayesian methods replace. The product is explicitly Bayesian so these are not applicable — they are the thing being replaced.
- **Why not a fit**: Included only so we don't pretend we considered them. We're building a Bayesian product; these belong to the alternative school.

---

## Top 15 picks for this product

1. **Shrinkage/partial-pooling ranking of professors** (S2): rank by Beta-Binomial posterior mean with α, β fit from department, not by raw average. Fixes the "5.0 from 2 reviews" artifact immediately. Cheap, high-impact, no new data.
2. **Beta posterior + 95% credible interval on "would take again %"** (S1): replace the bare headline number on `ProfessorDetail` with mean ± CI. Transparency win.
3. **P(Prof A > Prof B) in the compare view** (S7): one Monte Carlo integral over two Beta posteriors. Replaces/augments raw score comparisons with a statement users can actually reason about.
4. **Credible intervals not confidence intervals — and don't mislabel them** (S4): applies to every headline stat. Lecture 3 p. 5 is explicit about the common mislabeling.
5. **Loss-function-driven display mode** (S3): Expected / Typical / Most-likely toggle, defaulting to a mildly conservative asymmetric-loss point estimate.
6. **Tag-count-aware posterior predictive rating** (S5 + A1): Bayesian linear regression on (tag counts, difficulty, dept, review count) → rating, then predict with posterior predictive. Moderation on small-n profs is automatic.
7. **Per-tag posterior (Beta-Binomial on each tag)** (S1 extension): same treatment as would-take-again but for each tag independently, giving each tag its own credible band for aggregation and display.
8. **Department/school baselines via empirical-Bayes priors** (S2): empirically fit α, β per department, per school, maintain a small cascade of priors.
9. **Bayesian A/B for product decisions** (A7): use Beta posteriors + decision theory for feature rollouts instead of frequentist tests.
10. **Laplace-approximated logistic regression for auto-tagging review text** (A2): moderation effect means short reviews don't get over-confident tag labels.
11. **GP classification of review sentiment/tags via ADF** (A5): deterministic approximation, no MCMC, well-suited to the one-dimensional per-review likelihood factorization.
12. **GP smoothing of department rating landscape** (A3): contextualizes a single prof against the local rating surface.
13. **ARD kernel to report "what drives ratings at UMich"** (A4): surfaces which features actually move ratings, as a standalone insight card.
14. **Sum/product kernel composition for richer GP models** (A4, Lecture 14 p. 5–7): combine discrete (department) and continuous (difficulty) covariance functions rather than forcing everything into one kernel.
15. **Expectation Propagation upgrade path** (A6, bonus file): when Laplace isn't good enough (skewed posteriors, bounded quantities), swap in EP for a meaningfully better approximation — particularly the truncation EP update for any [1,5]-bounded quality score.
