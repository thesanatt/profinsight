# ProfInsight — Bayesian Enhancement Live Guide

This folder is my working memory. I update it continuously so I (and anyone reviewing) can see exactly what was done, why, and what is still to do. The goal is to minimize hallucination by grounding every claim in a file reference or lecture citation.

## Goal
Turn ProfInsight into a legitimately phenomenal product by wiring the Bayesian concepts taught in the user's class (`class_content/`) into the existing scoring/recommendation pipeline and UI. Also ship a one-command deployment script.

## Operating Principles
- **Ground truth over memory.** Every concept I apply cites a specific lecture PDF.
- **Current-state first.** I audit what the pipeline already does before adding anything.
- **Small, testable additions.** Each new Bayesian component is isolated so we can unit-test it.
- **User-visible.** If the math doesn't change the UI or the recommendations, it doesn't ship.

## Files in this folder
- `00_OVERVIEW.md` — this file
- `01_CURRENT_STATE.md` — what the codebase does today (filled by Explorer agent)
- `02_CLASS_CONCEPTS.md` — Bayesian concepts extracted from lectures (filled by Class-content agent)
- `03_GAP_ANALYSIS.md` — concepts that would materially improve the product but aren't implemented yet
- `04_PLAN.md` — prioritized implementation plan
- `05_PROGRESS_LOG.md` — append-only log of what I did and when
- `06_DEPLOYMENT.md` — deployment notes + script documentation
- `07_OPEN_QUESTIONS.md` — things I wasn't sure about; resolved once confirmed

## Anti-hallucination rules
1. Before citing a lecture, open its PDF.
2. Before claiming a file does X, read the file.
3. If a subagent reports something surprising, spot-check the underlying source.
4. Any claim about the API or data shape must be backed by a tested request or a direct read of the schema.
