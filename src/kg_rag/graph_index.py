"""Entity table of one KG scope, exported from Neo4j once and cached as JSON.

One row per Entity:
    entity_id, name, type, domain, domains, value, degree (typed entity relations, both
    directions), forms (entity name, names of the mentions resolved to it, their aliases),
    section_ids (sections with a mention resolved to the entity).

One row per entity relation (relations_<scope>.json):
    source, relation, target, support, section_ids, evidence (the evidence quotes of the
    mention-level relations it aggregates, with their section; either direction for the
    symmetric ALTERNATIVE_TO).

Linking and the KG retrievers read these tables instead of querying Neo4j per question.

Usage:
    python -m src.kg_rag.graph_index --scope full          # export (overwrites the caches)
"""
import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = PROJECT_ROOT / "experiments" / "kg_rag"


def cache_path(scope: str) -> Path:
    return OUT_DIR / f"entities_{scope}.json"


def relations_path(scope: str) -> Path:
    return OUT_DIR / f"relations_{scope}.json"


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


def export_relations(scope: str) -> List[Dict[str, Any]]:
    from src.kg.client import KGClient
    from src.kg.schema import SYMMETRIC_RELATIONS

    with KGClient() as client:
        rels = client.run(
            """
            MATCH (a:Entity {scope: $scope})-[r]->(b:Entity {scope: $scope})
            RETURN a.entity_id AS source, type(r) AS relation, b.entity_id AS target,
                   r.support AS support, r.section_ids AS section_ids
            ORDER BY source, relation, target
            """, scope=scope)
        evidence = client.run(
            """
            MATCH (ea:Entity {scope: $scope})<-[:RESOLVES_TO]-(ma:Mention)-[x:REL]->(mb:Mention)
                  -[:RESOLVES_TO]->(eb:Entity {scope: $scope})
            RETURN ea.entity_id AS source, x.type AS relation, eb.entity_id AS target,
                   x.evidence AS evidence, ma.section_id AS section_id
            """, scope=scope)
    quotes: Dict[tuple, List[Dict[str, str]]] = {}
    for e in evidence:
        if not e["evidence"]:
            continue
        keys = [(e["source"], e["relation"], e["target"])]
        if e["relation"] in SYMMETRIC_RELATIONS:
            keys.append((e["target"], e["relation"], e["source"]))
        for key in keys:
            bucket = quotes.setdefault(key, [])
            if all(q["text"] != e["evidence"] for q in bucket):
                bucket.append({"text": e["evidence"], "section_id": e["section_id"]})
    return [{**r, "section_ids": sorted(r["section_ids"] or []),
             "evidence": quotes.get((r["source"], r["relation"], r["target"]), [])} for r in rels]


def load_relations(scope: str = "full", refresh: bool = False) -> List[Dict[str, Any]]:
    path = relations_path(scope)
    if refresh or not path.exists():
        relations = export_relations(scope)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(relations, ensure_ascii=False), encoding="utf-8")
        return relations
    return json.loads(path.read_text(encoding="utf-8"))


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
    relations = load_relations(args.scope, refresh=True)
    print(f"{len(relations):,} relations, {sum(bool(r['evidence']) for r in relations):,} with evidence "
          f"-> {relations_path(args.scope)}")


if __name__ == "__main__":
    main()
