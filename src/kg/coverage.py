"""How well the graph covers the gold sections of dev-500 (or the validation split).

For each example: does the gold section have mentions, and is one of its entities named in
the question or the answer.

    python -m src.kg.coverage --scope pilot
    python -m src.kg.coverage --scope full [--examples validation]
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from src.data.loader import load_qa_pairs, load_sections, make_section_id
from src.kg.client import KGClient
from src.kg.resolve import key_of
from src.kg.stats import scope_documents

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
KG_DIR = PROJECT_ROOT / "experiments" / "kg"
DEV_IDS_FILE = PROJECT_ROOT / "data" / "dev_500_ids.json"
MIN_KEY_CHARS = 2


def load_examples(which: str = "dev500") -> List[Dict[str, Any]]:
    examples = load_qa_pairs(split="validation", max_examples=None)
    if which == "validation":
        return examples
    ids = json.loads(DEV_IDS_FILE.read_text(encoding="utf-8"))
    by_id = {ex["example_id"]: ex for ex in examples}
    return [by_id[i] for i in ids if i in by_id]


def gold_sections(example: Dict[str, Any], section_of_span: Dict[tuple, str]) -> Set[str]:
    return {section_of_span[(g["doc_id"], str(g["id_sp"]))] for g in example["grounding"]
            if (g.get("doc_id"), str(g.get("id_sp"))) in section_of_span}


def contains(text_key: str, key: str) -> bool:
    return len(key) >= MIN_KEY_CHARS and f" {key} " in f" {text_key} "


def section_entities(client: KGClient, scope: Optional[str], section_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """{section_id: {"n_mentions", "entities": {entity_id: {"name", "type", "keys"}}}} for the sections."""
    scope_m = "" if scope is None else " AND m.scope = $scope"
    rows = client.run(
        f"""
        MATCH (s:Section)-[:MENTIONS]->(m:Mention)-[:RESOLVES_TO]->(e:Entity)
        WHERE s.section_id IN $sids{scope_m}
        OPTIONAL MATCH (e)<-[:RESOLVES_TO]-(other:Mention)
        RETURN s.section_id AS sid, m.mention_id AS mid, e.entity_id AS eid, e.name AS name, e.type AS type,
               collect(DISTINCT other.name) AS names, collect(DISTINCT other.alias) AS aliases
        """, sids=section_ids, scope=scope)
    out: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"mentions": set(), "entities": {}})
    for r in rows:
        sec = out[r["sid"]]
        sec["mentions"].add(r["mid"])
        forms = {r["name"], *r["names"], *(a for a in r["aliases"] if a)}
        sec["entities"][r["eid"]] = {"name": r["name"], "type": r["type"],
                                     "keys": sorted({key_of(f) for f in forms if f})}
    return out


def coverage(client: KGClient, scope: Optional[str], which: str = "dev500") -> Dict[str, Any]:
    docs = set(scope_documents(client, scope))
    section_of_span = {(s["doc_id"], sp): make_section_id(s["doc_id"], s["id_sp"])
                       for s in load_sections() for sp in s["span_ids"]}
    examples = []
    for ex in load_examples(which):
        gold = {sid for sid in gold_sections(ex, section_of_span) if sid.split("::")[0] in docs}
        if gold:
            examples.append((ex, sorted(gold)))
    info = section_entities(client, scope, sorted({sid for _, g in examples for sid in g}))

    rows = []
    for ex, gold in examples:
        q, a = key_of(ex["question"]), key_of(ex["reference_answer"])
        ents = {eid: e for sid in gold for eid, e in info.get(sid, {"entities": {}})["entities"].items()}
        in_q = sorted({e["name"] for e in ents.values() if any(contains(q, k) for k in e["keys"])})
        in_a = sorted({e["name"] for e in ents.values() if any(contains(a, k) for k in e["keys"])})
        rows.append({
            "example_id": ex["example_id"], "domain": ex["domain"], "gold_sections": gold,
            "gold_has_mentions": any(info.get(sid, {}).get("mentions") for sid in gold),
            "gold_entities": len(ents), "entity_in_question": in_q, "entity_in_answer": in_a,
            "question": ex["question"], "reference_answer": ex["reference_answer"],
        })

    def share(pred) -> Dict[str, Any]:
        n = sum(1 for r in rows if pred(r))
        return {"n": n, "share": n / len(rows) if rows else None}

    summary = {
        "scope": scope or "*", "examples_from": which, "documents_in_scope": len(docs),
        "examples_in_scope": len(rows),
        "gold_section_has_mentions": share(lambda r: r["gold_has_mentions"]),
        "entity_matched_in_question": share(lambda r: r["entity_in_question"]),
        "entity_matched_in_answer": share(lambda r: r["entity_in_answer"]),
        "entity_matched_in_question_or_answer": share(lambda r: r["entity_in_question"] or r["entity_in_answer"]),
        "by_domain": {},
    }
    for dom in sorted({r["domain"] for r in rows}):
        sub = [r for r in rows if r["domain"] == dom]
        summary["by_domain"][dom] = {
            "examples": len(sub),
            "gold_has_mentions": sum(r["gold_has_mentions"] for r in sub),
            "entity_in_question_or_answer": sum(bool(r["entity_in_question"] or r["entity_in_answer"]) for r in sub),
        }
    return {"summary": summary, "examples": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scope", default="pilot", help="scope name, or '*' for all scopes")
    parser.add_argument("--examples", choices=["dev500", "validation"], default="dev500")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    scope = None if args.scope == "*" else args.scope
    with KGClient() as client:
        result = coverage(client, scope, args.examples)
    suffix = "" if args.examples == "dev500" else "_validation"
    output = args.output or KG_DIR / f"kg_coverage_{args.scope.replace('*', 'all')}{suffix}.json"
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    s = result["summary"]
    print(f"Scope {s['scope']}: {s['documents_in_scope']} documents, {s['examples_in_scope']} {s['examples_from']} "
          f"examples with a gold section in scope")
    for k in ("gold_section_has_mentions", "entity_matched_in_question", "entity_matched_in_answer",
              "entity_matched_in_question_or_answer"):
        v = s[k]
        print(f"  {k:38} {v['n']:4}  ({v['share']:.1%})" if v["share"] is not None else f"  {k}: -")
    print(f"  by domain: {s['by_domain']}")
    print(f"Saved -> {output}")


if __name__ == "__main__":
    main()
