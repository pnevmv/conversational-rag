"""Simple post-filters applied to v2.1 extractions.

Removes opening hours typed as TimeLimit, staff typed as Role and short UI texts
("sign in", "learn more"), and flips PART_OF when one entity is the source of several
PART_OF relations in a section. Every change is logged in the record.
"""
import re
from collections import Counter
from typing import Any, Dict, List, Tuple

from src.kg.schema import is_valid_triple

UI_MAX_WORDS = 4

_OPENING_HOURS = re.compile(
    r"24\s*/\s*7|\bhours? a day\b|\bdays? a week\b|\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)s?\b"
    r"|\bweekdays?\b|\bbusiness hours\b|\b\d{1,2}(:\d{2})?\s*[ap]\.?\s?m\.?\s*(to|-|until)\s*\d{1,2}(:\d{2})?\s*[ap]\.?\s?m\.?",
    re.IGNORECASE,
)
_STAFF = re.compile(
    r"\b(counsel+ors?|social workers?|program managers?|staff( members?)?|representatives?)\b", re.IGNORECASE)
_UI = re.compile(
    r"^(sign (in|up)|log ?in|create (an |your )?account|learn more|read more|find out more|continue|"
    r"click( here)?|download|contact us|chat online)\b",
    re.IGNORECASE,
)
_UI_REQUEST = re.compile(r"^Request( [A-Z][\w-]*)*$")  # Title Case button label


def _norm(text: str) -> str:
    return " ".join((text or "").split())


def is_opening_hours(entity: Dict[str, Any]) -> bool:
    return entity["type"] == "TimeLimit" and any(_OPENING_HOURS.search(entity.get(f) or "") for f in ("name", "value"))


def is_staff_role(entity: Dict[str, Any]) -> bool:
    return entity["type"] == "Role" and bool(_STAFF.search(entity["name"]))


def is_ui_text(entity: Dict[str, Any]) -> bool:
    name = _norm(entity["name"])
    return (bool(_UI.match(name)) or bool(_UI_REQUEST.match(name))) and len(name.split()) <= UI_MAX_WORDS


def apply(entities: List[Dict[str, Any]], relations: List[Dict[str, Any]]
          ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return (entities, relations, log) after the filters; log lists every removal/change."""
    log: List[Dict[str, Any]] = []
    kept, dropped = [], set()
    for e in entities:
        reason = ("opening_hours" if is_opening_hours(e) else "staff_role" if is_staff_role(e)
                  else "ui_text" if is_ui_text(e) else None)
        if reason:
            dropped.add(e["name"].casefold())
            log.append({"action": "drop_entity", "reason": reason, "name": e["name"], "type": e["type"]})
        else:
            kept.append(e)

    rels = []
    for r in relations:
        hit = {r["source"].casefold(), r["target"].casefold()} & dropped
        if hit:
            log.append({"action": "drop_relation", "reason": "endpoint_removed", "source": r["source"],
                        "relation": r["relation"], "target": r["target"]})
        else:
            rels.append(r)

    part_sources = Counter(r["source"].casefold() for r in rels if r["relation"] == "PART_OF")
    parents = {s for s, n in part_sources.items() if n >= 2}
    fixed = []
    for r in rels:
        if r["relation"] == "PART_OF" and r["source"].casefold() in parents:
            flipped = {**r, "source": r["target"], "target": r["source"],
                       "source_type": r["target_type"], "target_type": r["source_type"]}
            flipped["schema_valid"] = is_valid_triple("PART_OF", flipped["source_type"], flipped["target_type"])
            log.append({"action": "flip_relation", "reason": "part_of_direction", "source": r["source"],
                        "relation": "PART_OF", "target": r["target"]})
            fixed.append(flipped)
        else:
            fixed.append(r)
    # Flipping can create a duplicate of an existing triple.
    seen, out = set(), []
    for r in fixed:
        key = (r["source"].casefold(), r["relation"], r["target"].casefold())
        if key not in seen:
            seen.add(key)
            out.append(r)
    return kept, out, log
