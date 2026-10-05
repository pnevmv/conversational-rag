"""Graph statistics for one scope: counts per layer, type and domain, degree
distribution, connected components and top entities.

    python -m src.kg.stats --scope pilot
"""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import networkx as nx
import numpy as np

from src.kg.client import KGClient
from src.kg.planning import MIN_CHARS

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
KG_DIR = PROJECT_ROOT / "experiments" / "kg"


def _scope_filter(var: str, scope: Optional[str]) -> str:
    return "" if scope is None else f" AND {var}.scope = $scope"


def scope_documents(client: KGClient, scope: Optional[str]) -> List[str]:
    rows = client.run(
        "MATCH (d:Document)-[:HAS_SECTION]->(:Section)-[:MENTIONS]->(m:Mention) "
        f"WHERE true{_scope_filter('m', scope)} RETURN DISTINCT d.doc_id AS doc_id ORDER BY doc_id",
        scope=scope,
    )
    return [r["doc_id"] for r in rows]


def layer_counts(client: KGClient, scope: Optional[str], docs: List[str]) -> Dict[str, Any]:
    f_m, f_e = _scope_filter("m", scope), _scope_filter("e", scope)
    structural = client.run(
        """
        MATCH (d:Document) WHERE d.doc_id IN $docs
        OPTIONAL MATCH (d)-[:HAS_SECTION]->(s:Section)
        OPTIONAL MATCH (s)-[:HAS_SPAN]->(sp:Span)
        RETURN count(DISTINCT d) AS Document, count(DISTINCT s) AS Section, count(DISTINCT sp) AS Span
        """, docs=docs)[0]
    nexts = client.run(
        "MATCH (d:Document)-[:HAS_SECTION]->(s:Section)-[r:NEXT]->() WHERE d.doc_id IN $docs RETURN count(r) AS n",
        docs=docs)[0]["n"]
    meta_rel = client.run(
        f"MATCH (m:Mention)-[r:REL]->(:Mention) WHERE true{f_m} RETURN r.type AS type, count(*) AS n ORDER BY type",
        scope=scope)
    mentions_by_type = client.run(
        f"MATCH (m:Mention) WHERE true{f_m} RETURN m.type AS type, count(*) AS n ORDER BY type", scope=scope)
    entities_by_type = client.run(
        f"MATCH (e:Entity) WHERE true{f_e} RETURN e.type AS type, count(*) AS n ORDER BY type", scope=scope)
    kg_rel = client.run(
        f"MATCH (e:Entity)-[r]->(:Entity) WHERE true{f_e} RETURN type(r) AS type, count(*) AS n, "
        "sum(r.support) AS support ORDER BY type", scope=scope)
    resolves = client.run(
        f"MATCH (m:Mention)-[r:RESOLVES_TO]->(:Entity) WHERE true{f_m} RETURN count(r) AS n", scope=scope)[0]["n"]
    return {
        "structural": {"nodes": {"Document": structural["Document"], "Section": structural["Section"],
                                 "Span": structural["Span"]},
                       "relationships": {"HAS_SECTION": structural["Section"], "HAS_SPAN": structural["Span"],
                                         "NEXT": nexts}},
        "metagraph": {"nodes": {"Mention": sum(r["n"] for r in mentions_by_type)},
                      "mentions_by_type": {r["type"]: r["n"] for r in mentions_by_type},
                      "relationships": {"MENTIONS": sum(r["n"] for r in mentions_by_type),
                                        "REL": sum(r["n"] for r in meta_rel)},
                      "REL_by_type": {r["type"]: r["n"] for r in meta_rel}},
        "kg": {"nodes": {"Entity": sum(r["n"] for r in entities_by_type)},
               "entities_by_type": {r["type"]: r["n"] for r in entities_by_type},
               "relationships": {"RESOLVES_TO": resolves, "entity relations": sum(r["n"] for r in kg_rel)},
               "relations_by_type": {r["type"]: {"edges": r["n"], "support": r["support"]} for r in kg_rel}},
    }


def section_coverage(client: KGClient, scope: Optional[str], docs: List[str]) -> Dict[str, Any]:
    rows = client.run(
        f"""
        MATCH (d:Document)-[:HAS_SECTION]->(s:Section) WHERE d.doc_id IN $docs
        OPTIONAL MATCH (s)-[:MENTIONS]->(m:Mention) WHERE true{_scope_filter('m', scope)}
        RETURN s.section_id AS sid, size(s.text) AS chars, s.is_boilerplate AS boiler, count(m) AS n
        """, docs=docs, scope=scope)
    eligible = [r for r in rows if not r["boiler"] and (r["chars"] or 0) >= MIN_CHARS]
    with_m = [r for r in rows if r["n"] > 0]
    return {
        "sections": len(rows),
        "with_mentions": len(with_m),
        "share_with_mentions": len(with_m) / len(rows) if rows else None,
        "extractable_sections": len(eligible),
        "share_of_extractable_with_mentions": (sum(1 for r in eligible if r["n"] > 0) / len(eligible)
                                               if eligible else None),
    }


def domain_breakdown(client: KGClient, scope: Optional[str]) -> Dict[str, Any]:
    f_e, f_m = _scope_filter("e", scope), _scope_filter("m", scope)
    ents = client.run(f"MATCH (e:Entity) WHERE true{f_e} RETURN e.domain AS domain, e.type AS type, count(*) AS n",
                      scope=scope)
    rels = client.run(f"MATCH (e:Entity)-[r]->(:Entity) WHERE true{f_e} "
                      "RETURN e.domain AS domain, type(r) AS type, count(*) AS n", scope=scope)
    cross = client.run(f"MATCH (e:Entity) WHERE true{f_e} AND size(e.domains) > 1 RETURN count(e) AS n",
                       scope=scope)[0]["n"]
    mentions = client.run(
        f"MATCH (m:Mention) WHERE true{f_m} RETURN coalesce(m.is_social, false) AS social, "
        "COUNT { (m)-[:RESOLVES_TO]->() } > 0 AS resolved, count(*) AS n", scope=scope)
    table: Dict[str, Dict[str, int]] = defaultdict(dict)
    for r in ents:
        table[r["domain"]][r["type"]] = r["n"]
    rtable: Dict[str, Dict[str, int]] = defaultdict(dict)
    for r in rels:
        rtable[r["domain"]][r["type"]] = r["n"]
    total = sum(r["n"] for r in mentions)
    non_social = sum(r["n"] for r in mentions if not r["social"])
    resolved = sum(r["n"] for r in mentions if r["resolved"])
    return {
        "entities_by_domain_and_type": dict(table),
        "entities_by_domain": {d: sum(v.values()) for d, v in table.items()},
        "relations_by_domain_and_type": dict(rtable),
        "relations_by_domain": {d: sum(v.values()) for d, v in rtable.items()},
        "entities_in_several_domains": cross,
        "mentions": {"total": total, "social": total - non_social, "resolved": resolved,
                     "share_resolved": resolved / total if total else None,
                     "share_of_non_social_resolved": resolved / non_social if non_social else None},
    }


def entity_graph(client: KGClient, scope: Optional[str]) -> Dict[str, Any]:
    f_e = _scope_filter("e", scope)
    nodes = client.run(f"MATCH (e:Entity) WHERE true{f_e} RETURN e.entity_id AS id, e.name AS name, "
                       "e.type AS type, e.n_mentions AS n_mentions", scope=scope)
    edges = client.run(f"MATCH (e:Entity)-[r]->(b:Entity) WHERE true{f_e} "
                       "RETURN e.entity_id AS a, b.entity_id AS b, type(r) AS type", scope=scope)
    g = nx.MultiGraph()
    g.add_nodes_from((n["id"], n) for n in nodes)
    g.add_edges_from((e["a"], e["b"]) for e in edges)
    degrees = np.array([d for _, d in g.degree()]) if len(g) else np.array([0])
    comps = sorted((len(c) for c in nx.connected_components(g)), reverse=True)
    top: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for node_id, deg in sorted(g.degree(), key=lambda x: (-x[1], x[0])):
        data = g.nodes[node_id]
        if len(top[data["type"]]) < 10 and deg > 0:
            top[data["type"]].append({"name": data["name"], "degree": deg, "n_mentions": data["n_mentions"]})
    return {
        "degree": {"median": float(np.median(degrees)), "p90": float(np.percentile(degrees, 90)),
                   "max": int(degrees.max()), "mean": round(float(degrees.mean()), 2),
                   "isolated": int((degrees == 0).sum())},
        "components": {"count": len(comps), "largest": comps[0] if comps else 0,
                       "largest_share": comps[0] / len(g) if len(g) else None,
                       "size_distribution": dict(sorted(Counter(comps).items(), reverse=True))},
        "top_by_degree": dict(top),
    }


def collect(client: KGClient, scope: Optional[str]) -> Dict[str, Any]:
    docs = scope_documents(client, scope)
    return {"scope": scope or "*", "documents": len(docs), "layers": layer_counts(client, scope, docs),
            "section_coverage": section_coverage(client, scope, docs), "entity_graph": entity_graph(client, scope),
            "domains": domain_breakdown(client, scope)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scope", default="pilot", help="scope name, or '*' for all scopes")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    scope = None if args.scope == "*" else args.scope
    with KGClient() as client:
        stats = collect(client, scope)
    output = args.output or KG_DIR / f"kg_stats_{args.scope.replace('*', 'all')}.json"
    output.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")

    L = stats["layers"]
    print(f"Scope {stats['scope']}: {stats['documents']} documents")
    for layer in ("structural", "metagraph", "kg"):
        print(f"  {layer:10} nodes {L[layer]['nodes']}  relationships {L[layer]['relationships']}")
    print(f"  mentions by type {L['metagraph']['mentions_by_type']}")
    print(f"  entities by type {L['kg']['entities_by_type']}")
    print(f"  KG relations {{type: edges}} {{{', '.join(f'{k}: {v['edges']}' for k, v in L['kg']['relations_by_type'].items())}}}")
    c = stats["section_coverage"]
    print(f"Sections with >= 1 mention: {c['with_mentions']}/{c['sections']} ({c['share_with_mentions']:.1%}); "
          f"of extractable sections: {c['share_of_extractable_with_mentions']:.1%}")
    g = stats["entity_graph"]
    print(f"Entity degree: {g['degree']}")
    print(f"Components: {g['components']['count']} (largest {g['components']['largest']}, "
          f"{g['components']['largest_share']:.1%}); sizes {g['components']['size_distribution']}")
    for t, items in g["top_by_degree"].items():
        print(f"  top {t}: " + "; ".join(f"{i['name']} ({i['degree']})" for i in items[:5]))
    d = stats["domains"]
    print(f"Entities by domain: {d['entities_by_domain']} (in several domains: {d['entities_in_several_domains']})")
    print(f"Entity relations by domain: {d['relations_by_domain']}")
    m = d["mentions"]
    print(f"Mentions resolved: {m['resolved']}/{m['total']} ({m['share_resolved']:.1%}); "
          f"of non-social: {m['share_of_non_social_resolved']:.1%} ({m['social']} social)")
    print(f"Saved -> {output}")


if __name__ == "__main__":
    main()
