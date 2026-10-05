"""Compare two prompt versions on the annotated pilot documents.

Precision, recall (against gold_v1.csv and a pooled gold set) and F1, overall, per relation
and per document, with a paired bootstrap over sections. `check` scores an unlabelled run
(e.g. v2.1) on the triples whose labels can be carried over.

    python -m src.kg.compare_prompts
    python -m src.kg.compare_prompts check --input FILE --name v2.1
"""
import csv
import json
from collections import Counter, defaultdict
from math import sqrt
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from src.kg.annotation import CORRECT, KG_DIR, _triple_key
from src.kg.extract_closed import ANNOTATION_DOCS, loadable_relations
from src.kg.schema import SYMMETRIC_RELATIONS

GOLD_CSV = KG_DIR / "gold_v1.csv"
V1_CSV = KG_DIR / "annotation_sample.csv"
V2_CSV = KG_DIR / "annotation_v2.csv"
V2_RUN2 = KG_DIR / "v2_extraction_run2.jsonl"
OUT_JSON = KG_DIR / "v1_v2_comparison.json"
OUT_MD = KG_DIR / "v1_v2_comparison.md"
N_BOOT = 2000
SEED = 42

DOC_LABELS = {"Register a leased vehicle#1_0": "DMV leased vehicle",
              "Appeal A Decision | Social Security Administration#2_0": "SSA appeal",
              "VA Housing Assistance | Veterans Affairs#1_0": "VA housing"}


def _read(path: Path) -> List[Dict[str, str]]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [{k: (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]


def _doc(section_id: str) -> str:
    return section_id.split("::")[0]


def load_versions() -> Tuple[List[Dict[str, str]], Dict[str, List[Dict[str, Any]]]]:
    gold = _read(GOLD_CSV)
    v1 = [{**r, "correct": r["label"].lower() in CORRECT,
           "gold_id": r["triple_id"] if r["label"].lower() in CORRECT else ""} for r in _read(V1_CSV)]
    v2 = [{**r, "correct": r["label"].lower() in CORRECT} for r in _read(V2_CSV)]
    return gold, {"v1": v1, "v2": v2}


def scores(triples: List[Dict[str, Any]], gold: List[Dict[str, str]], sections: Optional[Set[str]] = None,
           relation: Optional[str] = None, doc: Optional[str] = None) -> Dict[str, Any]:
    def keep(sid: str) -> bool:
        return (sections is None or sid in sections) and (doc is None or _doc(sid) == doc)

    ts = [t for t in triples if keep(t["section_id"]) and (relation is None or t["relation"] == relation)]
    gs = [g for g in gold if keep(g["section_id"]) and (relation is None or g["relation"] == relation)]
    tp = sum(t["correct"] for t in ts)
    covered = {t["gold_id"] for t in triples if t["correct"] and t["gold_id"]} & {g["gold_id"] for g in gs}
    p = tp / len(ts) if ts else None
    r = len(covered) / len(gs) if gs else None
    f1 = 2 * p * r / (p + r) if p and r else (0.0 if p is not None and r is not None else None)
    return {"labelled": len(ts), "correct": tp, "gold": len(gs), "gold_found": len(covered),
            "precision": p, "recall": r, "f1": f1}


def bootstrap(gold, versions, n_boot: int = N_BOOT, seed: int = SEED) -> Dict[str, Any]:
    """Paired section bootstrap; returns percentile CIs for overall, per-relation and per-doc metrics."""
    sections = sorted({t["section_id"] for v in versions.values() for t in v} | {g["section_id"] for g in gold})
    rng = np.random.default_rng(seed)
    relations = sorted({t["relation"] for v in versions.values() for t in v} | {g["relation"] for g in gold})
    samples: Dict[str, List[float]] = defaultdict(list)

    for _ in range(n_boot):
        pick = Counter(rng.choice(len(sections), size=len(sections), replace=True))
        # Multiply each section by how often it was drawn.
        rep = {sections[i]: n for i, n in pick.items()}

        def weighted(vname: str, relation: Optional[str] = None, doc: Optional[str] = None) -> Tuple[Optional[float], ...]:
            ts = [t for t in versions[vname] if t["section_id"] in rep
                  and (relation is None or t["relation"] == relation) and (doc is None or _doc(t["section_id"]) == doc)]
            gs = [g for g in gold if g["section_id"] in rep
                  and (relation is None or g["relation"] == relation) and (doc is None or _doc(g["section_id"]) == doc)]
            found = {t["gold_id"] for t in versions[vname] if t["correct"] and t["gold_id"]}
            lab = sum(rep[t["section_id"]] for t in ts)
            cor = sum(rep[t["section_id"]] for t in ts if t["correct"])
            gtot = sum(rep[g["section_id"]] for g in gs)
            gfound = sum(rep[g["section_id"]] for g in gs if g["gold_id"] in found)
            p = cor / lab if lab else None
            r = gfound / gtot if gtot else None
            f = 2 * p * r / (p + r) if p and r else (0.0 if p is not None and r is not None else None)
            return p, r, f

        for scope, kw in [("overall", {})] + [(f"rel:{x}", {"relation": x}) for x in relations] + \
                         [(f"doc:{d}", {"doc": d}) for d in ANNOTATION_DOCS]:
            vals = {v: weighted(v, **kw) for v in versions}
            for v, (p, r, f) in vals.items():
                for m, x in (("precision", p), ("recall", r), ("f1", f)):
                    if x is not None:
                        samples[f"{scope}|{v}|{m}"].append(x)
            for m, i in (("precision", 0), ("recall", 1), ("f1", 2)):
                a, b = vals["v1"][i], vals["v2"][i]
                if a is not None and b is not None:
                    samples[f"{scope}|delta|{m}"].append(b - a)

    def ci(xs: List[float]) -> List[float]:
        return [float(np.percentile(xs, 2.5)), float(np.percentile(xs, 97.5))]

    return {k: {"ci": ci(v), "n": len(v)} for k, v in samples.items()}


def run_agreement() -> Dict[str, Any]:
    """Precision of v2 run-1 triples found by both runs vs by run 1 only."""
    run2 = set()
    for r in map(json.loads, open(V2_RUN2, encoding="utf-8")):
        if r["doc_id"] not in ANNOTATION_DOCS:
            continue
        for t in loadable_relations(r):
            run2.add(_triple_key(r["section_id"], t["source"], t["relation"], t["target"]))
            if t["relation"] in SYMMETRIC_RELATIONS:
                run2.add(_triple_key(r["section_id"], t["target"], t["relation"], t["source"]))
    out = {"both_runs": [0, 0], "run1_only": [0, 0]}
    rows = []
    for t in _read(V2_CSV):
        both = _triple_key(t["section_id"], t["source"], t["relation"], t["target"]) in run2
        bucket = out["both_runs" if both else "run1_only"]
        bucket[0] += t["label"].lower() in CORRECT
        bucket[1] += 1
        rows.append({"triple_id": t["triple_id"], "in_run2": both})

    def wilson(k: int, n: int, z: float = 1.96) -> List[float]:
        if not n:
            return [None, None]
        p = k / n
        d = 1 + z * z / n
        c = (p + z * z / (2 * n)) / d
        h = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
        return [c - h, c + h]

    return {k: {"correct": c, "labelled": n, "precision": c / n if n else None, "ci": wilson(c, n)}
            for k, (c, n) in out.items()} | {"_rows": rows}


SOCIAL_GOLD = {"t0130", "t0131", "t0132", "t0133", "t0134"}  # VBA -> Facebook/Instagram/... (dropped from KG)


def recall_variants(gold, versions, in_run2: Dict[str, bool]) -> Dict[str, Any]:
    v1, v2 = versions["v1"], versions["v2"]
    found = {"v1": {t["gold_id"] for t in v1 if t["correct"]},
             "v2": {t["gold_id"] for t in v2 if t["correct"] and t["gold_id"]}}
    extra = [t for t in v2 if t["correct"] and not t["gold_id"]]
    inter = [t for t in v2 if in_run2.get(t["triple_id"])]
    found["v2 intersection"] = {t["gold_id"] for t in inter if t["correct"] and t["gold_id"]}
    extra_inter = [t for t in inter if t["correct"] and not t["gold_id"]]
    n_gold, n_social = len(gold), len(SOCIAL_GOLD)
    out = {}
    for name in ("v1", "v2", "v2 intersection"):
        n_extra = {"v1": 0, "v2": len(extra), "v2 intersection": len(extra_inter)}[name]
        f = found[name]
        out[name] = {
            "fixed": len(f) / n_gold,
            "fixed_no_social": len(f - SOCIAL_GOLD) / (n_gold - n_social),
            "pooled": (len(f) + n_extra) / (n_gold + len(extra)),
            "pooled_no_social": (len(f - SOCIAL_GOLD) + n_extra) / (n_gold - n_social + len(extra)),
        }
    out["v2 intersection"]["precision"] = sum(t["correct"] for t in inter) / len(inter) if inter else None
    out["v2 intersection"]["labelled"] = len(inter)
    out["_pool_size"] = n_gold + len(extra)
    return out


def _pct(x: Optional[float]) -> str:
    return "—" if x is None else f"{100 * x:.1f}"


def _ci(b: Dict[str, Any], key: str) -> str:
    v = b.get(key)
    return "" if not v else f" [{100 * v['ci'][0]:.1f}, {100 * v['ci'][1]:.1f}]"


def _dci(b: Dict[str, Any], key: str) -> str:
    v = b.get(key)
    return "—" if not v else f"[{100 * v['ci'][0]:+.1f}, {100 * v['ci'][1]:+.1f}]"


def label_pool() -> Tuple[Dict[tuple, Tuple[str, str]], Dict[str, str]]:
    """{triple key: (label, pooled gold id)} from v1 + v2 + missed gold; {pooled id: relation}."""
    pool: Dict[tuple, Tuple[str, str]] = {}
    pooled_rel: Dict[str, str] = {}

    def add(section_id, source, relation, target, label, pid):
        for k in [_triple_key(section_id, source, relation, target)] + (
                [_triple_key(section_id, target, relation, source)] if relation in SYMMETRIC_RELATIONS else []):
            pool.setdefault(k, (label, pid))

    for g in _read(GOLD_CSV):
        pooled_rel[g["gold_id"]] = g["relation"]
        add(g["section_id"], g["source"], g["relation"], g["target"], "correct", g["gold_id"])
    for r in _read(V1_CSV):
        ok = r["label"].lower() in CORRECT
        add(r["section_id"], r["source"], r["relation"], r["target"], r["label"].lower(), r["triple_id"] if ok else "")
    for r in _read(V2_CSV):
        ok = r["label"].lower() in CORRECT
        pid = (r["gold_id"] or r["triple_id"]) if ok else ""
        if ok and not r["gold_id"]:
            pooled_rel[r["triple_id"]] = r["relation"]
        add(r["section_id"], r["source"], r["relation"], r["target"], r["label"].lower(), pid)
    return pool, pooled_rel


def pooled_facts() -> List[Dict[str, str]]:
    """The pooled gold facts with their triple fields (gold set + v2 correct outside it)."""
    facts = [{**g, "pid": g["gold_id"]} for g in _read(GOLD_CSV)]
    facts += [{**r, "pid": r["triple_id"]} for r in _read(V2_CSV) if r["label"].lower() in CORRECT and not r["gold_id"]]
    return facts


def _words(name: str) -> Set[str]:
    from src.kg.pilot2_stats import normalized_key
    return set(normalized_key(name).split())


def _overlap(a: str, b: str) -> float:
    wa, wb = _words(a), _words(b)
    return len(wa & wb) / len(wa | wb) if wa | wb else 0.0


def approx_found(triples: List[Tuple[str, Dict[str, Any]]], facts: List[Dict[str, str]], threshold: float = 0.5) -> Set[str]:
    """Pooled facts expressed by some triple: same section and relation, both endpoints mostly the same words."""
    found = set()
    for f in facts:
        for sid, t in triples:
            if sid != f["section_id"] or t["relation"] != f["relation"]:
                continue
            pairs = [(f["source"], f["target"])] + ([(f["target"], f["source"])] if f["relation"] in SYMMETRIC_RELATIONS else [])
            if any(_overlap(t["source"], a) >= threshold and _overlap(t["target"], b) >= threshold for a, b in pairs):
                found.add(f["pid"])
                break
    return found


def check(path: Path, name: str) -> Dict[str, Any]:
    pool, pooled_rel = label_pool()
    records = [r for r in map(json.loads, open(path, encoding="utf-8")) if r["doc_id"] in ANNOTATION_DOCS]
    triples = [(r["section_id"], t) for r in records for t in loadable_relations(r)]
    labelled = [(sid, t, pool[k]) for sid, t in triples
                if (k := _triple_key(sid, t["source"], t["relation"], t["target"])) in pool]
    correct = [x for x in labelled if x[2][0] in CORRECT]
    found = {x[2][1] for x in correct if x[2][1]}
    by_rel = Counter(t["relation"] for _, t in triples)
    rel_recall = {rel: (len({p for p in found if pooled_rel.get(p) == rel}),
                        sum(1 for v in pooled_rel.values() if v == rel)) for rel in sorted(set(pooled_rel.values()))}
    removed = []
    for r in records:
        for e in r.get("postfilter", []):
            if e["action"] in ("drop_relation", "flip_relation"):
                k = _triple_key(r["section_id"], e["source"], e["relation"], e["target"])
                removed.append({**e, "section_id": r["section_id"], "known_label": pool.get(k, ("", ""))[0]})
            else:
                removed.append({**e, "section_id": r["section_id"], "known_label": ""})
    facts = pooled_facts()
    approx = approx_found(triples, facts)
    approx_by_rel = {rel: (sum(1 for f in facts if f["pid"] in approx and f["relation"] == rel),
                           sum(1 for f in facts if f["relation"] == rel)) for rel in sorted({f["relation"] for f in facts})}
    return {
        "name": name, "loadable_triples": len(triples), "labelled": len(labelled), "correct": len(correct),
        "precision_labelled": len(correct) / len(labelled) if labelled else None,
        "pooled_recall": len(found) / len(pooled_rel), "pooled_size": len(pooled_rel),
        "pooled_recall_approx": len(approx) / len(facts), "approx_recall_by_relation": approx_by_rel,
        "relations": dict(by_rel), "recall_by_relation": rel_recall,
        "postfilter": removed,
    }


def main() -> None:
    gold, versions = load_versions()
    boot = bootstrap(gold, versions)
    result: Dict[str, Any] = {"overall": {}, "by_relation": {}, "by_document": {}}
    for v in versions:
        result["overall"][v] = scores(versions[v], gold)
    relations = sorted({t["relation"] for x in versions.values() for t in x} | {g["relation"] for g in gold})
    for rel in relations:
        result["by_relation"][rel] = {v: scores(versions[v], gold, relation=rel) for v in versions}
    for d in ANNOTATION_DOCS:
        result["by_document"][DOC_LABELS[d]] = {v: scores(versions[v], gold, doc=d) for v in versions}
    result["v2_correct_outside_gold"] = sum(1 for t in versions["v2"] if t["correct"] and not t["gold_id"])
    agreement = run_agreement()
    result["v2_run_agreement"] = {k: v for k, v in agreement.items() if not k.startswith("_")}
    in_run2 = {r["triple_id"]: r["in_run2"] for r in agreement["_rows"]}
    result["recall_variants"] = recall_variants(gold, versions, in_run2)
    result["bootstrap"] = boot
    OUT_JSON.write_text(json.dumps(result, indent=2), encoding="utf-8")
    with open(KG_DIR / "annotation_v2_stability.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["triple_id", "in_run2"])
        w.writeheader()
        w.writerows({"triple_id": r["triple_id"], "in_run2": str(r["in_run2"]).lower()} for r in agreement["_rows"])

    o1, o2 = result["overall"]["v1"], result["overall"]["v2"]
    lines = ["# Extraction prompt v1 vs v2 (3 annotated pilot documents)", "",
             "Paired section bootstrap, B = 2,000, 95% percentile CIs in brackets. Recall is against the same "
             f"{len(gold)} gold triples for both versions.", "",
             "| | v1 | v2 | v2 − v1 |", "|---|---|---|---|"]
    for m in ("precision", "recall", "f1"):
        lines.append(f"| {m.capitalize() if m != 'f1' else 'F1'} | {_pct(o1[m])}{_ci(boot, f'overall|v1|{m}')} | "
                     f"{_pct(o2[m])}{_ci(boot, f'overall|v2|{m}')} | "
                     f"{100 * (o2[m] - o1[m]):+.1f} {_dci(boot, f'overall|delta|{m}')} |")
    lines += [f"| Labelled triples (correct) | {o1['labelled']} ({o1['correct']}) | {o2['labelled']} ({o2['correct']}) | |",
              f"| Gold facts found (of {len(gold)}) | {o1['gold_found']} | {o2['gold_found']} | |",
              f"| Correct triples outside the gold set | 0 | {result['v2_correct_outside_gold']} | |", "",
              "## By relation", "",
              "| Relation | v1 P | v2 P | v1 R | v2 R | v1 F1 | v2 F1 | labelled v1 / v2 | gold |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for rel, s in result["by_relation"].items():
        a, b = s["v1"], s["v2"]
        lines.append(f"| {rel} | {_pct(a['precision'])} | {_pct(b['precision'])} | {_pct(a['recall'])} | "
                     f"{_pct(b['recall'])} | {_pct(a['f1'])} | {_pct(b['f1'])} | {a['labelled']} / {b['labelled']} | {a['gold']} |")
    lines += ["", "## By document", "",
              "| Document | v1 P | v2 P | v1 R | v2 R | v1 F1 | v2 F1 |", "|---|---|---|---|---|---|---|"]
    for name, s in result["by_document"].items():
        d = next(k for k, v in DOC_LABELS.items() if v == name)
        a, b = s["v1"], s["v2"]
        row = [name]
        for m in ("precision", "recall", "f1"):
            row += [f"{_pct(a[m])}{_ci(boot, f'doc:{d}|v1|{m}')}", f"{_pct(b[m])}{_ci(boot, f'doc:{d}|v2|{m}')}"]
        lines.append("| " + " | ".join([row[0], row[1], row[2], row[3], row[4], row[5], row[6]]) + " |")
    ag = result["v2_run_agreement"]
    lines += ["", "## v2 precision by run agreement (run-1 triples)", "",
              "| | Correct / labelled | Precision (Wilson 95% CI) |", "|---|---:|---|"]
    for k in ("both_runs", "run1_only"):
        a = ag[k]
        lines.append(f"| {k.replace('_', ' ')} | {a['correct']} / {a['labelled']} | {_pct(a['precision'])} "
                     f"[{_pct(a['ci'][0])}, {_pct(a['ci'][1])}] |")
    rv = result["recall_variants"]
    pool = rv["_pool_size"]
    lines += ["", "## Recall variants and the two-run intersection", "",
              f"The fixed gold set ({len(gold)}) was built from v1's output plus the facts v1 missed, so it favours v1. "
              f"Pooled: gold extended with v2's {result['v2_correct_outside_gold']} correct triples outside it "
              f"({pool} facts). No social: without the 5 social-media links the KG layer drops by design.", "",
              f"| | Precision | Recall (fixed {len(gold)}) | Recall (fixed, no social) | Recall (pooled) | Recall (pooled, no social) |",
              "|---|---:|---:|---:|---:|---:|"]
    precs = {"v1": o1["precision"], "v2": o2["precision"], "v2 intersection": rv["v2 intersection"]["precision"]}
    for name in ("v1", "v2", "v2 intersection"):
        r = rv[name]
        lines.append(f"| {name} | {_pct(precs[name])} | {_pct(r['fixed'])} | {_pct(r['fixed_no_social'])} | "
                     f"{_pct(r['pooled'])} | {_pct(r['pooled_no_social'])} |")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nSaved -> {OUT_JSON}, {OUT_MD}")


if __name__ == "__main__":
    import sys
    main_check() if len(sys.argv) > 1 and sys.argv[1] == "check" else main()


def main_check() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["check"])
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    res = check(args.input, args.name)
    out = KG_DIR / f"check_{args.name.replace('.', '')}.json"
    out.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "postfilter"}, indent=1))
    print(f"post-filter entries: {len(res['postfilter'])}; saved -> {out}")
