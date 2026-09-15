"""Manual annotation of extracted triples: export sheets and score them.

export: writes, for the annotation documents,
  - annotation_sample.csv   every loadable triple, with empty `label` (correct /
                            incorrect) and `note` columns to fill in;
  - annotation_sections.csv the full text of every section of those documents
                            (including skipped ones), to find missing triples;
  - annotation_missing.csv  an empty template where each missing triple is one row
                            (same columns as the sample; relation and types must
                            come from the schema).

stability: writes annotation_stability.csv (triple_id, in_run2): whether each annotated
triple was also extracted by the second, independent run of the same pilot. It only
reads annotation_sample.csv.

score: computes precision, recall and F1 per relation type and per entity type
(a triple counts for both of its endpoint types) from the filled-in CSVs:
  precision = correct / labelled,  recall = correct / (correct + missing).
If annotation_stability.csv exists, precision is also reported separately for triples
found by both runs and by run 1 only.

Usage:
    python -m src.kg.annotation export
    python -m src.kg.annotation stability
    python -m src.kg.annotation score
"""
import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from src.kg.extract_closed import loadable_relations
from src.kg.pilot2_stats import normalized_key
from src.kg.schema import ENTITY_TYPES, RELATION_TYPES, is_valid_triple

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
KG_DIR = PROJECT_ROOT / "experiments" / "kg"
DEFAULT_INPUT = KG_DIR / "pilot3_closed_extraction.jsonl"
# Second run of the annotated pilot: same prompt and settings, separate cache.
DEFAULT_RUN2 = KG_DIR / "pilot3_closed_extraction_run2.jsonl"
STABILITY_CSV = KG_DIR / "annotation_stability.csv"
SAMPLE_CSV = KG_DIR / "annotation_sample.csv"
SECTIONS_CSV = KG_DIR / "annotation_sections.csv"
MISSING_CSV = KG_DIR / "annotation_missing.csv"
SCORES_JSON = KG_DIR / "annotation_scores.json"

# One document per domain (DMV, SSA, VA) from the 8 pilot documents, ~140 triples.
ANNOTATION_DOCS = [
    "Register a leased vehicle#1_0",
    "Appeal A Decision | Social Security Administration#2_0",
    "VA Housing Assistance | Veterans Affairs#1_0",
]

TRIPLE_COLUMNS = ["section_id", "source", "source_type", "relation", "target", "target_type", "evidence"]
SAMPLE_COLUMNS = ["triple_id"] + TRIPLE_COLUMNS + ["label", "note"]
MISSING_COLUMNS = TRIPLE_COLUMNS + ["note"]
CORRECT = {"correct", "c", "1", "yes", "y", "true"}
INCORRECT = {"incorrect", "i", "0", "no", "n", "false"}


def export(input_path: Path) -> None:
    records = [r for r in map(json.loads, open(input_path, encoding="utf-8")) if r["doc_id"] in ANNOTATION_DOCS]
    order = {d: i for i, d in enumerate(ANNOTATION_DOCS)}
    records.sort(key=lambda r: (order[r["doc_id"]], r["section_id"]))

    n = 0
    with open(SAMPLE_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SAMPLE_COLUMNS)
        w.writeheader()
        for r in records:
            for t in loadable_relations(r):
                n += 1
                w.writerow({"triple_id": f"t{n:04d}", "section_id": r["section_id"], "source": t["source"],
                            "source_type": t["source_type"], "relation": t["relation"], "target": t["target"],
                            "target_type": t["target_type"], "evidence": t["evidence"], "label": "", "note": ""})

    with open(SECTIONS_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["section_id", "document", "heading", "extracted", "text"])
        w.writeheader()
        for r in records:
            w.writerow({"section_id": r["section_id"], "document": r["title"], "heading": r["heading"],
                        "extracted": "no" if r["status"] == "skipped" else "yes", "text": r["text"]})

    if not MISSING_CSV.exists():
        with open(MISSING_CSV, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=MISSING_COLUMNS).writeheader()

    print(f"{n} triples from {len(records)} sections of {len(ANNOTATION_DOCS)} documents")
    print(f"-> {SAMPLE_CSV}\n-> {SECTIONS_CSV}\n-> {MISSING_CSV} (template, not overwritten)")


def _triple_key(section_id: str, source: str, relation: str, target: str) -> Tuple[str, str, str, str]:
    return section_id, normalized_key(source) or source.casefold(), relation, normalized_key(target) or target.casefold()


def stability(run2_path: Path) -> None:
    """Mark each annotated triple with whether run 2 also extracted it (loadable relations)."""
    run2 = set()
    for r in map(json.loads, open(run2_path, encoding="utf-8")):
        for t in r.get("relations", []):
            if t["schema_valid"]:
                run2.add(_triple_key(r["section_id"], t["source"], t["relation"], t["target"]))
    rows = _read(SAMPLE_CSV)
    with open(STABILITY_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["triple_id", "in_run2"])
        w.writeheader()
        for row in rows:
            key = _triple_key(row["section_id"], row["source"], row["relation"], row["target"])
            w.writerow({"triple_id": row["triple_id"], "in_run2": str(key in run2).lower()})
    n_in = sum(_triple_key(r["section_id"], r["source"], r["relation"], r["target"]) in run2 for r in rows)
    print(f"{n_in} of {len(rows)} annotated triples also found by run 2 -> {STABILITY_CSV}")


def _read(path: Path) -> List[Dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f)]


def _categories(row: Dict[str, str]) -> Iterable[Tuple[str, str]]:
    yield "relation", row["relation"]
    for t in {row["source_type"], row["target_type"]}:
        yield "entity_type", t


def _prf(tp: int, fp: int, fn: int) -> Dict[str, float]:
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f1 = 2 * p * r / (p + r) if p and r else (0.0 if p is not None and r is not None else None)
    return {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r, "f1": f1}


def score() -> Dict[str, object]:
    sample, missing = _read(SAMPLE_CSV), _read(MISSING_CSV)
    counts: Dict[Tuple[str, str], Dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    total = {"tp": 0, "fp": 0, "fn": 0}
    unlabelled, invalid_missing = [], []

    for row in sample:
        label = row["label"].lower()
        if label in CORRECT:
            key = "tp"
        elif label in INCORRECT:
            key = "fp"
        else:
            unlabelled.append(row["triple_id"])
            continue
        total[key] += 1
        for cat in _categories(row):
            counts[cat][key] += 1

    for i, row in enumerate(missing, start=2):  # row 1 is the header
        ok = (row["relation"] in RELATION_TYPES and row["source_type"] in ENTITY_TYPES
              and row["target_type"] in ENTITY_TYPES
              and is_valid_triple(row["relation"], row["source_type"], row["target_type"]))
        if not ok:
            invalid_missing.append(i)
            continue
        total["fn"] += 1
        for cat in _categories(row):
            counts[cat]["fn"] += 1

    by_stability = None
    if STABILITY_CSV.exists():
        in_run2 = {r["triple_id"]: r["in_run2"].lower() == "true" for r in _read(STABILITY_CSV)}
        split = {"both_runs": {"tp": 0, "fp": 0}, "run1_only": {"tp": 0, "fp": 0}}
        for row in sample:
            label = row["label"].lower()
            if row["triple_id"] not in in_run2 or label not in CORRECT | INCORRECT:
                continue
            bucket = split["both_runs" if in_run2[row["triple_id"]] else "run1_only"]
            bucket["tp" if label in CORRECT else "fp"] += 1
        by_stability = {k: {**v, "precision": v["tp"] / (v["tp"] + v["fp"]) if v["tp"] + v["fp"] else None}
                        for k, v in split.items()}

    result = {
        "overall": _prf(**total),
        "precision_by_stability": by_stability,
        "by_relation": {k[1]: _prf(**v) for k, v in sorted(counts.items()) if k[0] == "relation"},
        "by_entity_type": {k[1]: _prf(**v) for k, v in sorted(counts.items()) if k[0] == "entity_type"},
        "unlabelled_triples": unlabelled,
        "invalid_missing_rows": invalid_missing,
    }
    SCORES_JSON.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _fmt(x) -> str:
    return "  —  " if x is None else f"{x:5.3f}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["export", "stability", "score"])
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--run2", type=Path, default=DEFAULT_RUN2)
    args = parser.parse_args()

    if args.command == "export":
        export(args.input)
        return
    if args.command == "stability":
        stability(args.run2)
        return

    result = score()
    if result["unlabelled_triples"]:
        print(f"Warning: {len(result['unlabelled_triples'])} triples have no valid label and are excluded",
              file=sys.stderr)
    if result["invalid_missing_rows"]:
        print(f"Warning: rows {result['invalid_missing_rows']} of {MISSING_CSV.name} use an unknown relation or "
              f"type, or a pair the schema does not allow; they are excluded", file=sys.stderr)
    for title, table in (("Relation type", result["by_relation"]), ("Entity type", result["by_entity_type"])):
        print(f"\n{title:<16} {'TP':>4} {'FP':>4} {'FN':>4}  {'P':>5}  {'R':>5}  {'F1':>5}")
        for name, m in table.items():
            print(f"{name:<16} {m['tp']:>4} {m['fp']:>4} {m['fn']:>4}  "
                  f"{_fmt(m['precision'])}  {_fmt(m['recall'])}  {_fmt(m['f1'])}")
    o = result["overall"]
    print(f"\n{'Overall':<16} {o['tp']:>4} {o['fp']:>4} {o['fn']:>4}  "
          f"{_fmt(o['precision'])}  {_fmt(o['recall'])}  {_fmt(o['f1'])}")
    if result["precision_by_stability"]:
        print("\nPrecision by run agreement:")
        for name, m in result["precision_by_stability"].items():
            print(f"  {name:<10} {m['tp']:>4} correct / {m['tp'] + m['fp']:>4} labelled  P={_fmt(m['precision'])}")
    print(f"Saved -> {SCORES_JSON}")


if __name__ == "__main__":
    main()
