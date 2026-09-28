"""Entity table of one KG scope, exported from Neo4j once and cached as JSON.

One row per Entity:
    entity_id, name, type, domain, domains, value, degree (typed entity relations, both
    directions), forms (entity name, names of the mentions resolved to it, their aliases),
    section_ids (sections with a mention resolved to the entity).

Linking and the KG retrievers read this table instead of querying Neo4j per question.

Usage:
    python -m src.kg_rag.graph_index --scope full          # export (overwrites the cache)
"""
import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = PROJECT_ROOT / "experiments" / "kg_rag"


def cache_path(scope: str) -> Path:
    return OUT_DIR / f"entities_{scope}.json"


def export_entities(scope: str) -> List[Dict[str, Any]]:
    from src.kg.client import KGClient

    with KGClient() as client:
        rows = client.run(
            """
            MATCH (e:Entity {scope: $scope})
            OPTIONAL MATCH (s:Section)-[:MENTIONS]->(m:Mention)-[:RESOLVES_TO]->(e)
            WITH e, collect(DISTINCT m.name) AS names, collect(DISTINCT m.alias) AS aliases,
                 collect(DISTINCT s.section_id) AS sids
            RETURN e.entity_id AS entity_id, e.name AS name, e.type AS type, e.domain AS domain,
                   e.domains AS domains, e.value AS value, names, aliases, sids,
                   COUNT { (e)-[]-(:Entity) } AS degree
            ORDER BY entity_id
            """, scope=scope)
    out = []
    for r in rows:
        forms, seen = [], set()
        for f in [r["name"], *r["names"], *r["aliases"]]:
            f = " ".join((f or "").split())
            if f and f.casefold() not in seen:
                seen.add(f.casefold())
                forms.append(f)
        out.append({"entity_id": r["entity_id"], "name": r["name"], "type": r["type"],
                    "domain": r["domain"], "domains": r["domains"] or [r["domain"]], "value": r["value"],
                    "degree": r["degree"], "forms": forms, "section_ids": sorted(r["sids"])})
    return out


def load_entities(scope: str = "full", refresh: bool = False) -> List[Dict[str, Any]]:
    path = cache_path(scope)
    if refresh or not path.exists():
        entities = export_entities(scope)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(entities, ensure_ascii=False), encoding="utf-8")
        return entities
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scope", default="full")
    args = parser.parse_args()
    entities = load_entities(args.scope, refresh=True)
    print(f"{len(entities):,} entities, {sum(len(e['forms']) for e in entities):,} surface forms "
          f"-> {cache_path(args.scope)}")


if __name__ == "__main__":
    main()
