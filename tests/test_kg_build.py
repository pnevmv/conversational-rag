"""Tests for the metagraph and KG-layer loaders (src/kg/load_neo4j.py).

They load the pilot extraction and its entity-resolution clusters into a dedicated
scope (`pytest_pilot`), so the `pilot` scope and the structural layer are left alone,
and delete that scope afterwards. Skipped when Neo4j is not reachable or the pilot
files (not versioned) are missing.
"""
import pytest

from src.kg.load_neo4j import DEFAULT_EXTRACTION, DEFAULT_RESOLUTION, build_rows, delete_scope, load, load_inputs, scope_counts
from src.kg.schema import SYMMETRIC_RELATIONS, is_valid_triple

SCOPE = "pytest_pilot"
RUN_ID = "pytest_run"


@pytest.fixture(scope="module")
def client():
    if not (DEFAULT_EXTRACTION.exists() and DEFAULT_RESOLUTION.exists()):
        pytest.skip("pilot extraction / resolution files not found")
    try:
        from src.kg.client import KGClient

        c = KGClient()
        c.verify()
    except Exception as exc:  # noqa: BLE001 - any connection problem skips the module
        pytest.skip(f"Neo4j not reachable: {exc}")
    yield c
    delete_scope(c, SCOPE)
    c.close()


@pytest.fixture(scope="module")
def rows():
    records, res = load_inputs(DEFAULT_EXTRACTION, DEFAULT_RESOLUTION)
    return build_rows(records, res, SCOPE, RUN_ID)


@pytest.fixture(scope="module")
def loaded(client, rows):
    structural_before = client.label_counts()
    load(client, DEFAULT_EXTRACTION, DEFAULT_RESOLUTION, SCOPE, RUN_ID)
    return structural_before


def _expected(rows):
    return {
        "Mention": len(rows["mentions"]), "MENTIONS": len(rows["mentions"]), "REL": len(rows["mention_rels"]),
        "Entity": len(rows["entities"]), "RESOLVES_TO": len(rows["resolves"]),
        "entity relations": len(rows["entity_rels"]),
    }


def test_rows_skip_relations_that_break_the_type_rules(rows):
    """Violating relations are counted, not loaded; loaded entity relations respect the
    rules under the resolved (majority) entity types."""
    assert rows["counts"].get("mention_relations_violating_rules", 0) > 0
    type_of = {e["entity_id"]: e["type"] for e in rows["entities"]}
    assert all(is_valid_triple(r["type"], type_of[r["src"]], type_of[r["dst"]]) for r in rows["entity_rels"])


def test_alternative_to_is_stored_once_per_pair(rows):
    pairs = [frozenset((r["src"], r["dst"])) for r in rows["entity_rels"] if r["type"] in SYMMETRIC_RELATIONS]
    assert len(pairs) == len(set(pairs))


def test_entity_relation_support_matches_section_ids(rows):
    for r in rows["entity_rels"]:
        assert r["support"] >= len(r["section_ids"]) >= 1


def test_counts_match_the_input(client, rows, loaded):
    assert scope_counts(client, SCOPE) == _expected(rows)


def test_loading_twice_is_idempotent(client, rows, loaded):
    load(client, DEFAULT_EXTRACTION, DEFAULT_RESOLUTION, SCOPE, RUN_ID)
    assert scope_counts(client, SCOPE) == _expected(rows)


def test_structural_layer_is_untouched(client, loaded):
    after = client.label_counts()
    for label in ("Domain", "Document", "Section", "Span"):
        assert after[label] == loaded[label]


def test_every_non_social_mention_resolves_to_exactly_one_entity(client, loaded):
    bad = client.run(
        "MATCH (m:Mention {scope: $scope, is_social: false}) OPTIONAL MATCH (m)-[r:RESOLVES_TO]->(:Entity) "
        "WITH m, count(r) AS n WHERE n <> 1 RETURN count(m) AS n", scope=SCOPE)[0]["n"]
    assert bad == 0


def test_social_media_contact_points_stay_out_of_the_kg_layer(client, rows, loaded):
    """Flagged in the metagraph, but no RESOLVES_TO, entity or entity relation."""
    social = client.run("MATCH (m:Mention {scope: $scope, is_social: true}) "
                        "RETURN m.type AS type, count(*) AS n, sum(COUNT { (m)-[:RESOLVES_TO]->() }) AS resolved",
                        scope=SCOPE)
    assert social and all(r["type"] == "ContactPoint" and r["resolved"] == 0 for r in social)
    assert sum(r["n"] for r in social) == sum(rows["social_mentions_by_domain"].values()) > 0
    names = client.run("MATCH (e:Entity {scope: $scope, type: 'ContactPoint'}) RETURN e.name AS name", scope=SCOPE)
    assert not any(n["name"].casefold() in {"facebook", "twitter", "youtube", "instagram", "linkedin"} for n in names)


def test_no_orphan_resolves_to_or_entities(client, loaded):
    # RESOLVES_TO only links Mention -> Entity of the same scope, and every Entity has a mention
    cross = client.run(
        "MATCH (m:Mention)-[:RESOLVES_TO]->(e:Entity) WHERE (m.scope = $scope) <> (e.scope = $scope) "
        "RETURN count(*) AS n", scope=SCOPE)[0]["n"]
    orphan_entities = client.run(
        "MATCH (e:Entity {scope: $scope}) WHERE NOT ()-[:RESOLVES_TO]->(e) RETURN count(e) AS n",
        scope=SCOPE)[0]["n"]
    assert cross == 0 and orphan_entities == 0


def test_every_mention_hangs_off_a_section(client, loaded):
    orphans = client.run(
        "MATCH (m:Mention {scope: $scope}) WHERE NOT (:Section)-[:MENTIONS]->(m) RETURN count(m) AS n",
        scope=SCOPE)[0]["n"]
    assert orphans == 0


def test_deleting_a_scope_leaves_other_scopes(client, loaded):
    other = client.run("MATCH (m:Mention) WHERE m.scope <> $scope RETURN count(m) AS n", scope=SCOPE)[0]["n"]
    delete_scope(client, SCOPE)
    assert scope_counts(client, SCOPE)["Mention"] == 0
    assert client.run("MATCH (m:Mention) WHERE m.scope <> $scope RETURN count(m) AS n", scope=SCOPE)[0]["n"] == other
