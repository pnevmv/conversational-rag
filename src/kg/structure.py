"""Structural layer of the knowledge graph (no LLM).

Loads the MultiDoc2Dial corpus into Neo4j as

    (:Domain {name})-[:HAS_DOCUMENT]->(:Document {doc_id, title, domain})
    (:Document)-[:HAS_SECTION]->(:Section {section_id, heading, text, order})
    (:Section)-[:HAS_SPAN]->(:Span {sp_id, text})
    (:Section)-[:NEXT]->(:Section)          # document order

Section ids match the RAG index (src.data.loader.make_section_id), and span ids
use the same "<doc_id>::<id_sp>" form so dataset grounding annotations map
directly onto Span nodes. All writes MERGE on ids, so re-running is idempotent.

Usage:
    python -m src.kg.structure
"""
from typing import Any, Dict, Iterable, List

from src.data.loader import (
    load_doc_domain_map,
    load_documents,
    load_sections,
    make_section_id,
)
from src.kg.client import KGClient

BATCH_SIZE = 1000


def _batches(rows: List[Dict[str, Any]], size: int = BATCH_SIZE) -> Iterable[List[Dict[str, Any]]]:
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


def build_rows() -> Dict[str, List[Dict[str, Any]]]:
    """Build node and relationship rows from the corpus, in document order."""
    domain_map = load_doc_domain_map()
    documents = load_documents()
    sections = load_sections()

    docs = [
        {"doc_id": doc_id, "title": doc.get("title", doc_id), "domain": domain_map[doc_id]}
        for doc_id, doc in documents.items()
    ]

    section_rows, span_rows, next_rows = [], [], []
    order_in_doc: Dict[str, int] = {}
    prev_in_doc: Dict[str, str] = {}
    for s in sections:  # load_sections yields each document's sections in span order
        doc_id = s["doc_id"]
        order = order_in_doc.get(doc_id, 0)
        order_in_doc[doc_id] = order + 1
        section_rows.append({
            "section_id": s["section_id"],
            "doc_id": doc_id,
            "heading": s["section_title"],
            "text": s["text"],
            "order": order,
        })
        if doc_id in prev_in_doc:
            next_rows.append({"src": prev_in_doc[doc_id], "dst": s["section_id"]})
        prev_in_doc[doc_id] = s["section_id"]

        raw_spans = documents[doc_id]["spans"]
        for id_sp in s["span_ids"]:
            span_rows.append({
                "sp_id": make_section_id(doc_id, id_sp),
                "section_id": s["section_id"],
                "text": raw_spans[id_sp]["text_sp"].strip(),
            })

    return {"documents": docs, "sections": section_rows, "spans": span_rows, "next": next_rows}


def load_structure(client: KGClient) -> None:
    rows = build_rows()
    client.ensure_constraints()

    for batch in _batches(rows["documents"]):
        client.run(
            """
            UNWIND $rows AS row
            MERGE (dom:Domain {name: row.domain})
            MERGE (d:Document {doc_id: row.doc_id})
            SET d.title = row.title, d.domain = row.domain
            MERGE (dom)-[:HAS_DOCUMENT]->(d)
            """,
            rows=batch,
        )

    for batch in _batches(rows["sections"]):
        client.run(
            """
            UNWIND $rows AS row
            MATCH (d:Document {doc_id: row.doc_id})
            MERGE (s:Section {section_id: row.section_id})
            SET s.heading = row.heading, s.text = row.text, s.order = row.order
            MERGE (d)-[:HAS_SECTION]->(s)
            """,
            rows=batch,
        )

    for batch in _batches(rows["spans"]):
        client.run(
            """
            UNWIND $rows AS row
            MATCH (s:Section {section_id: row.section_id})
            MERGE (sp:Span {sp_id: row.sp_id})
            SET sp.text = row.text
            MERGE (s)-[:HAS_SPAN]->(sp)
            """,
            rows=batch,
        )

    for batch in _batches(rows["next"]):
        client.run(
            """
            UNWIND $rows AS row
            MATCH (a:Section {section_id: row.src}), (b:Section {section_id: row.dst})
            MERGE (a)-[:NEXT]->(b)
            """,
            rows=batch,
        )


def main() -> None:
    with KGClient() as client:
        client.verify()
        print(f"Connected to {client.uri}")
        load_structure(client)

        print("\nNode counts by label:")
        for label, n in client.label_counts().items():
            print(f"  {label:<10} {n:>7,}")
        print("\nRelationship counts by type:")
        for rel, n in client.relationship_counts().items():
            print(f"  {rel:<14} {n:>7,}")


if __name__ == "__main__":
    main()
