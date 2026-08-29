# Talking about ProfInsight in an interview

Every number here is in `metrics/latest.md`, produced by `python evaluate.py`. If the two disagree, the metrics file wins; re-read it before an interview.

## The 60-second version

I built ProfInsight, a site that turns RateMyProfessors reviews into calibrated professor ratings. It covers 65 universities, 50,000 professors and 1.39 million reviews. The models are pure Python: a Beta-Binomial model with empirical-Bayes priors fit per department, a Gaussian process for rating trends, and a Naive Bayes topic classifier. I wrote an evaluation harness that splits each professor's reviews by date and scores every estimator on the later half. Shrinkage cuts held-out log-loss 46% for professors with fewer than five reviews. The harness also found four bugs that were live on the site, including a GP with no mean function that put the wrong trend label on 61% of professors. The API is FastAPI on Render, the frontend is React on Vercel, and GitHub Actions refreshes a third of the schools every night.

## One paragraph on architecture

A scraper hits RMP's GraphQL endpoint, discovers professors with two-letter search terms, pages through every review, and writes one JSON per school. The pipeline reads that file, fits school and department priors, runs the three models per professor and writes an analyzed JSON. Data is not in git: the nightly workflows publish gzipped raw and analyzed files to a rolling GitHub release, and the API downloads the analyzed set at boot when its data directory is empty (about 25 seconds for 65 schools), then loads files on demand into a small LRU cache and serves 16 routes. The React frontend is a hash-routed single page. A separate scraper pulls UMD's public course schedule and matches instructors to professors with rapidfuzz. Nothing in the modeling path imports NumPy, SciPy or scikit-learn; the Beta CDF is a continued fraction, the GP solve is a hand-written Cholesky, the prior fit is Nelder-Mead over the Beta-Binomial marginal likelihood.

## Six stories, each with a number

### 1. The prior fit was degenerate, and fixing it changed nothing

The empirical-Bayes prior was fit by method of moments on the raw variance of per-professor proportions. That variance includes binomial sampling noise, so it overstated between-professor spread and the concentration alpha + beta fell to the clamp floor of 2 in 80% of departments. I replaced it with type-II maximum likelihood over the Beta-Binomial marginal, which accounts for each professor's sample size. Then the harness showed the two estimators predict held-out outcomes almost identically: log-loss 0.3317 vs 0.3315 on take-again. The floor still binds, but for 35% of departments instead of 78%. The reason is that professors really are that heterogeneous; the ML fit also lands near alpha + beta of 2. The clamp had been accidentally right. I kept the ML estimator because it is correct by construction, and I report the null result.

What to say if asked "so was it worth it": the harness is what told me the fix did not matter, and the same harness is what makes every other number on the resume defensible.

The follow-up finding is more interesting. A prior-strength sweep in the harness (keep the EB mean, vary alpha + beta over 1 to 32) shows the best held-out log-loss at a concentration of about 4 to 8, not the 2 that maximum likelihood picks. Marginal likelihood fits the training halves; the test halves are later in time, and under drift a stronger pull toward the department mean predicts better. On the good-rating outcome this is why a fixed Beta(2,2) prior edges the ML prior overall. I report that as-is. The honest next step is to choose the concentration by temporal cross-validation inside the pipeline rather than by marginal likelihood.

### 2. The GP reverted to zero

Ratings live on a 1 to 5 scale and the GP had a zero prior mean, so in any gap wider than the six-month length-scale the posterior mean decayed toward zero. 51% of fitted curves dipped below one star. The trend label compares the first quarter of the curve to the last quarter, so this produced "Declining over time" for professors who had been steady at 4.5. Centering on the professor's mean fixed it. On the held-out test, the old GP predicted the next period's mean rating with 2.40 stars of error; the centered GP with a marginal-likelihood length-scale gets 0.63, about the same as the running average (0.64) and better than a last-5 average (0.68). The GP does not beat a running mean at point prediction; what it adds is the credible band and a trend label that is no longer wrong. The harness measures that directly: the trend label changes for 61% of professors between the old and the shipped GP; the biggest single flow is 166 professors going from "Declining over time" to "Consistently highly rated" in a 3,000-professor sample. Across three schools, "Declining over time" went from the most common label to the fourth. The chosen length-scales pile up at both ends of the grid (3 and 48 months), which says the fixed noise and signal variances are doing most of the work; a learned noise variance is the next step.

### 3. Self-training made the classifier worse than guessing

The topic classifier started from keyword seeds and then self-trained on its own confident predictions. RMP reviews carry tags like "Tough grader" and "Amazing lectures", which map to my five topics, so a review whose tags point to one topic is a weak label. I never used tags as features, so this is a fair test. Seeds alone scored 31.8% top-1 on 96,000 cross-school weak labels; seeds plus self-training scored 17.5%, under the 27.4% majority-class baseline. A supervised multinomial NB trained on 97,000 weak labels from the other 33 schools scored 53.2%, macro-F1 0.45. The shipped model is trained on all weak labels; the number I quote is the cross-school one. The exams class is the weak spot: it is 6% of labels and its F1 is under 0.1, so per-topic sentiment for exams is the least trustworthy card on the page.

### 4. Five schools were the wrong school

The scraper took the first hit from RMP's school search. For "University of California Irvine" the first hit is UC Riverside. Dallas returned Arlington, Texas A&M returned a Beaumont campus with five professors, USC returned its dentistry school with four, UCF returned a satellite campus, and Maryland returned UMBC. I found this because the harness prints per-school names next to slugs. The fix is a pinned school ID per ambiguous entry (27 of 80 configured schools are now pinned), a name-similarity sort on search results, and a rule that a scrape with fewer than 20 professors is not saved. UCI, UT Dallas, Texas A&M, USC, UCF, Florida State and University of Washington were re-scraped with the correct IDs (seven schools in total; FSU had been Panama City and UW had been Bothell).

### 5. Recency weighting is the best estimator, and I can show it

Each review's contribution to the Beta posterior decays with a three-year half-life. On the temporal hold-out that is the best single estimator: log-loss 0.326 on take-again against 0.332 for the unweighted posterior and 0.398 for the raw average, and the improvement holds in every sample-size bucket. It is also the best calibrated: nominal 90% predictive intervals cover 90.4% of held-out outcomes, against 88.5% for the unweighted posterior. It is the one feature where I had a hypothesis, tested it, and the test agreed.

### 6. The GP could not finish on the biggest school

BYU has a professor with 6,626 reviews. The GP solve is O(n cubed) in pure Python, and with the length-scale grid it runs six times per professor, so that one professor alone would take hours; the earlier April run of that school took most of an afternoon. The fix is statistical, not just engineering: bin ratings by calendar month, use the bin mean as the observation and scale the noise variance by one over the bin count. A professor is then at most 240 points regardless of review volume. BYU now analyzes in 22 seconds, all 65 schools in about ten minutes on ten cores, and the harness shows the binned GP predicts as well as the unbinned one.

## Numbers to have ready

| Number | Value | Where |
|---|---|---|
| Schools / professors / reviews | 65 / 50,842 / 1,386,314 | metrics dataset block |
| Words of review text | 64M | same |
| Log-loss reduction, EB vs raw, take-again | 16.6% overall, 46.3% for n <= 4 (35,075 professors, 384,800 held-out reviews) | shrinkage take_again |
| Log-loss reduction, good-rating | 14.5% overall, 50.5% for n <= 4 (46,670 professors, 698,356 held-out reviews) | shrinkage good_rating |
| 90% predictive interval coverage | 88.5% (take-again), 86.1% (good-rating); recency-weighted 90.4% / 89.4% | coverage |
| Department priors at floor, old vs new | 78% vs 35% (take-again), 76% vs 25% (good-rating) | dept_priors_at_floor |
| GP next-period MAE, old vs new | 2.40 vs 0.63 stars (running mean 0.64) | gp block |
| Curves below 1 star, old vs new | 51% vs 0.4% | gp block |
| Trend labels changed by the fix | 61.2% (3,000-professor harness sample) | gp block, trend_label_changed_pct |
| Classifier accuracy: majority / seeds / old / new | 27.4% / 31.8% / 17.5% / 53.2% on 96,274 cross-school weak labels | classifier block |
| Weak labels available | 193,036 (96,762 train + 96,274 test in the harness split) | classifier block |
| Grade-inflation slope | median 0.78 rating points per GPA point across 65 schools, split-half gap 0.05 | grade_inflation |
| Tests | 65 pytest cases, 107 doctests, CI on push | tests/, .github/workflows/test.yml |
| API routes | 16 | api.py |
| Pipeline speed | 65 schools in about 10 minutes on 10 cores; BYU (65K reviews) in 22 s | reanalysis log |
| UMD schedule join | 2,232 instructor assignments, 455 professors, 2,643 unmatched names | data/umd_schedule.json match_stats |
| Repository size, before vs after moving data to a release | 6.7 GB on GitHub vs under 2 MB tracked; deploy payload 118 MB gzipped | git count-objects, gh api repos/... size |

## Questions to expect

**Why Beta-Binomial instead of averaging stars?**
A star average from 3 reviews and one from 300 look identical. Turning each review into a Bernoulli outcome (rating at least 3.5, or would-take-again yes/no) gives a conjugate posterior with a real credible interval and a prior I can fit from the data. The cost is discarding some information in the 1 to 5 scale; the harness measures the trade and the posterior wins on held-out data.

**What is empirical Bayes doing here?**
The prior Beta(alpha, beta) for a department is fit from that department's professors by maximizing the Beta-Binomial marginal likelihood. A small-n professor is pulled toward the department's rate, with the amount of pull determined by how much professors in that department actually differ. Departments with fewer than 10 professors fall back to the school prior.

**Why type-II maximum likelihood instead of method of moments?**
The moment estimator on raw proportions counts sampling noise as between-professor variance. With three-review professors the noise dominates, so concentration collapses. The marginal likelihood conditions on each n_i. Story 1 covers why the result did not change.

**How do you know the intervals are calibrated?**
For each professor I compute the Beta-Binomial posterior-predictive interval on the number of successes in the held-out half and check whether the observed count falls inside. Nominal 90% intervals cover 88.5% on take-again and 86.1% on good-rating for the unweighted posterior, and 90.4% and 89.4% for the recency-weighted one. The under-coverage of the unweighted version is consistent with drift over time, which the split is designed to expose, and the recency weighting is what closes it.

**Why log-loss and Brier and not accuracy?**
The outputs are probabilities shown to users, so the metric has to score the probability, not a thresholded decision. Log-loss punishes confident wrong answers, which is exactly the small-n failure mode. Brier is bounded and easier to explain. I report both plus per-professor MAE.

**Is there leakage in the evaluation?**
Priors are fit on training halves only. The classifier is trained on one set of schools and scored on disjoint schools. Tags are never features. The split is by date within professor, so the test half is always later than the training half.

**How does the GP work without NumPy?**
Reviews are binned by calendar month (mean rating, count as weight), which caps a professor at 240 points; the noise on each bin is the base noise variance divided by its count. Kernel matrix from the RBF kernel over months-since-first-review, add the per-bin noise to the diagonal, Cholesky factor, two triangular solves for the posterior mean, one more per test point for the variance. The length-scale is chosen per professor from {3, 6, 12, 24, 48} months by log marginal likelihood; noise and signal variance are fixed. Before binning, one BYU professor with 6,626 reviews meant a 6,626-point O(n cubed) solve in pure Python that never finished; the whole school now takes 22 seconds.

**What does the classifier assume?**
Multinomial Naive Bayes: bag of words, class-conditional word independence, Laplace smoothing. The weak labels are noisy because a review tagged "Tough grader" may talk mostly about lectures. 52% over five classes is used to aggregate sentiment by topic across a professor's reviews, not to label one review.

**What is the grade-inflation slope?**
Within each professor, regress rating on the reviewer's reported GPA points after subtracting the professor's means, then pool the centered pairs. That is a fixed-effects estimator: it measures how much a student's own grade moves their rating of the same professor. Median 0.77 rating points per GPA point. The adjusted rating reports what a B student would give.

**What would you do next?**
Hierarchical priors that share strength across schools for small departments. A learned noise variance for the GP. Replace the weak-label NB with a small fine-tuned text model and compare on the same harness. Schedule joins for schools beyond UMD; the endpoints for Berkeley, UIUC and MIT were verified public.

**What are the weaknesses?**
Self-selected, unverified reviews; nothing in the model fixes selection bias. Per-school scrapes are capped at 1,500 professors. The site has no measured user traffic. See the Limitations section of the README.

## Rules for talking about it

Lead with the subject and the scale. Give one concrete technical choice. State the null result in story 1 plainly. Do not claim traffic, users or any number not in `metrics/latest.md`.
