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
        return dial_data.get(domain, [])

    # Concatenate across all domains
    all_dialogues = []
    for dom, dialogues in dial_data.items():
        all_dialogues.extend(dialogues)
    return all_dialogues
