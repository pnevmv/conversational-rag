"""Closed-schema entity and relation extraction from MultiDoc2Dial sections.

Uses the schema in src.kg.schema (9 entity types, 11 relation types, at most
MAX_ENTITIES entities per LLM call), temperature 0 and a strict JSON schema.
Extraction is organised in *units* (src.kg.planning): short and boilerplate sections
are skipped, a text repeated across sections is extracted once and attached to every
section where it occurs, and texts over CHUNK_MAX_CHARS are split into chunks at
sentence boundaries. Raw outputs are cached per (unit chunk, prompt hash).

Post-processing (per chunk, then merged per unit):
  - normalises names and aliases, drops empty and duplicate entities
  - clears `kind` / `value` where the type does not use them, maps unknown kinds to "other"
  - a ContactPoint whose evidence contains a phone number, address, email or URL must have
    a value: if the model left it empty, the detail found in the evidence is used
  - ContactPoints that are social-media links are flagged `is_social` (kept here, not
    loaded into the KG layer)
  - drops relations with an endpoint that is not an extracted entity, and self-loops
  - stores symmetric relations (ALTERNATIVE_TO) in one canonical direction
  - flags relations that violate the domain -> range rules (`schema_valid`); they stay in
    the output and are dropped at load time (see loadable_relations)

Modes (nothing is written to Neo4j):
    python -m src.kg.extract_closed                      # whole-document pilot (8 docs)
    python -m src.kg.extract_closed --tables             # is_table sections, 2 per domain
    python -m src.kg.extract_closed --regression         # sections behind known pilot-1 errors
    python -m src.kg.extract_closed --cache-dir DIR --output FILE   # e.g. a second run
"""
import argparse
import hashlib
import json
import random
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.data.loader import load_doc_domain_map, load_documents, load_sections
from src.kg.extract import DEFAULT_CACHE_DIR, DOMAINS, PROJECT_ROOT, ExtractionCache, _call_llm
from src.kg.planning import plan_units
from src.kg.schema import (
    ENTITY_TYPES,
    MAX_ENTITIES,
    SYMMETRIC_RELATIONS,
    extraction_json_schema,
    find_contact_detail,
    is_social_contact,
    is_valid_triple,
    schema_prompt_block,
)
from src.kg.structure import is_table_like
from src.llm.client import LLMClient

KG_DIR = PROJECT_ROOT / "experiments" / "kg"
DEFAULT_OUTPUTS = {
    "pilot": KG_DIR / "pilot4_closed_extraction.jsonl",
    "tables": KG_DIR / "pilot4_table_extraction.jsonl",
    "regression": KG_DIR / "regression_extraction.jsonl",
}
# Most deterministic sampling the deployment offers (pilot3_report.md, section 8): it is a
# reasoning model; temperature is accepted only with reasoning effort "none", and `seed` is
# not supported. Part of the cache key, so changing it re-runs the extraction.
CALL_PARAMS: Dict[str, Any] = {"reasoning": {"effort": "none"}, "temperature": 0}
# Whole-document pilot: documents of moderate length, so that cross-section entity
# overlap is measurable while the number of LLM calls stays small.
MIN_DOC_SECTIONS = 5
MAX_DOC_SECTIONS = 20

# Sections where the open-extraction pilot made known errors (reversed REQUIRES,
# requirement-as-source relations, self-loops, EXEMPTS instead of EXEMPT_FROM).
REGRESSION_SECTIONS = [
    "Get a learner permit#1_0::31",
    "Women's Health Care Needs | Veterans Affairs#1_0::1",
    "Commercial vehicle registration fees, vehicle use taxes and supplemental fees#3_0::34",
    "Benefits Planner: Disability | Are You Working | Social Security Administration#2_0::1",
    "Benefits Planner: Disability | Family Benefits | Social Security Administration#2_0::33",
    "Finding and Applying for Scholarships | Federal Student Aid#1_0::55",
    "Print Out Your VA Welcome Kit | Veterans Affairs#1_0::13",
    "Benefits Planner: Retirement | Medicare Premiums | SSA#1_0::32",
    "Benefits Planner: Retirement | Other Things to Consider | Social Security Administration#1_0::2",
    "Become a driving school instructor#3_0::10",
]

CLOSED_PROMPT = """You are building a knowledge graph of U.S. government services from official web pages.

Extract entities and relations from the section below, using ONLY the types listed.

{schema}

Rules:
- Extract only what the section states; do not add background knowledge.
- "name": the shortest noun phrase that names the entity, copied from the text in its natural form (e.g. "learner permit", "Supplemental Security Income (SSI)"). Never use CamelCase identifiers or invented labels.
- "alias": when the text gives both a full name and an abbreviation for the same entity (e.g. "Department of Motor Vehicles (DMV)"), put the full name in "name" and the abbreviation in "alias"; otherwise null.
- "kind": one of the listed kinds for Service, Organization, Amount and ContactPoint; null for other types.
- "value": the exact amount, duration or contact detail as written (e.g. "$25.00", "every 12 months", "800-827-1000") for Amount, TimeLimit and ContactPoint; null for other types, or when the text gives no value. For a ContactPoint whose evidence contains a phone number, postal address, email or URL, "value" is REQUIRED: copy that detail.
- "text": for Requirement and Outcome, the full condition or consequence copied from the text; null for other types.
- "negated": true only when the text states the opposite (e.g. "photocopies are not accepted"); otherwise false.
- "evidence": ONE contiguous quote copied verbatim from the section text (at most ~25 words). Do not join fragments with "...".
- Relations: "source" and "target" must be the exact "name" of an extracted entity, and must respect the listed source -> target types. Use the relation in the stated direction (e.g. a service REQUIRES a requirement, never the reverse). Never relate an entity to itself.
- Extract at most {max_entities} entities: if the text lists more items than that (e.g. long enumerations), keep the ones most useful for answering a citizen's questions.
- If the text states nothing extractable, return empty lists.

Domain: {domain}
Document title: {title}
Section heading: {heading}
{text_label}:
\"\"\"
{text}
\"\"\"
"""


class CacheMiss(LookupError):
    """Raised when a cache-only extraction (client=None) has no cached output."""


def build_prompt(section: Dict[str, Any], chunk: str, index: int, n_chunks: int) -> str:
    label = "Section text" if n_chunks == 1 else f"Section text (part {index + 1} of {n_chunks})"
    return CLOSED_PROMPT.format(
        schema=schema_prompt_block(),
        max_entities=MAX_ENTITIES,
        domain=section["domain"],
        title=section["title"],
        heading=section["section_title"] or "(none)",
        text_label=label,
        text=chunk,
    )


def extract_chunk(client: Optional[LLMClient], cache: ExtractionCache, unit: Dict[str, Any], index: int,
                  max_retries: int = 5) -> Tuple[Dict[str, Any], str]:
    """Return (raw extraction, status) for one chunk; client=None reads the cache only."""
    prompt = build_prompt(unit["representative"], unit["chunks"][index], index, len(unit["chunks"]))
    prompt_hash = hashlib.sha256(
        f"{prompt}\x00{json.dumps(CALL_PARAMS, sort_keys=True)}".encode("utf-8")).hexdigest()
    key = f"{unit['unit_id']}::chunk{index}"
    raw = cache.get(key, prompt_hash)
    if raw is not None:
        return json.loads(raw), "cached"
    if client is None:
        raise CacheMiss(key)
    raw = _call_llm(client, prompt, max_retries, schema=extraction_json_schema(),
                    schema_name="kg_closed_extraction", params=CALL_PARAMS)
    cache.put(key, prompt_hash, raw)
    return json.loads(raw), "success"


def _clean(text: Optional[str]) -> Optional[str]:
    return " ".join(text.split()) or None if text else None


def postprocess(raw: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, int]]:
    """Clean one chunk's raw extraction; return (entities, relations, counters)."""
    counts: Dict[str, int] = defaultdict(int)
    entities: List[Dict[str, Any]] = []
    type_of: Dict[str, str] = {}
    for e in raw["entities"][:MAX_ENTITIES]:
        name = _clean(e["name"])
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
        value = _clean(e["value"]) if spec["value"] else None
        if e["type"] == "ContactPoint" and value is None and find_contact_detail(e["evidence"]):
            value = find_contact_detail(e["evidence"])
            counts["contact_value_from_evidence"] += 1
        if spec["value"] and value is None:
            counts["entity_value_missing"] += 1
        alias = _clean(e.get("alias"))
        if alias and alias.casefold() == name.casefold():
            alias = None
        text = _clean(e["text"]) if e["type"] in ("Requirement", "Outcome") else None
        entity = {"name": name, "alias": alias, "type": e["type"], "kind": kind, "value": value,
                  "text": text, "negated": bool(e["negated"]), "evidence": e["evidence"]}
        entity["is_social"] = is_social_contact(entity)
        entities.append(entity)
        type_of[name.casefold()] = e["type"]

    relations: List[Dict[str, Any]] = []
    seen = set()
    for r in raw["relations"]:
        src, dst = _clean(r["source"]) or "", _clean(r["target"]) or ""
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
        src_type, dst_type = type_of[src.casefold()], type_of[dst.casefold()]
        valid = is_valid_triple(rel, src_type, dst_type)
        if not valid:
            counts["relation_schema_violation"] += 1
        relations.append({"source": src, "relation": rel, "target": dst, "evidence": r["evidence"],
                          "source_type": src_type, "target_type": dst_type, "schema_valid": valid})
    return entities, relations, dict(counts)


def merge_chunks(parts: List[Tuple[List, List, Dict[str, int]]]) -> Tuple[List, List, Dict[str, int]]:
    """Merge per-chunk results of one unit: dedupe entities by name, relations by triple."""
    entities: List[Dict[str, Any]] = []
    by_name: Dict[str, Dict[str, Any]] = {}
    relations: List[Dict[str, Any]] = []
    seen = set()
    counts: Dict[str, int] = defaultdict(int)
    for ents, rels, cnt in parts:
        for k, v in cnt.items():
            counts[k] += v
        for e in ents:
            existing = by_name.get(e["name"].casefold())
            if existing is None:
                by_name[e["name"].casefold()] = e
                entities.append(e)
            elif not existing["alias"] and e["alias"]:
                existing["alias"] = e["alias"]
        for r in rels:
            key = (r["source"].casefold(), r["relation"], r["target"].casefold())
            if key not in seen:
                seen.add(key)
                relations.append(r)
    return entities, relations, dict(counts)


def loadable_relations(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Relations that respect the domain -> range rules; the others are not loaded."""
    return [r for r in record["relations"] if r["schema_valid"]]


def _with_domain(sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    domain_map = load_doc_domain_map()
    return [{**s, "domain": domain_map[s["doc_id"]]} for s in sections]


def select_pilot_sections(all_sections: List[Dict[str, Any]], docs_per_domain: int, seed: int) -> List[Dict[str, Any]]:
    """Every section of `docs_per_domain` whole documents per domain (same sample as pilot 2)."""
    by_doc: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for s in all_sections:
        by_doc[s["doc_id"]].append(s)
    rng = random.Random(seed)
    picked: List[Dict[str, Any]] = []
    for dom in DOMAINS:
        pool = sorted(d for d, secs in by_doc.items()
                      if secs[0]["domain"] == dom and MIN_DOC_SECTIONS <= len(secs) <= MAX_DOC_SECTIONS)
        for doc_id in rng.sample(pool, docs_per_domain):
            picked.extend(by_doc[doc_id])
    return picked


def select_table_sections(all_sections: List[Dict[str, Any]], per_domain: int, seed: int) -> List[Dict[str, Any]]:
    documents = load_documents()
    by_domain: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for s in all_sections:
        spans = documents[s["doc_id"]]["spans"]
        content_ids = s["span_ids"][1:] if s["section_title"] else s["span_ids"]
        if is_table_like([spans[i]["text_sp"] for i in content_ids]):
            by_domain[s["domain"]].append(s)
    rng = random.Random(seed)
    picked: List[Dict[str, Any]] = []
    for dom in DOMAINS:
        pool = sorted(by_domain[dom], key=lambda s: s["section_id"])
        picked.extend(rng.sample(pool, min(per_domain, len(pool))))
    return picked


def run(targets: List[Dict[str, Any]], all_sections: List[Dict[str, Any]], client: Optional[LLMClient],
        cache: ExtractionCache, workers: int = 8) -> List[Dict[str, Any]]:
    """Extract the units covering `targets`; return one record per target section."""
    plan = plan_units(all_sections)
    unit_of = {sid: u for u in plan["units"] for sid in u["member_ids"]}
    documents = load_documents()

    needed = {unit_of[s["section_id"]]["unit_id"]: unit_of[s["section_id"]]
              for s in targets if s["section_id"] in unit_of}
    jobs = [(u, i) for u in needed.values() for i in range(len(u["chunks"]))]

    def _job(job):
        unit, i = job
        try:
            raw, status = extract_chunk(client, cache, unit, i)
            return (unit["unit_id"], i), (raw, status)
        except Exception as exc:  # noqa: BLE001 - recorded per section
            return (unit["unit_id"], i), (None, f"error: {exc}")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = dict(pool.map(_job, jobs))

    records = []
    for s in targets:
        spans = documents[s["doc_id"]]["spans"]
        content_ids = s["span_ids"][1:] if s["section_title"] else s["span_ids"]
        record = {
            "section_id": s["section_id"],
            "doc_id": s["doc_id"],
            "domain": s["domain"],
            "title": s["title"],
            "heading": s["section_title"],
            "text": s["text"],
            "is_table": is_table_like([spans[i]["text_sp"] for i in content_ids]),
            "model": client.default_model if client else None,
        }
        unit = unit_of.get(s["section_id"])
        if unit is None:
            record.update({"status": "skipped", "skip_reason": plan["skipped"][s["section_id"]],
                           "entities": [], "relations": [], "postprocess": {}})
            records.append(record)
            continue
        outs = [results[(unit["unit_id"], i)] for i in range(len(unit["chunks"]))]
        errors = [st for _, st in outs if st.startswith("error")]
        record.update({"unit_id": unit["unit_id"], "n_chunks": len(unit["chunks"]),
                       "shared_with": len(unit["member_ids"]) - 1})
        if errors:
            record.update({"status": errors[0], "entities": [], "relations": [], "postprocess": {}})
        else:
            parts = [postprocess(raw) for raw, _ in outs]
            entities, relations, counts = merge_chunks(parts)
            record.update({
                "raw_n_entities": [len(raw["entities"]) for raw, _ in outs],
                "raw_n_relations": sum(len(raw["relations"]) for raw, _ in outs),
                "entities": entities,
                "relations": relations,
                "postprocess": counts,
                "status": "cached" if all(st == "cached" for _, st in outs) else "success",
            })
        records.append(record)
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--tables", action="store_true", help="is_table sections instead of whole documents")
    mode.add_argument("--regression", action="store_true", help="sections behind known pilot-1 errors")
    parser.add_argument("--docs-per-domain", type=int, default=2)
    parser.add_argument("--tables-per-domain", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    args = parser.parse_args()

    all_sections = _with_domain(load_sections())
    if args.tables:
        name, targets = "tables", select_table_sections(all_sections, args.tables_per_domain, args.seed)
    elif args.regression:
        wanted = set(REGRESSION_SECTIONS)
        name, targets = "regression", [s for s in all_sections if s["section_id"] in wanted]
    else:
        name, targets = "pilot", select_pilot_sections(all_sections, args.docs_per_domain, args.seed)
    output = args.output or DEFAULT_OUTPUTS[name]
    print(f"{name}: {len(targets)} sections from {len({s['doc_id'] for s in targets})} documents")

    records = run(targets, all_sections, LLMClient(), ExtractionCache(args.cache_dir), args.workers)

    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    statuses: Dict[str, int] = defaultdict(int)
    for r in records:
        statuses["error" if r["status"].startswith("error") else r["status"]] += 1
    n_rel = sum(len(r["relations"]) for r in records)
    n_loadable = sum(len(loadable_relations(r)) for r in records)
    print(f"Statuses: {dict(statuses)}")
    print(f"Kept {sum(len(r['entities']) for r in records)} entities, {n_rel} relations "
          f"({n_loadable} loadable, {n_rel - n_loadable} violate the schema) -> {output}")


if __name__ == "__main__":
    main()
