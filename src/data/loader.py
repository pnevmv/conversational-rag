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


def load_qa_pairs(
    split: str = "validation",
    domain: Optional[str] = None,
    max_examples: Optional[int] = None,
    data_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    Extract deterministic QA pairs from MultiDoc2Dial dialogues.

    Each pair represents a user question followed by the ground-truth agent response.

    Args:
        split: 'train' or 'validation'.
        domain: Optional domain filter ('dmv', 'ssa', 'va', 'studentaid').
        max_examples: Maximum number of QA pairs to return.
        data_dir: Path to directory containing dialogue files.

    Returns:
        List of dictionaries with keys:
            - example_id (str)
            - domain (str)
            - dialogue_id (str)
            - turn_id (int)
            - question (str)
            - reference_answer (str)
            - document_id (Optional[str])
            - grounding (List[Dict])
    """
    base_dir = data_dir or get_data_dir()
    dial_file = base_dir / f"multidoc2dial_dial_{split}.json"

    if not dial_file.exists():
        raise FileNotFoundError(f"Dialogue file not found at: {dial_file}")

    with open(dial_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    dial_data = data.get("dial_data", {})
    domains_to_process = [domain] if domain else sorted(dial_data.keys())

    qa_pairs: List[Dict[str, Any]] = []

    for dom in domains_to_process:
        dialogues = dial_data.get(dom, [])
        for dial in dialogues:
            dial_id = dial["dial_id"]
            turns = dial.get("turns", [])
            for i in range(len(turns) - 1):
                u_turn = turns[i]
                a_turn = turns[i + 1]

                if u_turn.get("role") == "user" and a_turn.get("role") == "agent":
                    q_text = u_turn.get("utterance", "").strip()
                    ref_text = a_turn.get("utterance", "").strip()

                    if q_text and ref_text:
                        references = a_turn.get("references", [])
                        ref_docs = [
                            r["doc_id"] for r in references if "doc_id" in r
                        ]

                        qa_pairs.append(
                            {
                                "example_id": f"{dial_id}_{u_turn['turn_id']}",
                                "domain": dom,
                                "dialogue_id": dial_id,
                                "turn_id": u_turn["turn_id"],
                                "question": q_text,
                                "reference_answer": ref_text,
                                "document_id": ref_docs[0] if ref_docs else None,
                                "grounding": references,
                            }
                        )

                        if max_examples and len(qa_pairs) >= max_examples:
                            return qa_pairs

    return qa_pairs
