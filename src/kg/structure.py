"""Load the structural layer into Neo4j: Domain -> Document -> Section -> Span.

Section and span ids match the RAG index, so retrieval results and grounding annotations
map directly to graph nodes. Sections get two flags: is_table (long enumerations, a text
heuristic) and is_boilerplate (text repeated in many documents). Re-running is safe.

    python -m src.kg.structure
"""
import re
from typing import Any, Dict, Iterable, List

from src.data.loader import (
    load_doc_domain_map,
    load_documents,
    load_sections,
    make_section_id,
)
from src.kg.client import KGClient
from src.kg.planning import is_boilerplate, text_document_counts

BATCH_SIZE = 1000
ENUM_MIN_ITEMS = 6
ENUM_ITEM_MAX_WORDS = 4


def is_table_like(content_texts: List[str]) -> bool:
    """True if any span enumerates ENUM_MIN_ITEMS or more short comma/semicolon items."""
    for text in content_texts:
        items = [p for p in re.split(r"[,;]", text) if 0 < len(p.split()) <= ENUM_ITEM_MAX_WORDS]
        if len(items) >= ENUM_MIN_ITEMS:
            return True
    return False


def _batches(rows: List[Dict[str, Any]], size: int = BATCH_SIZE) -> Iterable[List[Dict[str, Any]]]:
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


def build_rows() -> Dict[str, List[Dict[str, Any]]]:
    """Build node and relationship rows from the corpus, in document order."""
    domain_map = load_doc_domain_map()
    documents = load_documents()
    sections = load_sections()
    doc_counts = text_document_counts(sections)

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
        raw_spans = documents[doc_id]["spans"]
        content_ids = s["span_ids"][1:] if s["section_title"] else s["span_ids"]
        section_rows.append({
            "section_id": s["section_id"],
            "doc_id": doc_id,
            "heading": s["section_title"],
            "text": s["text"],
            "order": order,
            "is_table": is_table_like([raw_spans[i]["text_sp"] for i in content_ids]),
            "is_boilerplate": is_boilerplate(s, doc_counts),
        })
        if doc_id in prev_in_doc:
            next_rows.append({"src": prev_in_doc[doc_id], "dst": s["section_id"]})
        prev_in_doc[doc_id] = s["section_id"]

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
            SET s.heading = row.heading, s.text = row.text, s.order = row.order,
                s.is_table = row.is_table, s.is_boilerplate = row.is_boilerplate
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
        n_table = client.run("MATCH (s:Section {is_table: true}) RETURN count(s) AS n")[0]["n"]
        n_boiler = client.run("MATCH (s:Section {is_boilerplate: true}) RETURN count(s) AS n")[0]["n"]
        print(f"\nSections flagged is_table: {n_table:,}")
        print(f"Sections flagged is_boilerplate: {n_boiler:,}")
        print("\nRelationship counts by type:")
        for rel, n in client.relationship_counts().items():
            print(f"  {rel:<14} {n:>7,}")


if __name__ == "__main__":
    main()
