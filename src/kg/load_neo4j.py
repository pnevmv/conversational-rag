"""Load the metagraph and KG layers into Neo4j for one scope.

Metagraph (one node per extracted mention, created, never merged):
    (:Section)-[:MENTIONS]->(:Mention {mention_id, name, name_normalized, type, value, kind,
                                      alias, evidence, run_id, scope, section_id})
    (:Mention)-[:REL {type, evidence}]->(:Mention)       # loadable relations only

KG layer (from the entity-resolution clusters):
    (:Mention)-[:RESOLVES_TO]->(:Entity {entity_id, name, type, domain, domains, value, kind,
                                        n_mentions, scope})
    (:Entity)-[:<RELATION> {support, section_ids}]->(:Entity)

Entity relations aggregate the mention-level relations between the resolved endpoints:
`support` is the number of mention-level relations and `section_ids` the sections they
come from. ALTERNATIVE_TO is stored once per entity pair. Relations that break the type
rules are not loaded (counted at mention level, and again at entity level, where the
resolved majority type can differ from the extracted one); relations whose two
endpoints resolve to the same entity are dropped and counted.

Idempotent: loading a scope first deletes that scope's Mention and Entity nodes (and
with them their relationships). The structural layer is never modified.

Usage:
    python -m src.kg.load_neo4j                       # pilot scope (defaults below)
    python -m src.kg.load_neo4j --scope pilot \\
        --extraction experiments/kg/pilot3_closed_extraction.jsonl \\
        --resolution experiments/kg/er_pilot_batched_mentions.jsonl --run-id pilot3_run1
"""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

from src.kg.client import KGClient
from src.kg.extract_closed import loadable_relations
from src.kg.resolve import key_of
from src.kg.schema import RELATION_TYPES, SYMMETRIC_RELATIONS, is_valid_triple

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
KG_DIR = PROJECT_ROOT / "experiments" / "kg"
DEFAULT_EXTRACTION = KG_DIR / "pilot3_closed_extraction.jsonl"
DEFAULT_RESOLUTION = KG_DIR / "er_pilot_batched_mentions.jsonl"
BATCH_SIZE = 1000


def _batches(rows: List[Dict[str, Any]]):
    for i in range(0, len(rows), BATCH_SIZE):
        yield rows[i:i + BATCH_SIZE]


def _most_common(values: List[Any]) -> Any:
    values = [v for v in values if v not in (None, "")]
    if not values:
        return None
    counts = Counter(values)
    return sorted(counts.items(), key=lambda kv: (-kv[1], -len(str(kv[0])), str(kv[0])))[0][0]


# --- row building (pure, testable without Neo4j) -----------------------------------------

def build_rows(records: List[Dict[str, Any]], resolution: Dict[str, Dict[str, Any]],
               scope: str, run_id: str) -> Dict[str, Any]:
    """Turn extraction records and an ER mention -> entity map into node/relationship rows."""
    counts: Dict[str, int] = Counter()
    mentions: List[Dict[str, Any]] = []
    mention_rels: List[Dict[str, Any]] = []
    domain_of: Dict[str, str] = {}

    for r in records:
        if r["status"] == "skipped" or r["status"].startswith("error"):
            continue
        index: Dict[str, str] = {}
        for i, e in enumerate(r["entities"]):
            mid = f"{r['section_id']}#{i}"  # same ids as src.kg.resolve.load_mentions
            index[e["name"].casefold()] = mid
            domain_of[mid] = r["domain"]
            mentions.append({
                "mention_id": mid, "section_id": r["section_id"], "name": e["name"],
                "name_normalized": key_of(e["name"]), "type": e["type"], "value": e.get("value"),
                "kind": e.get("kind"), "alias": e.get("alias"), "evidence": e["evidence"],
            })
        loadable = loadable_relations(r)
        counts["mention_relations_violating_rules"] += len(r["relations"]) - len(loadable)
        for rel in loadable:
            src, dst = index.get(rel["source"].casefold()), index.get(rel["target"].casefold())
            if src is None or dst is None:
                counts["mention_relations_unmatched"] += 1
                continue
            mention_rels.append({"src": src, "dst": dst, "type": rel["relation"],
                                 "evidence": rel["evidence"], "section_id": r["section_id"]})

    # KG layer: entities aggregated over the mentions resolved to them.
    members: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    resolves = []
    for m in mentions:
        res = resolution.get(m["mention_id"])
        if res is None:
            counts["mentions_unresolved"] += 1
            continue
        eid = f"{scope}:{res['entity_id']}"
        members[eid].append({**m, "resolved_type": res["type"], "domain": domain_of[m["mention_id"]]})
        resolves.append({"mention_id": m["mention_id"], "entity_id": eid})
    entity_of = {r["mention_id"]: r["entity_id"] for r in resolves}

    entities = []
    type_of: Dict[str, str] = {}
    for eid, ms in members.items():
        type_of[eid] = ms[0]["resolved_type"]
        domains = Counter(m["domain"] for m in ms)
        entities.append({
            "entity_id": eid, "name": _most_common([m["name"] for m in ms]), "type": type_of[eid],
            "domain": domains.most_common(1)[0][0], "domains": sorted(domains),
            "value": _most_common([m["value"] for m in ms]), "kind": _most_common([m["kind"] for m in ms]),
            "n_mentions": len(ms),
        })

    agg: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for rel in mention_rels:
        a, b = entity_of.get(rel["src"]), entity_of.get(rel["dst"])
        if a is None or b is None:
            counts["entity_relations_unresolved"] += 1
            continue
        if a == b:
            counts["entity_relations_self_loop"] += 1
            continue
        if not is_valid_triple(rel["type"], type_of[a], type_of[b]):
            counts["entity_relations_violating_rules"] += 1
            continue
        if rel["type"] in SYMMETRIC_RELATIONS and b < a:
            a, b = b, a
        key = (a, rel["type"], b)
        entry = agg.setdefault(key, {"src": a, "dst": b, "type": rel["type"], "support": 0, "section_ids": set()})
        entry["support"] += 1
        entry["section_ids"].add(rel["section_id"])
    entity_rels = [{**v, "section_ids": sorted(v["section_ids"])} for v in agg.values()]

    for m in mentions:
        m.update({"scope": scope, "run_id": run_id})
    for e in entities:
        e["scope"] = scope
    return {"mentions": mentions, "mention_rels": mention_rels, "entities": entities,
            "resolves": resolves, "entity_rels": entity_rels, "counts": dict(counts)}


def load_inputs(extraction: Path, resolution: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    records = [json.loads(line) for line in open(extraction, encoding="utf-8")]
    res = {r["mention_id"]: r for r in map(json.loads, open(resolution, encoding="utf-8"))}
    return records, res


# --- Neo4j --------------------------------------------------------------------------------

def ensure_schema(client: KGClient) -> None:
    client.ensure_constraints()
    client.run("CREATE CONSTRAINT entity_entity_id_unique IF NOT EXISTS "
               "FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE")
    client.run("CREATE INDEX mention_lookup IF NOT EXISTS FOR (m:Mention) ON (m.scope, m.run_id, m.mention_id)")
    client.run("CREATE INDEX mention_scope IF NOT EXISTS FOR (m:Mention) ON (m.scope)")
    client.run("CREATE INDEX entity_scope IF NOT EXISTS FOR (e:Entity) ON (e.scope)")


def delete_scope(client: KGClient, scope: str) -> None:
    """Remove the scope's metagraph and KG layer; structural nodes are untouched."""
    with client.driver.session(database=client.database) as session:
        session.run(
            "MATCH (n) WHERE (n:Mention OR n:Entity) AND n.scope = $scope "
            "CALL (n) { DETACH DELETE n } IN TRANSACTIONS OF 5000 ROWS",
            scope=scope,
        ).consume()


def write(client: KGClient, rows: Dict[str, Any], scope: str, run_id: str) -> None:
    for batch in _batches(rows["mentions"]):
        client.run(
            """
            UNWIND $rows AS row
            MATCH (s:Section {section_id: row.section_id})
            CREATE (m:Mention {mention_id: row.mention_id, section_id: row.section_id, name: row.name,
                               name_normalized: row.name_normalized, type: row.type, value: row.value,
                               kind: row.kind, alias: row.alias, evidence: row.evidence,
                               run_id: row.run_id, scope: row.scope})
            CREATE (s)-[:MENTIONS]->(m)
            """,
            rows=batch,
        )
    for batch in _batches(rows["mention_rels"]):
        client.run(
            """
            UNWIND $rows AS row
            MATCH (a:Mention {scope: $scope, run_id: $run_id, mention_id: row.src})
            MATCH (b:Mention {scope: $scope, run_id: $run_id, mention_id: row.dst})
            CREATE (a)-[:REL {type: row.type, evidence: row.evidence}]->(b)
            """,
            rows=batch, scope=scope, run_id=run_id,
        )
    for batch in _batches(rows["entities"]):
        client.run(
            """
            UNWIND $rows AS row
            CREATE (:Entity {entity_id: row.entity_id, name: row.name, type: row.type, domain: row.domain,
                             domains: row.domains, value: row.value, kind: row.kind,
                             n_mentions: row.n_mentions, scope: row.scope})
            """,
            rows=batch,
        )
    for batch in _batches(rows["resolves"]):
        client.run(
            """
            UNWIND $rows AS row
            MATCH (m:Mention {scope: $scope, run_id: $run_id, mention_id: row.mention_id})
            MATCH (e:Entity {entity_id: row.entity_id})
            CREATE (m)-[:RESOLVES_TO]->(e)
            """,
            rows=batch, scope=scope, run_id=run_id,
        )
    by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for rel in rows["entity_rels"]:
        by_type[rel["type"]].append(rel)
    for rel_type, rels in by_type.items():
        assert rel_type in RELATION_TYPES  # relationship types come from the closed schema only
        for batch in _batches(rels):
            client.run(
                f"""
                UNWIND $rows AS row
                MATCH (a:Entity {{entity_id: row.src}}), (b:Entity {{entity_id: row.dst}})
                CREATE (a)-[:{rel_type} {{support: row.support, section_ids: row.section_ids}}]->(b)
                """,
                rows=batch,
            )


def load(client: KGClient, extraction: Path, resolution: Path, scope: str, run_id: str) -> Dict[str, Any]:
    records, res = load_inputs(extraction, resolution)
    rows = build_rows(records, res, scope, run_id)
    ensure_schema(client)
    delete_scope(client, scope)
    write(client, rows, scope, run_id)
    return rows


def scope_counts(client: KGClient, scope: str) -> Dict[str, int]:
    q = {
        "Mention": "MATCH (m:Mention {scope: $scope}) RETURN count(m) AS n",
        "MENTIONS": "MATCH (:Section)-[r:MENTIONS]->(:Mention {scope: $scope}) RETURN count(r) AS n",
        "REL": "MATCH (:Mention {scope: $scope})-[r:REL]->() RETURN count(r) AS n",
        "Entity": "MATCH (e:Entity {scope: $scope}) RETURN count(e) AS n",
        "RESOLVES_TO": "MATCH (:Mention {scope: $scope})-[r:RESOLVES_TO]->() RETURN count(r) AS n",
        "entity relations": "MATCH (a:Entity {scope: $scope})-[r]->(:Entity) RETURN count(r) AS n",
    }
    return {k: client.run(v, scope=scope)[0]["n"] for k, v in q.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scope", default="pilot")
    parser.add_argument("--extraction", type=Path, default=DEFAULT_EXTRACTION)
    parser.add_argument("--resolution", type=Path, default=DEFAULT_RESOLUTION)
    parser.add_argument("--run-id", default="pilot3_run1")
    args = parser.parse_args()

    with KGClient() as client:
        client.verify()
        rows = load(client, args.extraction, args.resolution, args.scope, args.run_id)
        print(f"Scope '{args.scope}' (run {args.run_id}) loaded from {args.extraction.name} "
              f"+ {args.resolution.name}")
        print(f"Rows: {len(rows['mentions'])} mentions, {len(rows['mention_rels'])} mention relations, "
              f"{len(rows['entities'])} entities, {len(rows['entity_rels'])} entity relations")
        print(f"Not loaded: {rows['counts']}")
        print(f"Neo4j: {scope_counts(client, args.scope)}")


if __name__ == "__main__":
    main()
