"""Compare two extraction prompt versions on the annotated pilot documents.

Inputs (all in experiments/kg/):
  - gold_v1.csv            the 98 gold triples (correct v1 triples t####, missed m##)
  - annotation_sample.csv  v1 labels (pilot 3 run 1)
  - annotation_v2.csv      v2 labels (carried + new), with gold_id for correct triples that
                           express a gold fact
  - v2_extraction_run2.jsonl  second v2 run, for the run-agreement split

Metrics per version: precision (correct / labelled), recall (distinct gold facts expressed
by a correct triple / 98), F1, per relation (precision by the triple's relation, recall by
the gold fact's relation) and per document. Confidence intervals come from a paired
bootstrap over sections (B = 2,000, seed 42): sections are resampled with replacement and
both versions are scored on the same resample, which also gives CIs for the v2 - v1
differences. Correct v2 triples without a gold id are correct facts outside the gold set;
they count for precision but not for the fixed-gold recall. Because the gold set was built
from v1's own output plus the facts v1 missed, the fixed-gold recall favours v1; the report
therefore also gives a pooled recall (gold set extended with v2's correct triples outside it),
recall without the social-media links that the KG layer drops by design, and the scores of
the v2 two-run intersection.

Usage:
    python -m src.kg.compare_prompts
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
             "98 gold triples for both versions.", "",
             "| | v1 | v2 | v2 − v1 |", "|---|---|---|---|"]
    for m in ("precision", "recall", "f1"):
        lines.append(f"| {m.capitalize() if m != 'f1' else 'F1'} | {_pct(o1[m])}{_ci(boot, f'overall|v1|{m}')} | "
                     f"{_pct(o2[m])}{_ci(boot, f'overall|v2|{m}')} | "
                     f"{100 * (o2[m] - o1[m]):+.1f} {_dci(boot, f'overall|delta|{m}')} |")
    lines += [f"| Labelled triples (correct) | {o1['labelled']} ({o1['correct']}) | {o2['labelled']} ({o2['correct']}) | |",
              f"| Gold facts found (of 98) | {o1['gold_found']} | {o2['gold_found']} | |",
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
              "The fixed gold set (98) was built from v1's output plus the facts v1 missed, so it favours v1. "
              f"Pooled: gold extended with v2's {result['v2_correct_outside_gold']} correct triples outside it "
              f"({pool} facts). No social: without the 5 social-media links the KG layer drops by design.", "",
              "| | Precision | Recall (fixed 98) | Recall (fixed, no social) | Recall (pooled) | Recall (pooled, no social) |",
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
    main()
