"""Aggregate pilot open-extraction output for schema design.

Reports entity/relation type frequencies with examples, evidence quotes that are
not verbatim in the section text (hallucination signal), and relations whose
endpoints are not among the section's extracted entities.

Usage:
    python -m src.kg.pilot_stats
"""
import argparse
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_INPUT = PROJECT_ROOT / "experiments" / "kg" / "pilot_open_extraction.jsonl"
DEFAULT_OUTPUT = PROJECT_ROOT / "experiments" / "kg" / "pilot_stats.json"
N_EXAMPLES = 3

_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"',
                         "–": "-", "—": "-", " ": " "})


def _strict(text: str) -> str:
    """Whitespace-collapsed text: evidence must match the section exactly otherwise."""
    return " ".join(text.split())


def _lenient(text: str) -> str:
    """Case-, punctuation- and quote-insensitive form, to separate copy noise from invention."""
    text = unicodedata.normalize("NFKC", text).translate(_QUOTES).lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def evidence_status(evidence: str, section_text: str) -> str:
    if _strict(evidence) in _strict(section_text):
        return "verbatim"
    if _lenient(evidence) in _lenient(section_text):
        return "near_verbatim"
    return "not_found"


def aggregate(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    ent_types: Counter = Counter()
    rel_types: Counter = Counter()
    ent_examples: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    rel_examples: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    evidence = {"entities": Counter(), "relations": Counter()}
    not_found: List[Dict[str, str]] = []
    dangling = 0

    for r in records:
        names = {e["name"] for e in r["entities"]}
        for e in r["entities"]:
            ent_types[e["type"]] += 1
            if len(ent_examples[e["type"]]) < N_EXAMPLES:
                ent_examples[e["type"]].append({"name": e["name"], "evidence": e["evidence"],
                                                "section_id": r["section_id"]})
            st = evidence_status(e["evidence"], r["text"])
            evidence["entities"][st] += 1
            if st == "not_found":
                not_found.append({"kind": "entity", "section_id": r["section_id"],
                                  "item": e["name"], "evidence": e["evidence"]})
        for rel in r["relations"]:
            rel_types[rel["relation"]] += 1
            if len(rel_examples[rel["relation"]]) < N_EXAMPLES:
                rel_examples[rel["relation"]].append({
                    "triple": f"{rel['source']} -[{rel['relation']}]-> {rel['target']}",
                    "evidence": rel["evidence"], "section_id": r["section_id"]})
            st = evidence_status(rel["evidence"], r["text"])
            evidence["relations"][st] += 1
            if st == "not_found":
                not_found.append({"kind": "relation", "section_id": r["section_id"],
                                  "item": f"{rel['source']} -[{rel['relation']}]-> {rel['target']}",
                                  "evidence": rel["evidence"]})
            if rel["source"] not in names or rel["target"] not in names:
                dangling += 1

    return {
        "n_sections": len(records),
        "n_sections_empty": sum(1 for r in records if not r["entities"]),
        "n_entities": sum(ent_types.values()),
        "n_relations": sum(rel_types.values()),
        "entity_types": [{"type": t, "count": c, "examples": ent_examples[t]}
                         for t, c in ent_types.most_common()],
        "relation_types": [{"relation": t, "count": c, "examples": rel_examples[t]}
                           for t, c in rel_types.most_common()],
        "evidence_check": {k: dict(v) for k, v in evidence.items()},
        "evidence_not_found": not_found,
        "dangling_relations": dangling,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    records = [json.loads(line) for line in open(args.input, encoding="utf-8")]
    stats = aggregate(records)
    args.output.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"{stats['n_sections']} sections, {stats['n_entities']} entities, "
          f"{stats['n_relations']} relations, {stats['n_sections_empty']} empty sections")
    print(f"{len(stats['entity_types'])} entity types, {len(stats['relation_types'])} relation types")
    print(f"Evidence check: {stats['evidence_check']}")
    print(f"Relations with endpoint not among extracted entities: {stats['dangling_relations']}")
    print(f"Saved -> {args.output}")


if __name__ == "__main__":
    main()
