"""Aggregate the whole-document closed-schema pilot.

Reports type and property statistics, name quality, schema violations, the evidence
check, the entity cap, and entity overlap across sections of the same document
(the input for planning entity resolution).

Usage:
    python -m src.kg.pilot2_stats
"""
import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

from src.kg.pilot_stats import evidence_status
from src.kg.schema import ENTITY_TYPES, MAX_ENTITIES

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_INPUT = PROJECT_ROOT / "experiments" / "kg" / "pilot2_closed_extraction.jsonl"
DEFAULT_OUTPUT = PROJECT_ROOT / "experiments" / "kg" / "pilot2_stats.json"

_ARTICLES = re.compile(r"\b(a|an|the|your|you)\b")
_PAREN = re.compile(r"\s*\([^)]*\)")


def is_camel_case(name: str) -> bool:
    return " " not in name and any(c.isupper() for c in name[1:]) and any(c.islower() for c in name)


def exact_key(name: str) -> str:
    return name.casefold()


def normalized_key(name: str) -> str:
    """Light lexical normalisation: drop parentheticals, articles, punctuation, plural 's'."""
    text = _PAREN.sub("", name.casefold())
    text = _ARTICLES.sub(" ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    words = [w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w for w in text.split()]
    return " ".join(words)


def overlap(records: List[Dict[str, Any]], key_fn) -> Dict[str, Any]:
    """Within-document overlap of (key, type) entities across sections."""
    per_doc: Dict[str, Dict[Any, set]] = defaultdict(lambda: defaultdict(set))
    names: Dict[Any, set] = defaultdict(set)
    for r in records:
        for e in r["entities"]:
            k = (key_fn(e["name"]), e["type"])
            per_doc[r["doc_id"]][k].add(r["section_id"])
            names[k].add(e["name"])
    mentions = sum(len(secs) for d in per_doc.values() for secs in d.values())
    distinct = sum(len(d) for d in per_doc.values())
    multi = sum(1 for d in per_doc.values() for secs in d.values() if len(secs) > 1)
    multi_mentions = sum(len(secs) for d in per_doc.values() for secs in d.values() if len(secs) > 1)
    top = sorted(((len(secs), doc, k) for doc, d in per_doc.items() for k, secs in d.items() if len(secs) > 1),
                 reverse=True)[:15]

    cross: Dict[Any, set] = defaultdict(set)
    for doc, d in per_doc.items():
        for k in d:
            cross[k].add(doc)
    return {
        "mentions": mentions,
        "distinct_per_doc": distinct,
        "multi_section_entities": multi,
        "mentions_in_multi_section_entities": multi_mentions,
        "top_repeated": [{"key": k[0], "type": k[1], "sections": n, "doc_id": doc,
                          "surface_names": sorted(names[k])} for n, doc, k in top],
        "cross_document_entities": sum(1 for docs in cross.values() if len(docs) > 1),
        "cross_document_examples": sorted(f"{k[0]} [{k[1]}] ({len(docs)} docs)"
                                          for k, docs in cross.items() if len(docs) > 1)[:15],
    }


def aggregate(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    ents = [e for r in records for e in r["entities"]]
    rels = [x for r in records for x in r["relations"]]

    type_counts = Counter(e["type"] for e in ents)
    kind_counts = {t: dict(Counter(e["kind"] for e in ents if e["type"] == t))
                   for t, spec in ENTITY_TYPES.items() if spec["kinds"]}
    value_fill = {t: (sum(1 for e in ents if e["type"] == t and e["value"]), type_counts[t])
                  for t, spec in ENTITY_TYPES.items() if spec["value"]}
    text_fill = {t: (sum(1 for e in ents if e["type"] == t and e["text"]), type_counts[t])
                 for t in ("Requirement", "Outcome")}

    post = Counter()
    for r in records:
        post.update(r["postprocess"])

    violations = Counter((x["relation"], x["source_type"], x["target_type"]) for x in rels if not x["schema_valid"])

    evid = {"entities": Counter(), "relations": Counter()}
    for r in records:
        for e in r["entities"]:
            evid["entities"][evidence_status(e["evidence"], r["text"])] += 1
        for x in r["relations"]:
            evid["relations"][evidence_status(x["evidence"], r["text"])] += 1
    ellipsis = sum(1 for x in ents + rels if "..." in x["evidence"] or "…" in x["evidence"])

    cap_hits = [r for r in records if r.get("raw_n_entities", 0) >= MAX_ENTITIES]

    # Same surface name extracted with different types within a document.
    type_conflicts = []
    per_doc_types: Dict[tuple, set] = defaultdict(set)
    for r in records:
        for e in r["entities"]:
            per_doc_types[(r["doc_id"], exact_key(e["name"]))].add(e["type"])
    for (doc, name), types in per_doc_types.items():
        if len(types) > 1:
            type_conflicts.append({"doc_id": doc, "name": name, "types": sorted(types)})

    return {
        "n_documents": len({r["doc_id"] for r in records}),
        "n_sections": len(records),
        "n_sections_empty": sum(1 for r in records if not r["entities"]),
        "n_sections_is_table": sum(1 for r in records if r["is_table"]),
        "n_entities": len(ents),
        "n_relations": len(rels),
        "raw_entities": sum(r.get("raw_n_entities", 0) for r in records),
        "raw_relations": sum(r.get("raw_n_relations", 0) for r in records),
        "cap_hits": [{"section_id": r["section_id"], "is_table": r["is_table"]} for r in cap_hits],
        "postprocess": dict(post),
        "entity_types": dict(type_counts.most_common()),
        "relation_types": dict(Counter(x["relation"] for x in rels).most_common()),
        "kinds": kind_counts,
        "value_fill": value_fill,
        "text_fill": text_fill,
        "negated": sum(1 for e in ents if e["negated"]),
        "camel_case_names": sum(1 for e in ents if is_camel_case(e["name"])),
        "mean_name_words": sum(len(e["name"].split()) for e in ents) / max(1, len(ents)),
        "schema_violations": [{"relation": k[0], "source_type": k[1], "target_type": k[2], "count": n}
                              for k, n in violations.most_common()],
        "evidence_check": {k: dict(v) for k, v in evid.items()},
        "evidence_with_ellipsis": ellipsis,
        "overlap_exact": overlap(records, exact_key),
        "overlap_normalized": overlap(records, normalized_key),
        "type_conflicts": type_conflicts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    records = [json.loads(line) for line in open(args.input, encoding="utf-8")]
    stats = aggregate(records)
    args.output.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in stats.items()
                      if k not in ("overlap_exact", "overlap_normalized", "type_conflicts")}, indent=1))
    for k in ("overlap_exact", "overlap_normalized"):
        o = stats[k]
        print(f"{k}: mentions={o['mentions']} distinct={o['distinct_per_doc']} "
              f"multi-section={o['multi_section_entities']} cross-doc={o['cross_document_entities']}")
    print(f"type conflicts: {len(stats['type_conflicts'])}")
    print(f"Saved -> {args.output}")


if __name__ == "__main__":
    main()
