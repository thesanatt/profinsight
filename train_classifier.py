"""
Train the review topic classifier from tag-derived weak labels.

RateMyProfessors lets a reviewer attach up to three tags to a review. A review
whose tags all map to one of our five topic categories (grading, lectures,
workload, approachability, exams) becomes a weakly labeled training example.
The tags are never shown to the classifier, only the comment text, so the
labels are an independent (if noisy) signal.

Usage:
    python train_classifier.py                       # train on every data/<slug>.json
    python train_classifier.py --exclude umich,mit   # hold schools out (evaluate.py does this)
    python train_classifier.py --output models/nb_topic_model.json

The output is a plain JSON of per-class word counts and class priors that
bayesian_pipeline.py loads at startup (NaiveBayesClassifier.load).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import time

from bayesian_pipeline import NaiveBayesClassifier
from datafiles import list_raw, load_json

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
DEFAULT_OUTPUT = os.path.join(ROOT, "models", "nb_topic_model.json")

# RMP tag (lower-cased) -> topic category. Tags that do not map cleanly to one
# category ("participation matters", "skip class? you won't pass.", "online
# savvy", "would take again") are deliberately left out.
TAG_TO_CATEGORY = {
    "tough grader": "grading",
    "clear grading criteria": "grading",
    "graded by few things": "grading",
    "extra credit": "grading",
    "extra credit offered": "grading",
    "amazing lectures": "lectures",
    "lecture heavy": "lectures",
    "inspirational": "lectures",
    "hilarious": "lectures",
    "get ready to read": "workload",
    "lots of homework": "workload",
    "so many papers": "workload",
    "group projects": "workload",
    "accessible outside class": "approachability",
    "caring": "approachability",
    "cares about students": "approachability",
    "gives good feedback": "approachability",
    "respected": "approachability",
    "respected by students": "approachability",
    "test heavy": "exams",
    "beware of pop quizzes": "exams",
    "tests are tough": "exams",
    "tests? not many": "exams",
}


def weak_label(review: dict) -> str | None:
    """Return the single topic category implied by a review's tags, or None."""
    raw = review.get("rating_tags") or ""
    tags = [t.strip().lower() for t in raw.split("--") if t.strip()]
    cats = {TAG_TO_CATEGORY[t] for t in tags if t in TAG_TO_CATEGORY}
    if len(cats) != 1:
        return None
    if not (review.get("comment") or "").strip():
        return None
    return next(iter(cats))


def raw_school_files(data_dir: str = DATA_DIR) -> list[str]:
    """Raw scrape files (plain or gzipped), one per school."""
    return list_raw(data_dir)


def collect_weak_labels(files: list[str]) -> tuple[list[str], list[str]]:
    texts, labels = [], []
    for path in files:
        data = load_json(path)
        for prof in data.get("professors", []):
            for r in prof.get("reviews", []):
                lab = weak_label(r)
                if lab is not None:
                    texts.append(r["comment"])
                    labels.append(lab)
    return texts, labels


def train(files: list[str], uniform_prior: bool = False) -> NaiveBayesClassifier:
    texts, labels = collect_weak_labels(files)
    model = NaiveBayesClassifier(smoothing=1.0)
    model.fit(texts, labels, uniform_prior=uniform_prior)
    return model


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default=DATA_DIR)
    ap.add_argument("--exclude", default="", help="Comma-separated slugs to hold out")
    ap.add_argument("--output", default=DEFAULT_OUTPUT)
    ap.add_argument("--uniform-prior", action="store_true",
                    help="Use uniform class priors instead of empirical label frequencies")
    args = ap.parse_args()

    exclude = {s.strip() for s in args.exclude.split(",") if s.strip()}
    from datafiles import slug_from_raw
    files = [f for f in raw_school_files(args.data_dir) if slug_from_raw(f) not in exclude]
    t0 = time.time()
    model = train(files, uniform_prior=args.uniform_prior)
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    model.save(args.output)
    print(f"Trained on {model.n_training_docs} weak-labeled reviews from {len(files)} schools "
          f"in {time.time() - t0:.1f}s")
    print(f"Vocabulary: {len(model.vocab)} tokens; class priors: "
          + ", ".join(f"{c}={p:.3f}" for c, p in model.category_prior.items()))
    print(f"Saved -> {args.output} ({os.path.getsize(args.output) / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
