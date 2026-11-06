"""Entity and relation precision from the labelled annotation set (experiments/kg_eval/).

Reads the `correct` (1/0) and `error_type` columns, and reports precision with a Wilson 95%
interval overall, per entity type and per relation type, plus the counts per error type.
By default it reads the 150-row sample of a file when one exists, otherwise the whole file.

    python experiments/kg_eval/score_precision.py
    python experiments/kg_eval/score_precision.py --entities experiments/kg_eval/entities.csv
"""
import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DIR = Path(__file__).resolve().parent
ENTITY_ERRORS = ("not_an_entity", "wrong_type", "bad_name", "wrong_merge")
RELATION_ERRORS = ("not_supported", "wrong_direction", "wrong_relation_type", "negation_lost", "self_or_circular")


def wilson(k: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


def default_path(name: str) -> Path:
    sample = DIR / f"{name}_sample150.csv"
    return sample if sample.exists() else DIR / f"{name}.csv"


def read_labels(path: Path, group_col: str, errors: Tuple[str, ...]) -> Tuple[List[Dict], List[str]]:
    rows, problems = [], []
    for r in csv.DictReader(open(path, encoding="utf-8")):
        c = (r.get("correct") or "").strip()
        if c == "":
            continue
        if c not in ("0", "1"):
            problems.append(f"{r.get('entity_id') or r.get('rel_id')}: correct = {c!r}")
            continue
        err = (r.get("error_type") or "").strip()
        if c == "0" and err not in errors:
            problems.append(f"{r.get('entity_id') or r.get('rel_id')}: error_type = {err!r}")
        rows.append({"correct": c == "1", "group": r[group_col], "error": err if c == "0" else ""})
    return rows, problems


def summary(rows: List[Dict], errors: Tuple[str, ...]) -> Dict:
    def prec(sub: List[Dict]) -> Dict:
        k, n = sum(r["correct"] for r in sub), len(sub)
        lo, hi = wilson(k, n)
        return {"n": n, "correct": k, "precision": k / n if n else None, "ci95": [lo, hi]}
    groups = defaultdict(list)
    for r in rows:
        groups[r["group"]].append(r)
    err = Counter(r["error"] for r in rows if not r["correct"])
    return {"overall": prec(rows),
            "by_group": {g: prec(sub) for g, sub in sorted(groups.items(), key=lambda kv: -len(kv[1]))},
            "errors": {e: err.get(e, 0) for e in errors} | {k: v for k, v in err.items() if k not in errors}}


def show(title: str, path: Path, s: Dict, n_rows: int, problems: List[str]) -> None:
    fmt = lambda p: f"{p['precision']*100:5.1f}% [{p['ci95'][0]*100:.1f}, {p['ci95'][1]*100:.1f}]" if p["n"] else "  -"
    o = s["overall"]
    print(f"\n{title} ({path.name}): {o['n']} of {n_rows} rows labelled")
    print(f"  overall        {o['correct']:3}/{o['n']:<3} {fmt(o)}")
    for g, p in s["by_group"].items():
        print(f"  {g:14} {p['correct']:3}/{p['n']:<3} {fmt(p)}")
    print("  errors: " + ", ".join(f"{e} {c}" for e, c in s["errors"].items()))
    for p in problems:
        print(f"  check: {p}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--entities", type=Path, default=None)
    ap.add_argument("--relations", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=DIR / "precision_scores.json")
    args = ap.parse_args()
    out = {}
    for name, path, col, errors in (("entities", args.entities or default_path("entities"), "type", ENTITY_ERRORS),
                                    ("relations", args.relations or default_path("relations"), "relation", RELATION_ERRORS)):
        n_rows = sum(1 for _ in csv.DictReader(open(path, encoding="utf-8")))
        rows, problems = read_labels(path, col, errors)
        s = summary(rows, errors)
        show(name.capitalize(), path, s, n_rows, problems)
        out[name] = {"file": path.name, "rows": n_rows, **s, "problems": problems}
    args.out.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()
