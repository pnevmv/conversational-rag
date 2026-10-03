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

Prompt versions (`--prompt-version`, part of the cache key, so both can be re-run):
    v1  the prompt used for the pilots and the v1 annotation
    v2  stricter rules for the error patterns of the v1 annotation (UI text, REQUIRES overuse,
        self-relations, places as Role, opening hours as TimeLimit, documents as Service,
        negation) and guidance for ALTERNATIVE_TO, HAS_AMOUNT and PART_OF, with three worked
        examples from documents outside the pilot
    v2.1 v2 plus contact-point extraction (phone, TTY, offices, online accounts as
        AVAILABLE_AT ContactPoints) and worked examples for contact points and taxes/fees;
        its output goes through the deterministic post-filters of src.kg.postfilter

Modes (nothing is written to Neo4j):
    python -m src.kg.extract_closed                      # whole-document pilot (8 docs)
    python -m src.kg.extract_closed --annotated          # the 3 annotated pilot documents
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
from src.kg import extract as extract_module
from src.kg.extract import DEFAULT_CACHE_DIR, DOMAINS, PROJECT_ROOT, ContentFilterError, ExtractionCache, _call_llm
from src.kg import postfilter
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
    "annotated": KG_DIR / "annotated_extraction.jsonl",
    "all": KG_DIR / "full_extraction.jsonl",
}
# The 3 pilot documents annotated for precision and recall (one per domain: DMV, SSA, VA).
ANNOTATION_DOCS = [
    "Register a leased vehicle#1_0",
    "Appeal A Decision | Social Security Administration#2_0",
    "VA Housing Assistance | Veterans Affairs#1_0",
]
# Most deterministic sampling the deployment offers (pilot3_report.md, section 8): it is a
# reasoning model; temperature is accepted only with reasoning effort "none", and `seed` is
# not supported. Part of the cache key, so changing it re-runs the extraction.
CALL_PARAMS: Dict[str, Any] = {"reasoning": {"effort": "none"}, "temperature": 0}
# Bounds a runaway response (e.g. a content-filter refusal repeated until the timeout); the
# average extraction output is ~1,000 tokens. Not part of the cache key.
MAX_OUTPUT_TOKENS = 6000
# Cached marker for chunks the provider's content filter blocks (false positives such as
# "escort driver certification"): recorded as an empty extraction, never re-requested.
CONTENT_FILTER_MARKER = {"entities": [], "relations": [], "content_filter": True}
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


CLOSED_PROMPT_V2 = """You are building a knowledge graph of U.S. government services from official web pages.

Extract entities and relations from the section below, using ONLY the types listed.

{schema}

What to extract:
- Extract only facts the section states; do not add background knowledge.
- Do NOT extract navigation or interface text as entities: link labels and calls to action ("learn more", "find out more", "sign in", "download", "find a test location now", "apply online", "visit our website"), button names, page titles and question headings.
- Forms, cards, licences, permits, IDs, letters and certificates are always Document, never Service. Applying for or renewing them is the Service.
- Role is a kind of person. Places (counties, cities, states, countries) are never a Role: leave them out, or keep them inside the text of a Requirement.
- TimeLimit is a deadline or a validity period. Opening hours, processing times and delivery times are not TimeLimits: skip them (opening hours can go in the value of a ContactPoint).

Relations:
- REQUIRES only when the text states a precondition for the source: "must", "need to", "required", "have to", "bring", "submit", "present", "show". Never for things that are only related, mentioned, reviewed by an agency, or merely described.
- Polarity: when the text says something is NOT needed or does not apply ("you do not need X", "X is not required", "does not mean"), never write REQUIRES X. Use EXEMPT_FROM if a role or service is exempted from it, otherwise write no relation.
- Never relate two names of the same thing: source and target must be different things, not the same service or document written two ways.
- ALTERNATIVE_TO: for an "X or Y (or Z)" list of interchangeable documents or options, link the first item to each of the others (X ALTERNATIVE_TO Y, X ALTERNATIVE_TO Z).
- HAS_AMOUNT: every fee, tax, premium or payment that a service or document carries, as an Amount with "kind" (fee, tax, premium, benefit, limit) and "value" when the text gives it.
- PART_OF: levels, stages or steps of a procedure: each stage PART_OF the procedure.
- "source" and "target" must be the exact "name" of an extracted entity and respect the listed source -> target types.

Fields:
- "name": the shortest noun phrase that names the entity, in the text's own wording (no CamelCase, no invented labels).
- "alias": when the text gives both a full name and an abbreviation ("Department of Motor Vehicles (DMV)"), the full name goes in "name" and the abbreviation in "alias"; otherwise null.
- "kind": one of the listed kinds for Service, Organization, Amount and ContactPoint; null for other types.
- "value": the exact amount, period or contact detail as written ("$25.00", "within 30 days", "800-827-1000") for Amount, TimeLimit and ContactPoint; null for other types or when the text gives none. For a ContactPoint whose evidence contains a phone number, postal address, email or URL, "value" is REQUIRED.
- "text": for Requirement and Outcome, the full condition or consequence copied from the text; null otherwise.
- "negated": true only when the text states the opposite; otherwise false.
- "evidence": ONE contiguous quote copied verbatim from the section text (at most ~25 words), never fragments joined with "...".
- Extract at most {max_entities} entities; for long lists keep the ones most useful for a citizen's questions.
- If the section states nothing extractable, return empty lists.

Worked examples (from other pages; fields not shown are null, "negated" is false):

{examples}

Now the section to extract.

Domain: {domain}
Document title: {title}
Section heading: {heading}
{text_label}:
\"\"\"
{text}
\"\"\"
"""

# Worked examples for prompt v2, taken from documents outside the 8 pilot documents so the
# evaluation on the annotated pilot documents is not contaminated. Each evidence quote is
# checked against its section text by tests/test_kg_extraction.py.
FEW_SHOT_V2: List[Dict[str, Any]] = [
    {
        "section_id": "Get A Veteran Health Identification Card (VHIC) | Veterans Affairs#1_0::22",
        "domain": "va",
        "entities": [
            {"name": "getting your picture taken", "type": "Service", "kind": "procedure",
             "evidence": "When you get your picture taken You ll need to show a current form of primary identification."},
            {"name": "current form of primary identification", "type": "Requirement",
             "text": "You ll need to show a current form of primary identification.",
             "evidence": "You ll need to show a current form of primary identification."},
            {"name": "State-issued driver's license", "type": "Document",
             "evidence": "State - issued driver s license , or U.S. passport or passport card"},
            {"name": "U.S. passport", "type": "Document",
             "evidence": "State - issued driver s license , or U.S. passport or passport card"},
            {"name": "passport card", "type": "Document",
             "evidence": "State - issued driver s license , or U.S. passport or passport card"},
            {"name": "other government ID", "type": "Document",
             "evidence": "Other government ID issued by a federal, state, or local government agency"},
            {"name": "document to confirm your address", "type": "Requirement",
             "text": "If it doesn t also show your address , you ll need to bring a separate document to confirm your address.",
             "evidence": "If it doesn t also show your address , you ll need to bring a separate document to confirm your address."},
            {"name": "electric bill", "type": "Document",
             "evidence": "This may include your electric bill, cable bill, voter registration card, or another mailed document."},
            {"name": "cable bill", "type": "Document",
             "evidence": "This may include your electric bill, cable bill, voter registration card, or another mailed document."},
            {"name": "voter registration card", "type": "Document",
             "evidence": "This may include your electric bill, cable bill, voter registration card, or another mailed document."},
        ],
        "relations": [
            ("getting your picture taken", "REQUIRES", "current form of primary identification",
             "You ll need to show a current form of primary identification."),
            ("getting your picture taken", "REQUIRES", "document to confirm your address",
             "you ll need to bring a separate document to confirm your address."),
            ("State-issued driver's license", "ALTERNATIVE_TO", "U.S. passport",
             "State - issued driver s license , or U.S. passport or passport card"),
            ("State-issued driver's license", "ALTERNATIVE_TO", "passport card",
             "State - issued driver s license , or U.S. passport or passport card"),
            ("State-issued driver's license", "ALTERNATIVE_TO", "other government ID",
             "or Other government ID issued by a federal, state, or local government agency"),
            ("electric bill", "ALTERNATIVE_TO", "cable bill",
             "This may include your electric bill, cable bill, voter registration card, or another mailed document."),
            ("electric bill", "ALTERNATIVE_TO", "voter registration card",
             "This may include your electric bill, cable bill, voter registration card, or another mailed document."),
        ],
        "note": None,
    },
    {
        "section_id": "Appeal a TVB ticket conviction#1_0::2",
        "domain": "dmv",
        "entities": [
            {"name": "appeal of a Traffic Violations Bureau conviction", "type": "Service", "kind": "appeal",
             "evidence": "You can appeal a Traffic Violations Bureau (TVB) conviction online or by mail"},
            {"name": "Traffic Violations Bureau", "alias": "TVB", "type": "Organization", "kind": "agency",
             "evidence": "You can appeal a Traffic Violations Bureau (TVB) conviction online or by mail"},
            {"name": "within 30 days of the date of conviction", "type": "TimeLimit",
             "value": "within 30 days of the date of conviction",
             "evidence": "you must file your appeal within 30 days of the date of conviction"},
            {"name": "appeal fee", "type": "Amount", "kind": "fee", "value": "$10",
             "evidence": "you must pay a $10 non refundable appeal fee for each conviction appealed"},
            {"name": "DMV Appeals Board", "type": "Organization", "kind": "agency",
             "evidence": "The DMV Appeals Board must determine that your appeal meets legal requirements."},
        ],
        "relations": [
            ("appeal of a Traffic Violations Bureau conviction", "HAS_TIME_LIMIT",
             "within 30 days of the date of conviction",
             "you must file your appeal within 30 days of the date of conviction"),
            ("appeal of a Traffic Violations Bureau conviction", "HAS_AMOUNT", "appeal fee",
             "you must pay a $10 non refundable appeal fee for each conviction appealed"),
            ("appeal of a Traffic Violations Bureau conviction", "PROVIDED_BY", "DMV Appeals Board",
             "The DMV Appeals Board must determine that your appeal meets legal requirements."),
        ],
        "note": "No relation for \"does not mean that your appeal has been accepted\" (a negative statement).",
    },
    {
        "section_id": "How to renew a license#1_0::29",
        "domain": "dmv",
        "entities": [
            {"name": "renew online", "type": "Service", "kind": "procedure",
             "evidence": "Follow these 3 steps to renew online and keep your current document type"},
            {"name": "eye test", "type": "Service", "kind": "test",
             "evidence": "Step 1: Pass an eye test by an approved provider"},
            {"name": "paper report", "type": "Document",
             "evidence": "or have a professional complete a paper report"},
            {"name": "print a temporary license", "type": "Service", "kind": "procedure",
             "evidence": "Step 3 : Download and print a temporary license in PDF format to use until your new license arrives."},
        ],
        "relations": [
            ("eye test", "PART_OF", "renew online", "Step 1: Pass an eye test by an approved provider"),
            ("print a temporary license", "PART_OF", "renew online",
             "Step 3 : Download and print a temporary license in PDF format to use until your new license arrives."),
            ("eye test", "ALTERNATIVE_TO", "paper report",
             "Pass an eye test by an approved provider , like a pharmacy find a test location now [4], or have a professional complete a paper report."),
        ],
        "note": "Skipped: \"find a test location now\" and \"Renew license online\" (link texts); \"Step 2: Renew online\" "
                "(the procedure itself, so no self-relation); \"within 10 business days\" (a delivery time, not a TimeLimit).",
    },
]


# v2.1: restores contact points (v2 lost most AVAILABLE_AT facts) and shows taxes/fees.
CLOSED_PROMPT_V21 = CLOSED_PROMPT_V2.replace(
    """- TimeLimit is a deadline or a validity period.""",
    """- Contact points are entities: phone numbers (including TTY), offices and addresses, and named online accounts or portals where the citizen can get the service or help. Extract them as ContactPoint with "value", even though link labels such as "learn more" are not entities.
- TimeLimit is a deadline or a validity period.""",
).replace(
    """- PART_OF: levels, stages or steps of a procedure: each stage PART_OF the procedure.""",
    """- PART_OF: levels, stages or steps of a procedure: each stage PART_OF the procedure.
- AVAILABLE_AT: from the service or organization the sentence is about to each ContactPoint where it can be done or asked about.""",
)
assert CLOSED_PROMPT_V21 != CLOSED_PROMPT_V2

FEW_SHOT_V21: List[Dict[str, Any]] = FEW_SHOT_V2 + [
    {
        "section_id": "Agent Orange Exposure In Vietnam Or Korea | Veterans Affairs#1_0::63",
        "domain": "va",
        "entities": [
            {"name": "help filing a claim", "type": "Service", "kind": "procedure",
             "evidence": "What if I need help filing my claim? You can get help from us in one of these ways"},
            {"name": "800 - 827 - 1000", "type": "ContactPoint", "kind": "phone", "value": "800 - 827 - 1000",
             "evidence": "Call 800 - 827 - 1000 or TTY 800 - 877 - 8339"},
            {"name": "TTY 800 - 877 - 8339", "type": "ContactPoint", "kind": "phone", "value": "800 - 877 - 8339",
             "evidence": "Call 800 - 827 - 1000 or TTY 800 - 877 - 8339"},
            {"name": "nearest VA regional benefit office", "type": "ContactPoint", "kind": "office",
             "evidence": "Go to your nearest VA regional benefit office"},
        ],
        "relations": [
            ("help filing a claim", "AVAILABLE_AT", "800 - 827 - 1000", "Call 800 - 827 - 1000 or TTY 800 - 877 - 8339"),
            ("help filing a claim", "AVAILABLE_AT", "TTY 800 - 877 - 8339", "Call 800 - 827 - 1000 or TTY 800 - 877 - 8339"),
            ("help filing a claim", "AVAILABLE_AT", "nearest VA regional benefit office",
             "Go to your nearest VA regional benefit office"),
        ],
        "note": "Skipped: \"a trained professional trusted to help with VA-related claims\" (a helper, not a Role of the citizen).",
    },
    {
        "section_id": "Passenger vehicle registration fees, use taxes and supplemental fees#3_0::19",
        "domain": "dmv",
        "entities": [
            {"name": "passenger vehicle original registrations and renewals", "type": "Service", "kind": "registration",
             "evidence": "All passenger vehicle original registrations and renewals"},
            {"name": "vehicle use tax", "type": "Amount", "kind": "tax", "value": "$30 for two years",
             "evidence": "Vehicle use tax - $30 for two years $15 per year"},
            {"name": "Supplemental MCTD fee", "type": "Amount", "kind": "fee", "value": "$50 for two years",
             "evidence": "Supplemental MCTD fee - $50 for two years $25 per year"},
        ],
        "relations": [
            ("passenger vehicle original registrations and renewals", "HAS_AMOUNT", "vehicle use tax",
             "Vehicle use tax - $30 for two years $15 per year"),
            ("passenger vehicle original registrations and renewals", "HAS_AMOUNT", "Supplemental MCTD fee",
             "Supplemental MCTD fee - $50 for two years $25 per year"),
        ],
        "note": "Skipped: the New York City counties in the heading (places, not Roles).",
    },
]


def render_few_shot(sections_by_id: Dict[str, Dict[str, Any]], examples: Optional[List[Dict[str, Any]]] = None) -> str:
    blocks = []
    for n, ex in enumerate(examples or FEW_SHOT_V2, start=1):
        sec = sections_by_id[ex["section_id"]]
        ents = "\n".join("  " + json.dumps({k: v for k, v in e.items()}, ensure_ascii=False) for e in ex["entities"])
        rels = "\n".join("  " + json.dumps({"source": a, "relation": r, "target": b, "evidence": ev}, ensure_ascii=False)
                         for a, r, b, ev in ex["relations"])
        block = (f"Example {n}\nDomain: {ex['domain']}\nDocument title: {sec['title']}\n"
                 f"Section heading: {sec['section_title'] or '(none)'}\nSection text:\n\"\"\"\n{sec['text']}\n\"\"\"\n"
                 f"entities:\n{ents}\nrelations:\n{rels}")
        if ex["note"]:
            block += f"\n{ex['note']}"
        blocks.append(block)
    return "\n\n".join(blocks)


_FEW_SHOT_CACHE: Dict[str, str] = {}


def few_shot(version: str = "v2") -> str:
    if version not in _FEW_SHOT_CACHE:
        sections = {s["section_id"]: s for s in load_sections()}
        _FEW_SHOT_CACHE[version] = render_few_shot(sections, FEW_SHOT_V21 if version == "v2.1" else FEW_SHOT_V2)
    return _FEW_SHOT_CACHE[version]


def few_shot_v2() -> str:
    return few_shot("v2")


PROMPT_VERSIONS = ("v1", "v2", "v2.1")
POSTFILTER_VERSIONS = {"v2.1"}


class CacheMiss(LookupError):
    """Raised when a cache-only extraction (client=None) has no cached output."""


def build_prompt(section: Dict[str, Any], chunk: str, index: int, n_chunks: int, version: str = "v1") -> str:
    label = "Section text" if n_chunks == 1 else f"Section text (part {index + 1} of {n_chunks})"
    if version in ("v2", "v2.1"):
        template = CLOSED_PROMPT_V21 if version == "v2.1" else CLOSED_PROMPT_V2
        return template.format(
            schema=schema_prompt_block("v2"),
            max_entities=MAX_ENTITIES,
            examples=few_shot(version),
            domain=section["domain"],
            title=section["title"],
            heading=section["section_title"] or "(none)",
            text_label=label,
            text=chunk,
        )
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
                  max_retries: int = 5, version: str = "v1") -> Tuple[Dict[str, Any], str]:
    """Return (raw extraction, status) for one chunk; client=None reads the cache only."""
    prompt = build_prompt(unit["representative"], unit["chunks"][index], index, len(unit["chunks"]), version)
    prompt_hash = hashlib.sha256(
        f"{prompt}\x00{json.dumps(CALL_PARAMS, sort_keys=True)}".encode("utf-8")).hexdigest()
    key = f"{unit['unit_id']}::chunk{index}"
    raw = cache.get(key, prompt_hash)
    if raw is not None:
        try:
            return json.loads(raw), "cached"
        except json.JSONDecodeError:
            pass  # an empty or truncated response was cached (e.g. a dropped connection): call again
    if client is None:
        raise CacheMiss(key)
    json_attempts = 2  # an empty/invalid response is asked again once (each call has its own retries)
    for attempt in range(json_attempts):
        try:
            raw = _call_llm(client, prompt, max_retries, schema=extraction_json_schema(),
                            schema_name="kg_closed_extraction", params=CALL_PARAMS,
                            max_output_tokens=MAX_OUTPUT_TOKENS)
        except ContentFilterError:
            cache.put(key, prompt_hash, json.dumps(CONTENT_FILTER_MARKER))
            return dict(CONTENT_FILTER_MARKER), "content_filter"
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            if attempt == json_attempts - 1:
                raise
            continue
        cache.put(key, prompt_hash, raw)  # only valid JSON is cached
        return parsed, "success"
    raise RuntimeError("unreachable")


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
        cache: ExtractionCache, workers: int = 8, version: str = "v1") -> List[Dict[str, Any]]:
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
            raw, status = extract_chunk(client, cache, unit, i, version=version)
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
            "prompt_version": version,
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
            if version in POSTFILTER_VERSIONS:
                entities, relations, record["postfilter"] = postfilter.apply(entities, relations)
            record.update({
                "raw_n_entities": [len(raw["entities"]) for raw, _ in outs],
                "raw_n_relations": sum(len(raw["relations"]) for raw, _ in outs),
                "entities": entities,
                "relations": relations,
                "postprocess": counts,
                "status": ("content_filter" if any(raw.get("content_filter") for raw, _ in outs)
                           else "cached" if all(st == "cached" for _, st in outs) else "success"),
            })
        records.append(record)
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--tables", action="store_true", help="is_table sections instead of whole documents")
    mode.add_argument("--regression", action="store_true", help="sections behind known pilot-1 errors")
    mode.add_argument("--annotated", action="store_true", help="the 3 annotated pilot documents")
    mode.add_argument("--all", action="store_true", help="every section of the corpus (full build)")
    parser.add_argument("--usage-log", type=Path, default=None, help="append per-call token usage (JSONL)")
    parser.add_argument("--prompt-version", choices=PROMPT_VERSIONS, default="v1")
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
    elif args.annotated:
        name, targets = "annotated", [s for s in all_sections if s["doc_id"] in ANNOTATION_DOCS]
    elif args.all:
        name, targets = "all", all_sections
    else:
        name, targets = "pilot", select_pilot_sections(all_sections, args.docs_per_domain, args.seed)
    output = args.output or DEFAULT_OUTPUTS[name]
    extract_module.USAGE_LOG = args.usage_log
    print(f"{name}: {len(targets)} sections from {len({s['doc_id'] for s in targets})} documents, "
          f"prompt {args.prompt_version}")

    records = run(targets, all_sections, LLMClient(), ExtractionCache(args.cache_dir), args.workers,
                  version=args.prompt_version)

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
