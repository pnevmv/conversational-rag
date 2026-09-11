"""Thin wrapper around the official neo4j driver, configured from environment variables."""
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

DEFAULT_URI = "bolt://localhost:7687"
DEFAULT_USER = "neo4j"

# (label, id property) pairs that must be unique across the graph.
UNIQUE_IDS = [
    ("Domain", "name"),
    ("Document", "doc_id"),
    ("Section", "section_id"),
    ("Span", "sp_id"),
]


class KGClient:
    """Neo4j client. Settings: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE."""

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
    ):
        self.uri = uri or os.getenv("NEO4J_URI", DEFAULT_URI)
        user = user or os.getenv("NEO4J_USER", DEFAULT_USER)
        password = password or os.getenv("NEO4J_PASSWORD")
        if not password:
            raise ValueError("NEO4J_PASSWORD not set. Add it to your .env file or environment.")
        self.database = database or os.getenv("NEO4J_DATABASE") or None
        self.driver = GraphDatabase.driver(self.uri, auth=(user, password))

    def close(self) -> None:
        self.driver.close()

    def __enter__(self) -> "KGClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def verify(self) -> None:
        self.driver.verify_connectivity()

    def run(self, query: str, **params: Any) -> List[Dict[str, Any]]:
        """Run a query and return all records as dicts."""
        records, _, _ = self.driver.execute_query(query, params, database_=self.database)
        return [r.data() for r in records]

    def ensure_constraints(self) -> None:
        for label, prop in UNIQUE_IDS:
            name = f"{label.lower()}_{prop}_unique"
            self.run(
                f"CREATE CONSTRAINT {name} IF NOT EXISTS "
                f"FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"
            )

    def label_counts(self) -> Dict[str, int]:
        rows = self.run(
            "MATCH (n) UNWIND labels(n) AS label "
            "RETURN label, count(*) AS n ORDER BY label"
        )
        return {r["label"]: r["n"] for r in rows}

    def relationship_counts(self) -> Dict[str, int]:
        rows = self.run(
            "MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS n ORDER BY type"
        )
        return {r["type"]: r["n"] for r in rows}
