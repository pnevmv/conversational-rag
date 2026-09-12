"""Closed-schema entity and relation extraction from MultiDoc2Dial sections.

Uses the schema in src.kg.schema (9 entity types, 11 relation types, at most
MAX_ENTITIES entities per section), temperature 0 and a strict JSON schema. Raw
model outputs are cached per (section_id, prompt hash). Post-processing:
  - normalises names, drops empty and duplicate entities
  - clears `kind` / `value` where the type does not use them, maps unknown kinds to "other"
  - drops relations with an endpoint that is not an extracted entity, and self-loops
  - stores symmetric relations (ALTERNATIVE_TO) in one canonical direction
  - flags relations whose endpoint types violate the schema (kept, flagged)

The default mode is the whole-document pilot: every section of a fixed sample of
documents. `--tables` instead samples sections flagged is_table, to check the entity
cap on enumeration-heavy sections. Nothing is written to Neo4j.

Usage:
    python -m src.kg.extract_closed
    python -m src.kg.extract_closed --docs-per-domain 2 --seed 42 --workers 8
    python -m src.kg.extract_closed --tables --tables-per-domain 2
"""
import argparse
import hashlib
import json
import random
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Tuple

from src.data.loader import load_doc_domain_map, load_documents, load_sections
from src.kg.extract import DEFAULT_CACHE_DIR, DOMAINS, PROJECT_ROOT, ExtractionCache, _call_llm
from src.kg.schema import (
    ENTITY_TYPES,
    MAX_ENTITIES,
    RELATION_TYPES,
    SYMMETRIC_RELATIONS,
    extraction_json_schema,
    schema_prompt_block,
)
from src.kg.structure import is_table_like
from src.llm.client import LLMClient

DEFAULT_OUTPUT = PROJECT_ROOT / "experiments" / "kg" / "pilot2_closed_extraction.jsonl"
DEFAULT_TABLE_OUTPUT = PROJECT_ROOT / "experiments" / "kg" / "pilot2_table_extraction.jsonl"
# Whole-document pilot: documents of moderate length, so that cross-section entity
# overlap is measurable while the number of LLM calls stays small.
MIN_DOC_SECTIONS = 5
MAX_DOC_SECTIONS = 20

CLOSED_PROMPT = """You are building a knowledge graph of U.S. government services from official web pages.

Extract entities and relations from the section below, using ONLY the types listed.

{schema}

Rules:
- Extract only what the section states; do not add background knowledge.
- "name": the shortest noun phrase that names the entity, copied from the text in its natural form (e.g. "learner permit", "Supplemental Security Income (SSI)"). Never use CamelCase identifiers or invented labels.
- "kind": one of the listed kinds for Service, Organization, Amount and ContactPoint; null for other types.
- "value": the exact amount, duration or contact detail as written (e.g. "$25.00", "every 12 months", "800-827-1000") for Amount, TimeLimit and ContactPoint; null for other types.
- "text": for Requirement and Outcome, the full condition or consequence copied from the text; null for other types.
- "negated": true only when the text states the opposite (e.g. "photocopies are not accepted"); otherwise false.
- "evidence": ONE contiguous quote copied verbatim from the section text (at most ~25 words). Do not join fragments with "...".
- Relations: "source" and "target" must be the exact "name" of an extracted entity, and must respect the listed source -> target types. Use the relation in the stated direction (e.g. a service REQUIRES a requirement, never the reverse). Never relate an entity to itself.
- Extract at most {max_entities} entities: if the section lists more items than that (e.g. long enumerations), keep the ones most useful for answering a citizen's questions.
- If the section states nothing extractable, return empty lists.

Domain: {domain}
Document title: {title}
Section heading: {heading}
Section text:
\"\"\"
{text}
\"\"\"
"""


def sample_documents(docs_per_domain: int, seed: int) -> Dict[str, List[Dict[str, Any]]]:
    """Pick whole documents per domain; return {doc_id: [sections in document order]}."""
    domain_map = load_doc_domain_map()
    by_doc: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for s in load_sections():
        by_doc[s["doc_id"]].append(s)

    rng = random.Random(seed)
    picked: Dict[str, List[Dict[str, Any]]] = {}
    for dom in DOMAINS:
        pool = sorted(d for d, secs in by_doc.items()
                      if domain_map[d] == dom and MIN_DOC_SECTIONS <= len(secs) <= MAX_DOC_SECTIONS)
        for doc_id in rng.sample(pool, docs_per_domain):
            picked[doc_id] = [{**s, "domain": dom} for s in by_doc[doc_id]]
    return picked


def sample_table_sections(per_domain: int, seed: int) -> List[Dict[str, Any]]:
    """Pick `per_domain` sections flagged is_table from each domain."""
    domain_map = load_doc_domain_map()
    documents = load_documents()
    by_domain: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for s in load_sections():
        spans = documents[s["doc_id"]]["spans"]
        content_ids = s["span_ids"][1:] if s["section_title"] else s["span_ids"]
        if is_table_like([spans[i]["text_sp"] for i in content_ids]):
            by_domain[domain_map[s["doc_id"]]].append({**s, "domain": domain_map[s["doc_id"]]})
    rng = random.Random(seed)
    picked: List[Dict[str, Any]] = []
    for dom in DOMAINS:
        pool = sorted(by_domain[dom], key=lambda s: s["section_id"])
        picked.extend(rng.sample(pool, min(per_domain, len(pool))))
    return picked


def build_prompt(section: Dict[str, Any]) -> str:
    return CLOSED_PROMPT.format(
        schema=schema_prompt_block(),
        max_entities=MAX_ENTITIES,
        domain=section["domain"],
        title=section["title"],
        heading=section["section_title"] or "(none)",
        text=section["text"],
    )


def postprocess(raw: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, int]]:
    """Clean one section's raw extraction; return (entities, relations, counters)."""
    counts = defaultdict(int)
    entities: List[Dict[str, Any]] = []
    type_of: Dict[str, str] = {}
    for e in raw["entities"][:MAX_ENTITIES]:
        name = " ".join(e["name"].split())
        if not name:
            counts["entity_empty_name"] += 1
            continue
        if name.casefold() in type_of:
            counts["entity_duplicate"] += 1
            continue
        spec = ENTITY_TYPES[e["type"]]
        kind = (e["kind"] or "").strip().lower() or None
        if not spec["kinds"]:
            kind = None
        elif kind not in spec["kinds"]:
            counts["entity_kind_invalid"] += 1
            kind = "other"
        value = (e["value"] or "").strip() or None if spec["value"] else None
        if spec["value"] and value is None:
            counts["entity_value_missing"] += 1
        text = (e["text"] or "").strip() or None if e["type"] in ("Requirement", "Outcome") else None
        entities.append({"name": name, "type": e["type"], "kind": kind, "value": value, "text": text,
                         "negated": bool(e["negated"]), "evidence": e["evidence"]})
        type_of[name.casefold()] = e["type"]

    relations: List[Dict[str, Any]] = []
    seen = set()
    for r in raw["relations"]:
        src, dst = " ".join(r["source"].split()), " ".join(r["target"].split())
        if src.casefold() not in type_of or dst.casefold() not in type_of:
            counts["relation_dangling"] += 1
            continue
        if src.casefold() == dst.casefold():
            counts["relation_self_loop"] += 1
            continue
        rel = r["relation"]
        if rel in SYMMETRIC_RELATIONS and dst.casefold() < src.casefold():
            src, dst = dst, src
        key = (src.casefold(), rel, dst.casefold())
        if key in seen:
            counts["relation_duplicate"] += 1
            continue
        seen.add(key)
        spec = RELATION_TYPES[rel]
        src_type, dst_type = type_of[src.casefold()], type_of[dst.casefold()]
        valid = src_type in spec["source"] and dst_type in spec["target"]
        if rel in SYMMETRIC_RELATIONS:
            valid = valid or (dst_type in spec["source"] and src_type in spec["target"])
        if not valid:
            counts["relation_schema_violation"] += 1
        relations.append({"source": src, "relation": rel, "target": dst, "evidence": r["evidence"],
                          "source_type": src_type, "target_type": dst_type, "schema_valid": valid})
    return entities, relations, dict(counts)


def extract_section(client: LLMClient, cache: ExtractionCache, section: Dict[str, Any],
                    max_retries: int = 5) -> Tuple[Dict[str, Any], str, str]:
    """Return (raw extraction, prompt hash, status) for one section."""
    prompt = build_prompt(section)
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    raw = cache.get(section["section_id"], prompt_hash)
    status = "cached"
    if raw is None:
        raw = _call_llm(client, prompt, max_retries, schema=extraction_json_schema(),
                        schema_name="kg_closed_extraction")
        cache.put(section["section_id"], prompt_hash, raw)
        status = "success"
    return json.loads(raw), prompt_hash, status


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--docs-per-domain", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--tables", action="store_true", help="sample is_table sections instead")
    parser.add_argument("--tables-per-domain", type=int, default=2)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    args = parser.parse_args()

    documents = load_documents()
    if args.tables:
        sections = sample_table_sections(args.tables_per_domain, args.seed)
        output = args.output or DEFAULT_TABLE_OUTPUT
        print(f"Sampled {len(sections)} is_table sections ({args.tables_per_domain}/domain, seed={args.seed})")
    else:
        picked = sample_documents(args.docs_per_domain, args.seed)
        sections = [s for secs in picked.values() for s in secs]
        output = args.output or DEFAULT_OUTPUT
        print(f"Sampled {len(picked)} documents ({args.docs_per_domain}/domain, seed={args.seed}), "
              f"{len(sections)} sections")

    client = LLMClient()
    cache = ExtractionCache(args.cache_dir)

    def _task(section: Dict[str, Any]) -> Dict[str, Any]:
        spans = documents[section["doc_id"]]["spans"]
        content_ids = section["span_ids"][1:] if section["section_title"] else section["span_ids"]
        record = {
            "section_id": section["section_id"],
            "doc_id": section["doc_id"],
            "domain": section["domain"],
            "title": section["title"],
            "heading": section["section_title"],
            "text": section["text"],
            "is_table": is_table_like([spans[i]["text_sp"] for i in content_ids]),
            "model": client.default_model,
        }
        try:
            raw, prompt_hash, status = extract_section(client, cache, section)
            entities, relations, counts = postprocess(raw)
            record.update({
                "prompt_hash": prompt_hash,
                "raw_n_entities": len(raw["entities"]),
                "raw_n_relations": len(raw["relations"]),
                "entities": entities,
                "relations": relations,
                "postprocess": counts,
                "status": status,
            })
        except Exception as exc:
            record.update({"entities": [], "relations": [], "postprocess": {}, "status": f"error: {exc}"})
        return record

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        records = list(pool.map(_task, sections))

    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    statuses: Dict[str, int] = defaultdict(int)
    for r in records:
        statuses["error" if r["status"].startswith("error") else r["status"]] += 1
    print(f"Statuses: {dict(statuses)}")
    print(f"Kept {sum(len(r['entities']) for r in records)} entities, "
          f"{sum(len(r['relations']) for r in records)} relations -> {output}")


if __name__ == "__main__":
    main()
