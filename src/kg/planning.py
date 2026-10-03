"""Extraction planning: which sections are extracted, deduplicated or chunked.

Rules (review decisions after the whole-document pilot):
  - sections shorter than MIN_CHARS are skipped (page boilerplate such as
    "Related PDFs:");
  - a text that occurs in BOILERPLATE_MIN_DOCS or more documents is boilerplate
    (e.g. VA "Call us" footers): skipped and flagged is_boilerplate;
  - any other repeated text is extracted once (an extraction *unit*) and the result
    is attached to every section where the text occurs;
  - a unit longer than CHUNK_MAX_CHARS is split into chunks at sentence boundaries,
    with the entity cap applied per chunk.
"""
import math
import re
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Set

MIN_CHARS = 40
BOILERPLATE_MIN_DOCS = 10
CHUNK_MAX_CHARS = 1500

# A sentence ends with . ! or ? (MultiDoc2Dial often has a space before it) and the next
# one starts with an upper-case letter, digit, quote or bracket.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"“(\[])")


def normalize_text(text: str) -> str:
    return " ".join(text.split())


def text_document_counts(sections: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    """Number of distinct documents in which each normalised section text occurs."""
    docs: Dict[str, Set[str]] = defaultdict(set)
    for s in sections:
        docs[normalize_text(s["text"])].add(s["doc_id"])
    return {t: len(d) for t, d in docs.items()}


def is_boilerplate(section: Dict[str, Any], doc_counts: Dict[str, int]) -> bool:
    return doc_counts.get(normalize_text(section["text"]), 0) >= BOILERPLATE_MIN_DOCS


def split_sentences(text: str) -> List[str]:
    return [s for s in _SENTENCE_END.split(normalize_text(text)) if s]


def chunk_text(text: str, max_chars: int = CHUNK_MAX_CHARS) -> List[str]:
    """Split text into roughly equal chunks of at most ~max_chars at sentence boundaries.

    A single sentence longer than max_chars becomes its own chunk.
    """
    text = normalize_text(text)
    if len(text) <= max_chars:
        return [text]
    target = len(text) / math.ceil(len(text) / max_chars)
    chunks: List[str] = []
    current = ""
    for sentence in split_sentences(text):
        candidate = f"{current} {sentence}".strip()
        if current and len(candidate) > target and len(candidate) > len(current) + 1:
            if len(candidate) > max_chars or len(current) >= target:
                chunks.append(current)
                current = sentence
                continue
        current = candidate
    if current:
        chunks.append(current)
    return chunks


def plan_units(all_sections: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Group the corpus into extraction units.

    Returns {"units": [...], "skipped": {section_id: reason}} where each unit is
    {unit_id, representative (section dict), member_ids (sorted), chunks}. The
    representative is the member with the smallest section_id, so plans are stable.
    """
    doc_counts = text_document_counts(all_sections)
    by_text: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    skipped: Dict[str, str] = {}
    for s in all_sections:
        text = normalize_text(s["text"])
        if doc_counts[text] >= BOILERPLATE_MIN_DOCS:
            skipped[s["section_id"]] = "boilerplate"
        elif len(text) < MIN_CHARS:
            skipped[s["section_id"]] = "short"
        else:
            by_text[text].append(s)

    units = []
    for text, members in by_text.items():
        members = sorted(members, key=lambda s: s["section_id"])
        units.append({
            "unit_id": members[0]["section_id"],
            "representative": members[0],
            "member_ids": [m["section_id"] for m in members],
            "chunks": chunk_text(text),
        })
    units.sort(key=lambda u: u["unit_id"])
    return {"units": units, "skipped": skipped}
