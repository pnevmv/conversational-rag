"""Closed KG schema for MultiDoc2Dial (entity types, relation types, extraction JSON schema).

Derived from the pilot open extraction (experiments/kg/schema_proposal.md) and the
review decisions: Organization and Amount renames, ContactPoint added, ALTERNATIVE_TO
kept as a symmetric relation, and a cap of MAX_ENTITIES entities per extraction call.
After the whole-document pilot: the extra pairs Organization -AVAILABLE_AT-> ContactPoint
and Requirement -REQUIRES-> Document are allowed, Service has appeal/insurance/online_tool
kinds, and entities carry an optional `alias` (abbreviation or full form).
"""
import re
from typing import Any, Dict, FrozenSet, List

MAX_ENTITIES = 15

# Contact details that make a ContactPoint's `value` mandatory. MultiDoc2Dial spells phone
# numbers with spaced hyphens ("800 - 827 - 1000").
_CONTACT_DETAIL = re.compile(
    r"\d{3}\s*[-.)]\s*\d{3}\s*-\s*\d{4}"               # phone number
    r"|\b1\s*-\s*8\d{2}\b|\b8\d{2}\s*-\s*[A-Z]{3,}"     # 1-800..., 888-GIBILL
    r"|https?://|\bwww\.|\b[\w.-]+\.(?:gov|com|org|net|edu)\b"  # URL / domain
    r"|[\w.+-]+@[\w-]+\.[\w.]+"                         # email
    r"|\bP\.?\s*O\.?\s*Box\b|\b[A-Z]{2}\s+\d{5}(?:\s*-\s*\d{4})?\b",  # postal address
    re.IGNORECASE,
)


def has_contact_detail(text: str) -> bool:
    """True if the text contains a phone number, URL, email or postal address."""
    return bool(_CONTACT_DETAIL.search(text or ""))


def find_contact_detail(text: str):
    """The first phone number, URL, email or postal-address fragment in the text, or None."""
    match = _CONTACT_DETAIL.search(text or "")
    return match.group(0).strip() if match else None

# type -> definition, allowed `kind` values (empty: no kind), whether `value` is used
ENTITY_TYPES: Dict[str, Dict[str, Any]] = {
    "Service": {
        "definition": "something a citizen can apply for, receive or complete: a benefit, program, "
                      "licence, registration, loan, test, course or procedure",
        "kinds": ["benefit", "program", "licence", "registration", "loan", "test", "course",
                  "procedure", "appeal", "insurance", "online_tool", "other"],
        "value": False,
    },
    "Organization": {
        "definition": "an agency, office, school, loan servicer, dealer or other organisation that "
                      "provides, issues or decides something",
        "kinds": ["agency", "office", "school", "servicer", "other"],
        "value": False,
    },
    "Document": {
        "definition": "a form, certificate, proof, card, letter or notice",
        "kinds": [],
        "value": False,
    },
    "Requirement": {
        "definition": "a condition or obligation: an eligibility criterion, something that must be "
                      "presented or done, or a restriction",
        "kinds": [],
        "value": False,
    },
    "Amount": {
        "definition": "a monetary value or limit: a fee, tax, premium, benefit amount, or income or "
                      "earnings limit",
        "kinds": ["fee", "tax", "premium", "benefit", "limit", "other"],
        "value": True,
    },
    "TimeLimit": {
        "definition": "a deadline, duration, frequency or waiting period",
        "kinds": [],
        "value": True,
    },
    "Role": {
        "definition": "a category of person the content applies to: an applicant group, status, "
                      "relative or official",
        "kinds": [],
        "value": False,
    },
    "Outcome": {
        "definition": "a result or consequence of an action or condition",
        "kinds": [],
        "value": False,
    },
    "ContactPoint": {
        "definition": "a phone number, website, online account, office location or information page "
                      "where the citizen can get the service or more information",
        "kinds": ["phone", "website", "account", "office", "other"],
        "value": True,
    },
}

# relation -> definition, allowed source types, allowed target types
RELATION_TYPES: Dict[str, Dict[str, Any]] = {
    "REQUIRES": {
        "definition": "the source needs the target (a condition, document or prior service)",
        "source": ["Service", "Document", "Role"],
        "target": ["Requirement", "Document", "Service"],
        "extra_pairs": [("Requirement", "Document")],
    },
    "PROVIDED_BY": {
        "definition": "the source is offered, issued, set or decided by the target organisation",
        "source": ["Service", "Document", "Amount"],
        "target": ["Organization"],
    },
    "HAS_AMOUNT": {
        "definition": "the source costs, pays or is limited by the target amount",
        "source": ["Service", "Document"],
        "target": ["Amount"],
    },
    "HAS_TIME_LIMIT": {
        "definition": "the source has the target deadline, duration, frequency or waiting period",
        "source": ["Service", "Requirement", "Document"],
        "target": ["TimeLimit"],
    },
    "APPLIES_TO": {
        "definition": "the source is available to, paid to or relevant for the target",
        "source": ["Service", "Requirement", "Amount", "TimeLimit"],
        "target": ["Role", "Service"],
    },
    "LEADS_TO": {
        "definition": "the source causes or results in the target",
        "source": ["Service", "Requirement", "Outcome"],
        "target": ["Outcome", "Service"],
    },
    "EXEMPT_FROM": {
        "definition": "the source does not need, pay or fall under the target",
        "source": ["Role", "Service", "Document"],
        "target": ["Requirement", "Amount", "Service"],
    },
    "DETERMINED_BY": {
        "definition": "the source's value or outcome depends on the target",
        "source": ["Amount", "Service", "Outcome"],
        "target": ["Requirement", "Role", "Amount"],
    },
    "AVAILABLE_AT": {
        "definition": "the source can be obtained, done or looked up at the target",
        "source": ["Service", "Document"],
        "target": ["ContactPoint", "Organization"],
        "extra_pairs": [("Organization", "ContactPoint")],
    },
    "PART_OF": {
        "definition": "the source is a component or sub-case of the target",
        "source": ["Service", "Document", "Amount"],
        "target": ["Service", "Document", "Amount"],
    },
    "ALTERNATIVE_TO": {
        "definition": "the source can be used or chosen instead of the target (symmetric)",
        "source": ["Service", "Document", "Requirement"],
        "target": ["Service", "Document", "Requirement"],
    },
}

def is_valid_triple(relation: str, source_type: str, target_type: str) -> bool:
    """Check a relation against its domain -> range rules (symmetric relations either way)."""
    spec = RELATION_TYPES[relation]

    def _ok(src: str, dst: str) -> bool:
        return (src in spec["source"] and dst in spec["target"]) or (src, dst) in spec.get("extra_pairs", [])

    if relation in SYMMETRIC_RELATIONS:
        return _ok(source_type, target_type) or _ok(target_type, source_type)
    return _ok(source_type, target_type)


# Stored in one canonical direction, queried undirected.
SYMMETRIC_RELATIONS: FrozenSet[str] = frozenset({"ALTERNATIVE_TO"})


def _nullable(type_: str) -> Dict[str, Any]:
    return {"type": [type_, "null"]}


def extraction_json_schema() -> Dict[str, Any]:
    """Strict JSON schema for one section's extraction output."""
    entity = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "alias": _nullable("string"),
            "type": {"type": "string", "enum": list(ENTITY_TYPES)},
            "kind": _nullable("string"),
            "value": _nullable("string"),
            "text": _nullable("string"),
            "negated": {"type": "boolean"},
            "evidence": {"type": "string"},
        },
        "required": ["name", "alias", "type", "kind", "value", "text", "negated", "evidence"],
        "additionalProperties": False,
    }
    relation = {
        "type": "object",
        "properties": {
            "source": {"type": "string"},
            "relation": {"type": "string", "enum": list(RELATION_TYPES)},
            "target": {"type": "string"},
            "evidence": {"type": "string"},
        },
        "required": ["source", "relation", "target", "evidence"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "entities": {"type": "array", "maxItems": MAX_ENTITIES, "items": entity},
            "relations": {"type": "array", "items": relation},
        },
        "required": ["entities", "relations"],
        "additionalProperties": False,
    }


def schema_prompt_block() -> str:
    """Human-readable schema description for the extraction prompt."""
    lines: List[str] = ["Entity types:"]
    for name, spec in ENTITY_TYPES.items():
        extra = []
        if spec["kinds"]:
            extra.append(f"kind: one of {' | '.join(spec['kinds'])}")
        if spec["value"]:
            extra.append("value: required")
        suffix = f" [{'; '.join(extra)}]" if extra else ""
        lines.append(f"- {name}: {spec['definition']}{suffix}")
    lines.append("")
    lines.append("Relation types (source type -> target type):")
    for name, spec in RELATION_TYPES.items():
        extra = "".join(f"; also {s} -> {d}" for s, d in spec.get("extra_pairs", []))
        lines.append(f"- {name}: {spec['definition']} "
                     f"({' | '.join(spec['source'])} -> {' | '.join(spec['target'])}{extra})")
    return "\n".join(lines)
