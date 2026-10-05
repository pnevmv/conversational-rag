"""Annotation sheets for extracted triples and their scoring.

    python -m src.kg.annotation export      # sheets for the annotated documents
    python -m src.kg.annotation stability   # which annotated triples run 2 also found
    python -m src.kg.annotation score       # precision / recall / F1
    python -m src.kg.annotation score-er    # precision of entity clusters
    python -m src.kg.annotation carry --input FILE --prefix NAME   # reuse labels for a new run
    python -m src.kg.annotation gold        # rebuild gold_v1.csv
    python -m src.kg.annotation control --input FILE               # control sample
"""
import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

from src.kg.extract_closed import ANNOTATION_DOCS, loadable_relations
from src.kg.pilot2_stats import normalized_key
from src.kg.schema import ENTITY_TYPES, RELATION_TYPES, SYMMETRIC_RELATIONS, is_valid_triple

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
ER_CLUSTERS_CSV = KG_DIR / "er_pilot_clusters.csv"
ER_SCORES_JSON = KG_DIR / "er_annotation_scores.json"
RULE_EVIDENCE = ("alias", "acronym", "form_number")


TRIPLE_COLUMNS = ["section_id", "source", "source_type", "relation", "target", "target_type", "evidence"]
SAMPLE_COLUMNS = ["triple_id"] + TRIPLE_COLUMNS + ["label", "note"]
MISSING_COLUMNS = TRIPLE_COLUMNS + ["note"]
# Relation names of the candidate schema that were renamed in the final one; accepted in
# annotation_missing.csv so hand-written rows using the old name still count.
RELATION_ALIASES = {"HAS_FEE": "HAS_AMOUNT", "HAS_DEADLINE": "HAS_TIME_LIMIT"}
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


GOLD_CSV = KG_DIR / "gold_v1.csv"
CONTROL_CSV = KG_DIR / "annotation_control.csv"
CONTROL_SIZE = 30
NEW_COLUMNS = ["triple_id"] + TRIPLE_COLUMNS + [
    "label", "gold_id", "suggested_gold_id", "note", "similar_labelled", "section_heading", "section_text"]


def gold_triples() -> List[Dict[str, str]]:
    """The gold set: correct v1 triples (their triple_id) plus missed triples (m01, m02, ...)."""
    gold = [{**{k: r[k] for k in TRIPLE_COLUMNS}, "gold_id": r["triple_id"], "origin": "v1_correct"}
            for r in _read(SAMPLE_CSV) if r["label"].lower() in CORRECT]
    for i, r in enumerate(_read(MISSING_CSV), start=1):
        rel = RELATION_ALIASES.get(r["relation"], r["relation"])
        gold.append({**{k: r[k] for k in TRIPLE_COLUMNS}, "relation": rel, "gold_id": f"m{i:02d}", "origin": "v1_missed"})
    return gold


def control_sample(input_path: Path, size: int = CONTROL_SIZE, seed: int = 42) -> List[Dict[str, str]]:
    import random

    from src.data.loader import load_sections
    from src.kg.extract_closed import _with_domain, select_pilot_sections

    pilot_docs = {s["doc_id"] for s in select_pilot_sections(_with_domain(load_sections()), 2, 42)}
    records = [r for r in map(json.loads, open(input_path, encoding="utf-8"))
               if r["doc_id"] not in pilot_docs and r["status"] not in ("skipped",) and not r["status"].startswith("error")
               and loadable_relations(r)]
    records.sort(key=lambda r: r["section_id"])
    rng = random.Random(seed)
    rows = []
    for n, r in enumerate(rng.sample(records, min(size, len(records))), start=1):
        t = rng.choice(loadable_relations(r))
        rows.append({"triple_id": f"control_{n:03d}", "section_id": r["section_id"], "source": t["source"],
                     "source_type": t["source_type"], "relation": t["relation"], "target": t["target"],
                     "target_type": t["target_type"], "evidence": t["evidence"], "label": "", "gold_id": "",
                     "suggested_gold_id": "", "note": "", "similar_labelled": "",
                     "section_heading": r["heading"], "section_text": r["text"]})
    with open(CONTROL_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=NEW_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return rows


def write_gold() -> List[Dict[str, str]]:
    """(Re)write gold_v1.csv from the current v1 labels and missed triples."""
    gold = gold_triples()
    with open(GOLD_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["gold_id", "origin"] + TRIPLE_COLUMNS)
        w.writeheader()
        w.writerows({k: g[k] for k in ["gold_id", "origin"] + TRIPLE_COLUMNS} for g in gold)
    return gold


def carry(input_path: Path, prefix: str) -> None:
    sample = _read(SAMPLE_CSV)
    v1_by_key = {_triple_key(r["section_id"], r["source"], r["relation"], r["target"]): r for r in sample}
    gold = gold_triples()
    gold_by_key = {_triple_key(g["section_id"], g["source"], g["relation"], g["target"]): g for g in gold}

    def keys(section_id: str, source: str, relation: str, target: str):
        k = _triple_key(section_id, source, relation, target)
        if relation in SYMMETRIC_RELATIONS:
            return [k, _triple_key(section_id, target, relation, source)]
        return [k]

    records = [r for r in map(json.loads, open(input_path, encoding="utf-8")) if r["doc_id"] in ANNOTATION_DOCS]
    texts = {r["section_id"]: (r["heading"], r["text"]) for r in records}
    rows, n = [], 0
    for r in sorted(records, key=lambda r: (ANNOTATION_DOCS.index(r["doc_id"]), r["section_id"])):
        for t in loadable_relations(r):
            n += 1
            row = {"triple_id": f"{prefix}_{n:04d}", "section_id": r["section_id"], "source": t["source"],
                   "source_type": t["source_type"], "relation": t["relation"], "target": t["target"],
                   "target_type": t["target_type"], "evidence": t["evidence"], "label": "", "gold_id": "",
                   "label_source": "", "note": ""}
            ks = keys(r["section_id"], t["source"], t["relation"], t["target"])
            v1 = next((v1_by_key[k] for k in ks if k in v1_by_key), None)
            g = next((gold_by_key[k] for k in ks if k in gold_by_key), None)
            if v1 is not None and v1["label"]:
                row.update(label=v1["label"].lower(), label_source="v1_triple", note=v1["note"],
                           gold_id=v1["triple_id"] if v1["label"].lower() in CORRECT else "")
            elif g is not None:
                row.update(label="correct", label_source="v1_missed_gold", gold_id=g["gold_id"])
            rows.append(row)

    columns = ["triple_id"] + TRIPLE_COLUMNS + ["label", "gold_id", "label_source", "note"]
    write_gold()
    with open(KG_DIR / f"{prefix}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)

    # Context for labelling: labelled v1 triples and gold triples of the same section that
    # share the relation or an endpoint with the new triple.
    labelled = [{**r, "kind": f"v1 {r['label']}", "id": r["triple_id"]} for r in sample] + \
               [{**g, "kind": "gold", "id": g["gold_id"]} for g in gold if g["origin"] == "v1_missed"]
    new = [r for r in rows if not r["label"]]
    gold_ids = {g["gold_id"] for g in gold}

    def words(name: str) -> Set[str]:
        return set(normalized_key(name).split())

    def overlap(a: str, b: str) -> float:
        wa, wb = words(a), words(b)
        return len(wa & wb) / len(wa | wb) if wa | wb else 0.0

    def similarity(r: Dict[str, str], x: Dict[str, str]) -> float:
        direct = (overlap(r["source"], x["source"]) + overlap(r["target"], x["target"])) / 2
        flipped = (overlap(r["source"], x["target"]) + overlap(r["target"], x["source"])) / 2
        return max(direct, flipped if r["relation"] in SYMMETRIC_RELATIONS else 0.0) + 0.25 * (x["relation"] == r["relation"])

    def both_similar(r: Dict[str, str], x: Dict[str, str], threshold: float = 0.5) -> bool:
        """Each endpoint overlaps its counterpart (either direction for symmetric relations)."""
        pairs = [(x["source"], x["target"])] + ([(x["target"], x["source"])] if r["relation"] in SYMMETRIC_RELATIONS else [])
        return any(overlap(r["source"], s) >= threshold and overlap(r["target"], t) >= threshold for s, t in pairs)

    with open(KG_DIR / f"{prefix}_new.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["triple_id"] + TRIPLE_COLUMNS + [
            "label", "gold_id", "suggested_gold_id", "note", "similar_labelled", "section_heading", "section_text"])
        w.writeheader()
        for r in new:
            same_section = sorted((x for x in labelled if x["section_id"] == r["section_id"]),
                                  key=lambda x: -similarity(r, x))
            sim = [f"[{x['id']} {x['kind']}] {x['source']} -{x['relation']}-> {x['target']}"
                   for x in same_section if similarity(r, x) > 0][:5]
            best = next((x for x in same_section if x["id"] in gold_ids and x["relation"] == r["relation"]
                         and both_similar(r, x)), None)
            heading, text = texts[r["section_id"]]
            w.writerow({**{k: r[k] for k in ["triple_id"] + TRIPLE_COLUMNS}, "label": "", "gold_id": "",
                        "suggested_gold_id": best["id"] if best else "", "note": "",
                        "similar_labelled": " || ".join(sim), "section_heading": heading, "section_text": text})
    carried = Counter(r["label_source"] for r in rows if r["label"])
    print(f"{len(rows)} loadable triples; labels carried: {dict(carried)}; to label: {len(new)}")
    print(f"-> {GOLD_CSV}\n-> {KG_DIR / f'{prefix}.csv'}\n-> {KG_DIR / f'{prefix}_new.csv'}")


def _read(path: Path) -> List[Dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f)]


def _categories(row: Dict[str, str]) -> Iterable[Tuple[str, str]]:
    yield "relation", row["relation"]
    for t in {row["source_type"], row["target_type"]}:
        yield "entity_type", t


def _prf(tp: int, fp: int, fn: int, recall_annotated: bool = True) -> Dict[str, float]:
    """Precision, recall and F1. Without missing-triple annotation, recall and F1 are None
    (otherwise every recall would trivially be 1.0)."""
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if (tp + fn and recall_annotated) else None
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
        row = {**row, "relation": RELATION_ALIASES.get(row["relation"], row["relation"])}
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

    recall_annotated = bool(missing)
    result = {
        "recall_annotated": recall_annotated,
        "overall": _prf(**total, recall_annotated=recall_annotated),
        "precision_by_stability": by_stability,
        "by_relation": {k[1]: _prf(**v, recall_annotated=recall_annotated)
                        for k, v in sorted(counts.items()) if k[0] == "relation"},
        "by_entity_type": {k[1]: _prf(**v, recall_annotated=recall_annotated)
                           for k, v in sorted(counts.items()) if k[0] == "entity_type"},
        "unlabelled_triples": unlabelled,
        "invalid_missing_rows": invalid_missing,
    }
    SCORES_JSON.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def score_er() -> Dict[str, object]:
    rows = [r for r in _read(ER_CLUSTERS_CSV) if r["label"].lower() in CORRECT | INCORRECT]

    def _p(rs: List[Dict[str, str]]) -> Dict[str, object]:
        ok = sum(1 for r in rs if r["label"].lower() in CORRECT)
        return {"correct": ok, "labelled": len(rs), "precision": ok / len(rs) if rs else None}

    by_type: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for r in rows:
        by_type[r["type"]].append(r)
    norm_only = [r for r in rows if not r["merge_evidence"].strip()]
    with_rule = [r for r in rows if any(e in r["merge_evidence"] for e in RULE_EVIDENCE)]
    with_llm = [r for r in rows if r["merge_evidence"].strip() and r not in with_rule]
    result = {
        "overall": _p(rows),
        "by_type": {t: _p(rs) for t, rs in sorted(by_type.items())},
        "by_evidence": {"normalisation_only": _p(norm_only), "rule": _p(with_rule), "llm": _p(with_llm)},
        "unlabelled": sum(1 for r in _read(ER_CLUSTERS_CSV) if r["label"].lower() not in CORRECT | INCORRECT),
    }
    ER_SCORES_JSON.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _fmt(x) -> str:
    return "  —  " if x is None else f"{x:5.3f}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["export", "stability", "score", "score-er", "carry", "gold", "control"])
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--prefix", default="annotation_v2", help="carry: output file prefix")
    parser.add_argument("--run2", type=Path, default=DEFAULT_RUN2)
    args = parser.parse_args()

    if args.command == "export":
        export(args.input)
        return
    if args.command == "stability":
        stability(args.run2)
        return
    if args.command == "carry":
        carry(args.input, args.prefix)
        return
    if args.command == "control":
        rows = control_sample(args.input)
        print(f"{len(rows)} control triples -> {CONTROL_CSV}")
        return
    if args.command == "gold":
        gold = write_gold()
        print(f"{len(gold)} gold triples -> {GOLD_CSV}")
        return
    if args.command == "score-er":
        res = score_er()
        print(f"{'':16} {'correct':>8} {'labelled':>9}  {'P':>5}")
        for name, m in [("Overall", res["overall"])] + list(res["by_type"].items()) + \
                       [(f"via {k}", v) for k, v in res["by_evidence"].items()]:
            print(f"{name:16} {m['correct']:>8} {m['labelled']:>9}  {_fmt(m['precision'])}")
        print(f"Saved -> {ER_SCORES_JSON}")
        return

    result = score()
    if result["unlabelled_triples"]:
        print(f"Warning: {len(result['unlabelled_triples'])} triples have no valid label and are excluded",
              file=sys.stderr)
    if not result["recall_annotated"]:
        print(f"Note: {MISSING_CSV.name} has no rows, so recall and F1 are not reported", file=sys.stderr)
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
