import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def get_data_dir() -> Path:
    """Return the resolved path to the dataset directory."""
    project_root = Path(__file__).resolve().parent.parent.parent
    return project_root / "data" / "multidoc2dial"


def load_documents(
    domain: Optional[str] = None, data_dir: Optional[Path] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Load MultiDoc2Dial document database.

    Args:
        domain: Optional domain filter ('dmv', 'ssa', 'va', 'studentaid').
        data_dir: Path to directory containing multidoc2dial_doc.json.

    Returns:
        Dictionary mapping doc_id to document content dict.
    """
    base_dir = data_dir or get_data_dir()
    doc_file = base_dir / "multidoc2dial_doc.json"

    if not doc_file.exists():
        raise FileNotFoundError(f"Document file not found at: {doc_file}")

    with open(doc_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    doc_data = data.get("doc_data", {})
    if domain:
        return doc_data.get(domain, {})

    # Flatten across all domains into a single dictionary
    all_docs = {}
    for dom, docs in doc_data.items():
        all_docs.update(docs)
    return all_docs


def load_dialogues(
    split: str = "validation",
    domain: Optional[str] = None,
    data_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    Load MultiDoc2Dial dialogues for a specific split.

    Args:
        split: 'train' or 'validation'.
        domain: Optional domain filter ('dmv', 'ssa', 'va', 'studentaid').
        data_dir: Path to directory containing dialogue json files.

    Returns:
        List of dialogue dictionaries.
    """
    base_dir = data_dir or get_data_dir()
    dial_file = base_dir / f"multidoc2dial_dial_{split}.json"

    if not dial_file.exists():
        raise FileNotFoundError(f"Dialogue file not found at: {dial_file}")

    with open(dial_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    dial_data = data.get("dial_data", {})
    if domain:
        dialogues = dial_data.get(domain, [])
        for dial in dialogues:
            dial["domain"] = domain
        return dialogues

    # Concatenate across all domains deterministically
    all_dialogues = []
    for dom in sorted(dial_data.keys()):
        for dial in dial_data[dom]:
            dial_copy = dict(dial)
            dial_copy["domain"] = dom
            all_dialogues.append(dial_copy)
    return all_dialogues


def _doc_to_sections(doc_id: str, doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Split a document into sections, each composed of a heading span and all
    following content spans until the next heading.

    The joined section text is what gets indexed for retrieval. span_ids records
    every individual span ID within the section so Recall@K can still be checked
    against the dataset's per-span grounding annotations.
    """
    title = doc.get("title", doc_id)
    raw_spans = doc.get("spans", {})
    sorted_spans = sorted(raw_spans.items(), key=lambda x: int(x[0]))

    heading_tags = {"h1", "h2", "h3", "h4", "h5", "h6"}
    sections: List[Dict[str, Any]] = []

    cur_heading = ""
    cur_heading_id: Optional[str] = None
    cur_texts: List[str] = []
    cur_ids: List[str] = []

    def _flush() -> None:
        if not cur_ids:
            return
        sections.append({
            "doc_id": doc_id,
            "id_sp": cur_heading_id or cur_ids[0],
            "span_ids": list(cur_ids),
            "title": title,
            "section_title": cur_heading,
            "text": " ".join(cur_texts),
        })

    for span_id, span in sorted_spans:
        tag = span.get("tag", "u")
        text = span.get("text_sp", "").strip()
        id_sp = str(span.get("id_sp", span_id))

        if tag in heading_tags:
            _flush()
            cur_heading = text
            cur_heading_id = id_sp
            cur_texts = [text] if text else []
            cur_ids = [id_sp]
        else:
            if text:
                cur_texts.append(text)
                cur_ids.append(id_sp)

    _flush()
    return sections


def load_sections(
    domain: Optional[str] = None, data_dir: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """
    Load all MultiDoc2Dial documents as a flat list of sections.

    Each section dict contains:
        doc_id, id_sp (heading span id or first content span id),
        span_ids (all individual span IDs in the section),
        title (document title), section_title (heading text), text (joined text).
    """
    docs = load_documents(domain=domain, data_dir=data_dir)
    sections: List[Dict[str, Any]] = []
    for doc_id, doc in docs.items():
        sections.extend(_doc_to_sections(doc_id, doc))
    return sections


UNANSWERABLE_PHRASE = "Unfortunately, no relevant information is found."


def _extract_domain_pairs(dial_data: Dict, domain: str, limit: int) -> List[Dict[str, Any]]:
    """Extract up to `limit` QA pairs from a single domain."""
    pairs: List[Dict[str, Any]] = []
    for dial in dial_data.get(domain, []):
        dial_id = dial["dial_id"]
        turns = dial.get("turns", [])
        prev_doc_id: Optional[str] = None
        for i in range(len(turns) - 1):
            u_turn = turns[i]
            a_turn = turns[i + 1]
            if u_turn.get("role") != "user" or a_turn.get("role") != "agent":
                continue
            q_text = u_turn.get("utterance", "").strip()
            ref_text = a_turn.get("utterance", "").strip()
            if not q_text or not ref_text:
                continue
            references = a_turn.get("references", [])
            ref_docs = [r["doc_id"] for r in references if "doc_id" in r]
            current_doc_id = ref_docs[0] if ref_docs else None
            history = [
                {"role": t["role"], "utterance": t["utterance"]}
                for t in turns[:i]
                if t.get("utterance", "").strip()
            ]
            is_doc_switch = (
                prev_doc_id is not None
                and current_doc_id is not None
                and current_doc_id != prev_doc_id
            )
            pairs.append({
                "example_id": f"{dial_id}_{u_turn['turn_id']}",
                "domain": domain,
                "dialogue_id": dial_id,
                "turn_id": u_turn["turn_id"],
                "question": q_text,
                "reference_answer": ref_text,
                "is_unanswerable": ref_text == UNANSWERABLE_PHRASE,
                "document_id": current_doc_id,
                "grounding": references,
                "dialogue_history": history,
                "is_doc_switch": is_doc_switch,
            })
            prev_doc_id = current_doc_id
            if len(pairs) >= limit:
                return pairs
    return pairs


def load_qa_pairs(
    split: str = "validation",
    domain: Optional[str] = None,
    max_examples: Optional[int] = None,
    data_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    Extract deterministic QA pairs from MultiDoc2Dial dialogues.

    When max_examples is set and no domain filter is given, examples are
    sampled round-robin across all four domains so the evaluation set is
    balanced. With a domain filter, the first max_examples pairs from that
    domain are returned.

    Each pair contains:
        example_id, domain, dialogue_id, turn_id, question, reference_answer,
        is_unanswerable, document_id, grounding, dialogue_history.
    """
    base_dir = data_dir or get_data_dir()
    dial_file = base_dir / f"multidoc2dial_dial_{split}.json"

    if not dial_file.exists():
        raise FileNotFoundError(f"Dialogue file not found at: {dial_file}")

    with open(dial_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    dial_data = data.get("dial_data", {})
    domains = [domain] if domain else sorted(dial_data.keys())

    # Single domain or no limit: flat extraction
    if len(domains) == 1 or not max_examples:
        pairs: List[Dict[str, Any]] = []
        for dom in domains:
            pairs.extend(_extract_domain_pairs(dial_data, dom, max_examples or 10_000))
        return pairs[:max_examples] if max_examples else pairs

    # Multi-domain: collect per-domain pools then round-robin interleave
    per_domain = (max_examples + len(domains) - 1) // len(domains)
    pools = {dom: _extract_domain_pairs(dial_data, dom, per_domain) for dom in domains}

    qa_pairs: List[Dict[str, Any]] = []
    i = 0
    while len(qa_pairs) < max_examples:
        added = False
        for dom in domains:
            if i < len(pools[dom]) and len(qa_pairs) < max_examples:
                qa_pairs.append(pools[dom][i])
                added = True
        if not added:
            break
        i += 1
    return qa_pairs


def load_doc_domain_map(data_dir: Optional[Path] = None) -> Dict[str, str]:
    """Return a mapping of {doc_id: domain} for all MultiDoc2Dial documents."""
    base_dir = data_dir or get_data_dir()
    with open(base_dir / "multidoc2dial_doc.json", encoding="utf-8") as f:
        data = json.load(f)
    return {
        doc_id: domain
        for domain, docs in data.get("doc_data", {}).items()
        for doc_id in docs
    }
