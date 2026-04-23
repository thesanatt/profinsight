# 08_USER_RESEARCH.md

What college students actually complain about and wish for in course-selection tools. Research conducted April 2026 from Hacker News, student newspapers, Reddit-adjacent forums (StudentDoctor, College Confidential, Quora), and school-built tool history (CourseTable, PlanetTerp, Berkeleytime, Atlas, Coursicle, Course Critique).

**A note on source quality:** Reddit itself blocks WebFetch, so direct r/uofm / r/berkeley / r/college thread quotes are not cited here. Instead, the strongest signal comes from (a) student newspapers citing named students, (b) StudentDoctor forum threads that are substantively similar to Reddit, (c) long-lived school-built tools, which reveal revealed preferences (what students actually built and still use), and (d) published research on RMP. Where signal is weak or inferred, it's flagged.

---

## Top signals (ranked by how often it comes up)

### 1. Grade distributions are the single most-desired feature missing from RMP
Every long-lived student-built tool that displaces RMP on its home campus has grade distributions at its core: Georgia Tech's Course Critique (since 1976) is literally "a grade distribution platform" ([SGA repo](https://github.com/GT-SGA/Course-Critique)); UMD's PlanetTerp pulls data via PIA request from IRPA specifically to show "a graphical distribution of reported grades — even accounting for pluses and minuses" ([PlanetTerp about](https://planetterp.com/about)); Berkeleytime wraps CalAnswers grade data ([Berkeleytime grades](https://berkeleytime.com/grades)); Michigan's Atlas features "average grade distribution" as a core instructor-profile field ([Atlas about](https://atlas.ai.umich.edu/about/)). The fact that every major campus independently reinvented this is the strongest signal in the dataset. Students do not want a subjective "difficulty" score — they want the actual A/B/C/D/F breakdown.

### 2. Distrust of unverified reviews and fake ratings
This is the most-cited single complaint about RMP across student papers. LSU's Professor Index was launched in 2025 explicitly to fix "fraudulent reviews" by requiring .edu verification ([LSU Reveille](https://lsureveille.com/250418/news/lsu-professor-launches-competitor-to-rate-my-professors-website/)). Coursicle markets itself on `.edu` verification: "every reviewer must verify their .edu email" preventing "professors from rating themselves and... fake or bot reviews" ([Coursicle alternative](https://www.coursicle.com/blog/the-rate-my-professor-alternative/)). Quora threads describe professors leaving fake rebuttal reviews on their own profiles ([Quora thread](https://www.quora.com/Each-time-me-and-my-classmates-left-a-negative-review-on-ratemyprofessor-the-professor-left-a-fake-positive-one-contradicting-us-It-was-very-obvious-it-was-the-professor-How-common-is-it-for-professors-to-rate)).

### 3. Selection bias / bimodal reviews (the "extremes-only" problem)
Most frequently voiced complaint in published opinion pieces. StudentDoctor commenter Tizoc: "Generally the only people who bother posting are people who've had an especially negative, or especially positive experiences." ([SDN thread](https://forums.studentdoctor.net/threads/rate-my-professor-a-reliable-source.514488/)). JMU senior Isaac Weissmann: "I do find Rate My Professors to be generally negative… people that post either have a very, very good experience or a very bad experience." ([Breeze JMU](https://www.breezejmu.org/culture/students-professors-weigh-in-on-rate-my-professors-effectiveness/article_0d0d3c9c-7d22-11ee-81bb-f754077a1417.html)). The Post Athens: "unhappy people are more likely to share their experiences than satisfied people, which can skew ratings" ([The Post](https://www.thepostathens.com/article/2025/11/abby-shriver-rate-my-professors-bad-classes-unreliable)).

### 4. Outdated reviews
Multiple opinion pieces flag this. The Post Athens: "Reviews from previous semesters may not reflect current conditions, such as changes in attendance policies" ([The Post](https://www.thepostathens.com/article/2025/11/abby-shriver-rate-my-professors-bad-classes-unreliable)). Pepperdine Graphic: "Professors who have taught for years may have student reviews on their Rate My Professors page from a decade ago" ([Pepperdine](https://pepperdine-graphic.com/opinion-students-should-rethink-rate-my-professor/)). SDN commenter HumidBeing: "I find it most helpful when there are several years' worth of comments" — but this is about *volume*, and the same user cautions against one-off old reviews. Strong signal for **time-weighting**, not deletion.

### 5. Reddit-as-primary-source for candid info
Students increasingly prefer school subreddits over RMP for unstructured, detailed, conversational info ([Coursicle alternatives blog](https://www.coursicle.com/blog/websites-like-rate-my-professor/); [Michigan Daily](https://www.michigandaily.com/news/academics/why-do-incoming-freshmen-use-reddit-for-academic-advice/) notes incoming freshmen rely heavily on r/uofm). The advantage cited is "context about teaching style, grading, and workload that a star rating can't capture." This signals: numeric ratings alone are not enough; students want qualitative "story" context about *how* a prof teaches.

### 6. Grade-inflation bias ("easy → high rating")
Well-documented research finding. NewLaborForum: professor ratings increase when students rate the course as easy ([New Labor Forum](https://newlaborforum.cuny.edu/2018/02/16/making-the-grade-rating-professors/)). Yale CourseTable's own data confirms this: "as a course's average workload increased, its average rating showed a downward-sloping trendline" ([YDN CourseTable data](https://yaledailynews.com/articles/dewees-newton-dont-go-with-your-gut-on-coursetable) — cited via [YCS features](https://catalog.yale.edu/departmental_academic_support/ycs_features/) and summary search). Students "game" RMP by picking highest-easiness profs.

### 7. Documented gender / race bias in ratings
UI study of 14M RMP reviews: students are "two to three times more likely to use the words 'brilliant' or 'genius' to describe male professors" ([Times Higher Ed](https://www.timeshighereducation.com/news/large-rate-my-professor-study-finds-gender-bias-comments); [Inside Higher Ed](https://www.insidehighered.com/news/2015/02/09/new-analysis-rate-my-professors-finds-patterns-words-used-describe-men-and-women)). Female profs rated 28% lower on average; up to 38% lower in hard sciences ([Medium analysis](https://the-professor.medium.com/rate-my-professors-inaccurate-unreliable-sexist-and-probably-racist-81a2f06047cd)). This is a strong signal for de-biasing adjustments, though students don't *ask* for this — it's a fairness obligation.

### 8. Accurate "is Prof X actually teaching this section next semester?"
This is an underrated concrete frustration. Atlas markets real-time seat availability ([Atlas about](https://atlas.ai.umich.edu/about/); [Consider Magazine tips](https://www.considermagazine.org/post/5-advanced-tips-for-atlas-schedule-builder)). Coursicle's entire paid product is "notify me when class opens" — users complain when the notifications fail ([JustUseApp reviews](https://justuseapp.com/en/app/1187418307/coursicle/reviews)). RMP doesn't connect reviews to scheduled sections, so students often read reviews for a prof who isn't teaching the section they're registering for.

### 9. Teaching-style / qualitative details beyond a star
SDN users call out: "What I like to use RateMyProfessor for is finding teachers that use powerpoints, and post their lectures online" ([SDN](https://forums.studentdoctor.net/threads/rate-my-professor-a-reliable-source.514488/)). PlanetTerp built TA reviews in as a differentiator ([Diamondback](https://dbknews.com/2018/03/25/umd-student-planet-terp-website/)). Students want concrete attributes: posts lectures online, attendance mandatory, curves, problem-set vs exam weighted, group projects.

### 10. TA quality (often ignored by RMP entirely)
"One student said her favorite aspect of the site is the teaching assistant reviews" on PlanetTerp ([Diamondback 2018](https://dbknews.com/2018/03/25/umd-student-planet-terp-website/)). For large STEM courses, the TA often matters more than the lecturer.

---

## What students say existing tools get wrong

### RateMyProfessors specifically
- **No verification.** Anyone can post. Cited as the #1 flaw in nearly every comparison piece ([Coursicle](https://www.coursicle.com/blog/the-rate-my-professor-alternative/); [LSU Reveille](https://lsureveille.com/250418/news/lsu-professor-launches-competitor-to-rate-my-professors-website/)).
- **Simple average, not statistically sound.** Coursicle's explicit positioning: RMP uses "just a simple average," ignoring review volume and consistency ([Coursicle](https://www.coursicle.com/blog/the-rate-my-professor-alternative/)). This is ProfInsight's exact wedge (Bayesian posteriors) — the signal is real.
- **Duplicate profiles / name collisions.** Implied but not heavily quoted.
- **Ad-heavy interface.** Coursicle positioning point.
- **"Quality" and "Difficulty" are confounded.** Correlation −0.63 to −0.89 in research data, meaning students rate easiness, not teaching ([Medium study](https://the-professor.medium.com/rate-my-professors-inaccurate-unreliable-sexist-and-probably-racist-81a2f06047cd)).
- **Review bombing is possible.** ([The Gauntlet](https://thegauntlet.ca/2025/10/29/i-dont-trust-rate-my-professor-and-you-shouldnt-either/))
- **Tags are too generic** ("lots of homework" lacks precision — [StudyBreaks](https://studybreaks.com/college/rate-my-professors-bias/)).

### School-internal tools (Atlas, Wolverine Access, CalCentral)
- **Ugly, clunky interfaces.** This is the entire reason CourseTable, Berkeleytime, Hydrant, and similar exist. HN comment on Yale/CourseTable: "awful system implemented 20 years ago by Sungard... 'awful system implemented 1 year ago by Sungard'" ([HN 7084555](https://news.ycombinator.com/item?id=7084555)).
- **Don't surface reviews or grade data prominently.** Atlas is actually an exception here and heavily used at UMich; most schools' official catalogs are pure schedule-of-classes.
- **Slow/unresponsive during registration.** Multiple student newspapers complain about schedule-builder crashes on reg day ([The Gateway](https://thegatewayonline.ca/2024/05/my-schedule-builder-failed-to-make-enrolment-easier-for-students/); [Trent Arthur](https://www.trentarthur.ca/news/course-registration-changes-prompt-frustration-from-trent-students)).
- **Official course evaluations are often locked behind login, released too late, or never released at all.** UMD student Kevin Hu: "The advice I've gotten from these reviews was monumentally more helpful than what I've tried to glean from the university's in-house system." ([Diamondback 2019](https://dbknews.com/2019/04/03/umd-course-evaluations-reddit-planet-terp-professor-courseevalum-response-rate/)). The Aggie notes "many students don't know they can access course evaluations online" ([The Aggie](https://theaggie.org/2024/11/14/what-do-uc-davis-professors-think-of-rate-my-professors-and-student-course-evaluations)).

### Coursicle specifically
- **Review threshold hides data too aggressively.** Coursicle hides the rating until 5+ reviews exist ([Coursicle blog](https://www.coursicle.com/blog/how-to-read-reviews-on-coursicle/)), which is a deliberate reliability choice but frustrates users at small schools with few adjuncts.
- **Paid premium for tracking >1 course.** $5/semester — frequent complaint ([JustUseApp reviews](https://justuseapp.com/en/app/1187418307/coursicle/reviews)).
- **4.0 redesign broke UX.** ([The Hawkeye](https://ulmhawkeyeonline.com/34929/opinion/coursicle-4-0-update-worsens-platform-ruins-experience/)).

---

## Features I'd bet on (and why)

### Strong bet: **Time-weighted reviews** (with visible weighting, not silent)
Signal is clear (#4 above). Students don't say "delete old reviews" — they say "reviews from 10 years ago don't apply" and "I find it most helpful when there are several years' worth of comments" ([SDN](https://forums.studentdoctor.net/threads/rate-my-professor-a-reliable-source.514488/)). The ask is *weighting*, not filtering. Implementation: show a decay factor explicitly, and let users see "based on reviews from last 3 semesters" as a toggle. Almost free to build on top of Bayesian posteriors.

### Strong bet: **Grade distributions** (if you can get the data)
This is the #1 signal. Every long-lived campus tool has this. For UMich specifically, Atlas already does it — so ProfInsight's *wedge* must either (a) be a cross-school open-source clone of Atlas for schools that don't have one, or (b) add value on top of Atlas at UMich via better statistics and better UX. If you can legally scrape or get IRPA-style FOIA data, this is table stakes, not a nice-to-have.

### Strong bet: **"Who's teaching what next semester"** (section-level matchup)
Concrete pain point. Students currently have to cross-reference Wolverine Access / official schedule with RMP manually. Connecting sections → professor → reviews/grade-dist is low effort and high value. This is the "binding agent" that makes everything else useful at registration time, which is when students actually use these tools.

### Strong bet: **Verified .edu reviews** (to build trust for new content)
Coursicle's entire moat. LSU's Professor Index launched in 2025 explicitly on this. If ProfInsight wants user-contributed reviews (beyond scraping), verification is non-negotiable — students already don't trust RMP on this axis.

### Medium bet: **Workload in hours/week**
CourseTable's 1–5 workload scale is the single most-scanned filter at Yale ("scanning courses for high numbers next to teachers' names and low numbers in the column for workload" — [YDN](https://yaledailynews.com/articles/dewees-newton-dont-go-with-your-gut-on-coursetable)). Hours/week is more actionable than a 1–5 scale, but whether students actually calibrate to absolute numbers vs. relative scale is uncertain. Recommendation: collect both; surface relative workload first (they understand "heavy for this department"), hours/week as a detail.

### Medium bet: **Qualitative teaching-style tags** (with evidence)
Students clearly want to know: posts lectures online? curves? mandatory attendance? problem-set-heavy vs exam-heavy? RMP has generic tags. PlanetTerp lets TA reviews happen. These are answerable from syllabi if you have access to a syllabus corpus. Harder to do well, but differentiating.

### Medium bet: **Gender/race bias correction**
Students don't ask for this. But it's the right thing to do, publishable research backs it ([TimesHigherEd](https://www.timeshighereducation.com/news/large-rate-my-professor-study-finds-gender-bias-comments); [Inside Higher Ed](https://www.insidehighered.com/news/2018/03/14/study-says-students-rate-men-more-highly-women-even-when-theyre-teaching-identical)), and it fits the "calibrated priors" narrative of ProfInsight. Hidden by default, shown as a methodology note.

---

## Features that sound good but users don't actually use (or ask for)

### **Personalized grade predictions ("will I get an A?")**
**Verdict: mostly performative; don't prioritize.** I found no evidence students ask for this. What they *do* ask for is the raw grade distribution so *they* can decide. The modeling burden to do a personalized prediction honestly (it requires knowing the student's own GPA, prior courses, demographic, etc.) is enormous and the perceived credibility gain is low — students trust the raw %A number more than a predicted "you'll get an A− with 62% confidence" that they can't audit. Atlas, PlanetTerp, Course Critique, Berkeleytime all show distributions, none show personalized predictions. Revealed preference is strong: distributions yes, predictions no.

### **"If you liked Prof X, try Prof Y" recommendations**
**Verdict: weak signal; don't prioritize.** I searched specifically for this and found nothing. The closest analog is that students ask friends and upperclassmen, or compare two profs teaching the same course. The comparison happens within one course, not across different professors teaching different things. RMP's "compare professors" tool exists but is barely mentioned in the coverage. Collaborative filtering for professors sounds cute; no student in my sources ever asks for it.

### **Fit quizzes / personality matching**
**Verdict: weak signal; unlikely to see real use.** Zero evidence students ask for this. No long-lived campus tool has one. Students do ask "is this prof a good fit for me" — but the answer they want is a list of concrete attributes (gives partial credit? office hours? posts lectures?), not a personality-type match. Keep it if it's a marketing hook, but don't invest in making it deeper.

### **Side-by-side compare tools**
**Verdict: mixed — used, but only for the specific "same-course-two-sections" case.** RMP's compare tool is barely discussed in the literature. The implicit "I'm picking between Prof A and Prof B for Orgo" is always section-bounded. So a *compare* feature should only surface when two or more profs teach the *same* course the *same* semester. A generic "compare any two professors" is a gimmick — I found no source extolling it.

### **Removing "easy" / "difficulty" entirely**
Some academic critics propose it ([Medium](https://the-professor.medium.com/rate-my-professors-inaccurate-unreliable-sexist-and-probably-racist-81a2f06047cd)). But students *want* this info — it's the most-scanned filter on CourseTable. The correct move is to decorrelate it from quality in the aggregate, not hide it.

---

## Quotes (direct, cited)

> "The advice I've gotten from these reviews was monumentally more helpful than what I've tried to glean from the university's in-house system."
> — UMD student Kevin Hu, on PlanetTerp vs CourseEvalUM ([Diamondback](https://dbknews.com/2019/04/03/umd-course-evaluations-reddit-planet-terp-professor-courseevalum-response-rate/))

> "I've never experienced a professor that has not been accurate to what the Rate My Professors [page] is saying."
> — JMU senior Abby Cooke ([BreezeJMU](https://www.breezejmu.org/culture/students-professors-weigh-in-on-rate-my-professors-effectiveness/article_0d0d3c9c-7d22-11ee-81bb-f754077a1417.html))

> "[The website] only reflects one's personal experience in a class... doesn't really accurately represent how a professor is going to be perceived by a group."
> — JMU freshman Hallie Meyer ([BreezeJMU](https://www.breezejmu.org/culture/students-professors-weigh-in-on-rate-my-professors-effectiveness/article_0d0d3c9c-7d22-11ee-81bb-f754077a1417.html))

> "I do find Rate My Professors to be generally negative… people that post either have a very, very good experience or a very bad experience."
> — JMU senior Isaac Weissmann ([BreezeJMU](https://www.breezejmu.org/culture/students-professors-weigh-in-on-rate-my-professors-effectiveness/article_0d0d3c9c-7d22-11ee-81bb-f754077a1417.html))

> "Generally the only people who bother posting are people who've had an especially negative, or especially positive experiences... Using it to compare between 2 who teach the same class, gold."
> — StudentDoctor user Tizoc ([SDN](https://forums.studentdoctor.net/threads/rate-my-professor-a-reliable-source.514488/))

> "I'd need a prof to have at least 5+ in-depth reviews before I'd even pay attention."
> — StudentDoctor user MilkmanAl ([SDN](https://forums.studentdoctor.net/threads/rate-my-professor-a-reliable-source.514488/))

> "What I like to use RateMyProfessor for is finding teachers that use powerpoints, and post their lectures online."
> — StudentDoctor user ([SDN](https://forums.studentdoctor.net/threads/rate-my-professor-a-reliable-source.514488/))

> "pick a prof used to be an awesome site with professor grade distribution, but now it's a paid site."
> — StudentDoctor user lamenting loss of free grade distribution ([SDN](https://forums.studentdoctor.net/threads/rate-my-professor-a-reliable-source.514488/))

> "Students were two to three times more likely to use the words 'brilliant' or 'genius' to describe male professors as they were to describe female professors."
> — UIUC study of 14M RMP reviews ([Times Higher Ed](https://www.timeshighereducation.com/news/large-rate-my-professor-study-finds-gender-bias-comments))

> "Female professors receive poor reviews 28% more often than male professors... Female professors in hard sciences were rated up to 38% lower than their male counterparts."
> — Summary of published research ([Medium](https://the-professor.medium.com/rate-my-professors-inaccurate-unreliable-sexist-and-probably-racist-81a2f06047cd))

> "Why would they wait to climb through the bullshit bureaucracy when they can build something that helps all the students now?"
> — Hacker News comment on CourseTable at Yale ([HN 7084555](https://news.ycombinator.com/item?id=7084555))

> "[Students] tend to use [CourseTable] by scanning courses for high numbers next to teachers' names and low numbers in the column for workload."
> — Yale Daily News on CourseTable usage ([YDN](https://yaledailynews.com/articles/dewees-newton-dont-go-with-your-gut-on-coursetable))

> "It is the average of student responses on course evaluations to the question, 'What is your overall assessment of this course?'" — and as a course's average workload increased, its average rating showed a downward-sloping trendline."
> — YDN data analysis showing workload/rating inverse relationship ([YDN data](https://yaledailynews.com/articles/dewees-newton-dont-go-with-your-gut-on-coursetable))

> "You can go on the website and just post a comment, where with OurUMD it has to get approved first."
> — UMD student on why PlanetTerp beat the previous tool ([Diamondback 2018](https://dbknews.com/2018/03/25/umd-student-planet-terp-website/))

> "All reviews are manually verified by us before being displayed on the site."
> — PlanetTerp about page, describing moderation differentiator ([PlanetTerp](https://planetterp.com/about))

> "Every reviewer must verify their .edu email address before posting a review. This ensures one review per student, prevents fake reviews and bot spam, and stops professors from rating themselves."
> — Coursicle positioning ([Coursicle](https://www.coursicle.com/blog/the-rate-my-professor-alternative/))

> "Biases and outdated reviews can distort the reality of a class, making it a poor foundation for important academic decisions."
> — The Post at Ohio University ([The Post](https://www.thepostathens.com/article/2025/11/abby-shriver-rate-my-professors-bad-classes-unreliable))

---

## Bottom line for ProfInsight

**Bet on, in order:**
1. **Grade distributions** wired to specific sections and weighted by recency — this is the thing every serious campus tool has and RMP doesn't.
2. **Time-weighted reviews** — cheap layer on top of Bayesian posteriors, matches a real stated complaint.
3. **Section-level "who's teaching what next semester"** — this is the binding agent that makes a review site actually useful at registration time.
4. **Calibrated priors that explicitly discount gender/STEM/racial bias** — positions ProfInsight as research-grade in a way RMP can't copy without admitting fault.
5. **.edu verification** if/when you accept new reviews.

**Deprioritize:**
- Personalized grade predictions (distributions are what they actually want)
- If-you-liked-X recommendations (no student asks for this)
- Generic compare tools (only useful within a single course)
- Fit quizzes as anything but a marketing hook

**Caveat on signal strength:** Reddit's direct content is not quotable here (WebFetch blocked). My Reddit-proxy signal comes from student newspapers citing Reddit behavior and from StudentDoctor forums which skew pre-med. Weight accordingly.
