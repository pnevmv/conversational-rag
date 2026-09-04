"""Create and save a fixed 500-example dev subset of the MultiDoc2Dial validation split.

Sampling rules:
  - 125 examples per domain (dmv, ssa, studentaid, va), shuffled with seed=42
  - At least 30 unanswerable examples (supplement from full pool if needed)
  - Doc-switch examples are naturally ≥60 at this sample size

Output: data/dev_500_ids.json  — ordered list of example_id strings.
        data/dev_500_stats.json — composition summary.
"""
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data import load_qa_pairs

MIN_UNANSWERABLE = 30
MIN_DOC_SWITCH = 60
TARGET = 500
PER_DOMAIN = TARGET // 4  # 125


def main():
    print("Loading all validation examples...")
    all_examples = load_qa_pairs(split="validation", max_examples=None)
    print(f"  Loaded {len(all_examples)} total\n")

    rng = random.Random(42)

    # Group by domain
    by_domain: dict = defaultdict(list)
    for ex in all_examples:
        by_domain[ex["domain"]].append(ex)

    # 125 per domain, shuffled
    sampled = []
    for domain in sorted(by_domain):
        pool = by_domain[domain][:]
        rng.shuffle(pool)
        sampled.extend(pool[:PER_DOMAIN])
        print(f"  {domain}: took {PER_DOMAIN} of {len(pool)}")

    # Ensure ≥ MIN_UNANSWERABLE
    sampled_ids = {ex["example_id"] for ex in sampled}
    n_unans = sum(1 for ex in sampled if ex["is_unanswerable"])
    print(f"\n  Unanswerable after initial sample: {n_unans}")

    if n_unans < MIN_UNANSWERABLE:
        need = MIN_UNANSWERABLE - n_unans
        extra_pool = [ex for ex in all_examples
                      if ex["is_unanswerable"] and ex["example_id"] not in sampled_ids]
        rng.shuffle(extra_pool)
        additions = extra_pool[:need]

        # Drop the same number of answerable examples to keep total = 500
        answerable_indices = [i for i, ex in enumerate(sampled) if not ex["is_unanswerable"]]
        rng.shuffle(answerable_indices)
        drop_set = set(answerable_indices[:len(additions)])
        sampled = [ex for i, ex in enumerate(sampled) if i not in drop_set]
        sampled.extend(additions)
        print(f"  Added {len(additions)} unanswerable, dropped {len(additions)} answerable")

    # Final sort for reproducibility (stable order regardless of insertion order)
    sampled.sort(key=lambda x: x["example_id"])

    # Stats
    n_total = len(sampled)
    n_unans_final = sum(1 for ex in sampled if ex["is_unanswerable"])
    n_ds_final = sum(1 for ex in sampled if ex["is_doc_switch"])
    by_dom_final = defaultdict(int)
    for ex in sampled:
        by_dom_final[ex["domain"]] += 1

    print(f"\n  Final subset:")
    print(f"    Total       : {n_total}")
    for d in sorted(by_dom_final):
        print(f"    {d:12s}: {by_dom_final[d]}")
    print(f"    Unanswerable: {n_unans_final}")
    print(f"    Doc-switch  : {n_ds_final}")

    if n_unans_final < MIN_UNANSWERABLE:
        print(f"\n  WARNING: unanswerable count {n_unans_final} < {MIN_UNANSWERABLE}")
    if n_ds_final < MIN_DOC_SWITCH:
        print(f"\n  WARNING: doc-switch count {n_ds_final} < {MIN_DOC_SWITCH}")

    # Save IDs
    ids = [ex["example_id"] for ex in sampled]
    ids_path = PROJECT_ROOT / "data" / "dev_500_ids.json"
    ids_path.parent.mkdir(parents=True, exist_ok=True)
    ids_path.write_text(json.dumps(ids, indent=2), encoding="utf-8")
    print(f"\n  IDs saved to: {ids_path}")

    stats = {
        "total": n_total,
        "per_domain": dict(by_dom_final),
        "unanswerable": n_unans_final,
        "doc_switch": n_ds_final,
        "seed": 42,
        "per_domain_target": PER_DOMAIN,
    }
    stats_path = PROJECT_ROOT / "data" / "dev_500_stats.json"
    stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(f"  Stats saved to: {stats_path}")


if __name__ == "__main__":
    main()
