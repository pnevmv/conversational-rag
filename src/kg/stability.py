"""Run-to-run stability of the closed-schema extraction.

Compares two extraction runs of the same sections (different caches, so the model is
called twice) at the level of entities (name, type) and triples
(source, relation, target), per section, with exact (case-insensitive) and lightly
normalised names.

Usage:
    python -m src.kg.stability
    python -m src.kg.stability --run1 A.jsonl --run2 B.jsonl --output stats.json
"""
import argparse
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Set, Tuple

from src.kg.extract_closed import loadable_relations
from src.kg.pilot2_stats import exact_key, normalized_key

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
KG_DIR = PROJECT_ROOT / "experiments" / "kg"


def _load(path: Path) -> Dict[str, Dict[str, Any]]:
    return {r["section_id"]: r for r in map(json.loads, open(path, encoding="utf-8")) if r["status"] != "skipped"}


def _agreement(a: Set, b: Set) -> Dict[str, float]:
    inter, union = len(a & b), len(a | b)
    return {
        "run1": len(a), "run2": len(b), "shared": inter,
        "jaccard": inter / union if union else 1.0,
        # share of each run's items that the other run also produced
        "run1_in_run2": inter / len(a) if a else 1.0,
        "run2_in_run1": inter / len(b) if b else 1.0,
    }


def compare(run1: Dict[str, Dict[str, Any]], run2: Dict[str, Dict[str, Any]],
            key: Callable[[str], str], loadable_only: bool) -> Dict[str, Any]:
    ents: Tuple[Set, Set] = (set(), set())
    triples: Tuple[Set, Set] = (set(), set())
    pairs: Tuple[Set, Set] = (set(), set())
    for sid in sorted(set(run1) & set(run2)):
        for i, rec in enumerate((run1[sid], run2[sid])):
            ents[i].update((sid, key(e["name"]), e["type"]) for e in rec["entities"])
            rels = loadable_relations(rec) if loadable_only else rec["relations"]
            for r in rels:
                triples[i].add((sid, key(r["source"]), r["relation"], key(r["target"])))
                pairs[i].add((sid, key(r["source"]), key(r["target"])))
    return {
        "entities": _agreement(*ents),
        "triples": _agreement(*triples),
        # same endpoints, relation label ignored: separates label flips from missing links
        "entity_pairs": _agreement(*pairs),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run1", type=Path, default=KG_DIR / "pilot3_closed_extraction.jsonl")
    parser.add_argument("--run2", type=Path, default=KG_DIR / "pilot3_closed_extraction_run2.jsonl")
    parser.add_argument("--output", type=Path, default=KG_DIR / "pilot3_stability.json")
    args = parser.parse_args()

    run1, run2 = _load(args.run1), _load(args.run2)
    result = {
        "sections_compared": len(set(run1) & set(run2)),
        "exact_names": {"all_relations": compare(run1, run2, exact_key, False),
                        "loadable_relations": compare(run1, run2, exact_key, True)},
        "normalized_names": {"all_relations": compare(run1, run2, normalized_key, False),
                             "loadable_relations": compare(run1, run2, normalized_key, True)},
    }
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Sections compared: {result['sections_compared']}")
    for names in ("exact_names", "normalized_names"):
        for scope in ("all_relations", "loadable_relations"):
            r = result[names][scope]
            print(f"{names:16} {scope:18} entities J={r['entities']['jaccard']:.3f}  "
                  f"triples J={r['triples']['jaccard']:.3f} "
                  f"(run1 in run2 {r['triples']['run1_in_run2']:.3f})  "
                  f"pairs J={r['entity_pairs']['jaccard']:.3f}")
    print(f"Saved -> {args.output}")


if __name__ == "__main__":
    main()
