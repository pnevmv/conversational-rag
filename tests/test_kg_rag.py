"""Tests for the KG retrieval helpers (src/kg_rag/)."""
import pytest

from src.kg_rag.eval_linking import query_text, wilson
from src.kg_rag.linker import tokenize
from src.kg_rag.queries import last_agent_turn, predict_domain


def test_last_agent_turn_skips_user_turns():
    ex = {"dialogue_history": [{"role": "agent", "utterance": "first"}, {"role": "user", "utterance": "q"},
                               {"role": "agent", "utterance": " second "}, {"role": "user", "utterance": "q2"}]}
    assert last_agent_turn(ex) == "second"
    assert last_agent_turn({"dialogue_history": []}) is None


def test_predict_domain_is_the_top5_majority():
    ddm = {"a": "dmv", "b": "dmv", "c": "va"}
    top = [{"doc_id": d} for d in ["a", "b", "c", "a", "b", "c", "c"]]  # only the top-5 count
    assert predict_domain(top, ddm) == ("dmv", 0.8)
    assert predict_domain([], ddm) == (None, 0.0)


def test_query_variants():
    rec = {"raw": "and that?", "rewritten": "renew license online", "last_agent": "You can renew online."}
    assert query_text(rec, "raw") == "and that?"
    assert query_text(rec, "rewritten_agent") == "renew license online\nYou can renew online."
    assert query_text({**rec, "last_agent": None}, "rewritten_agent") == "renew license online"


def test_tokenize_drops_stopwords():
    assert tokenize("How do I renew my NY State license?") == ["renew", "ny", "state", "license"]


def test_wilson_interval():
    lo, hi = wilson(62, 140)
    assert lo == pytest.approx(0.363, abs=1e-3) and hi == pytest.approx(0.526, abs=1e-3)



from collections import defaultdict

from src.kg_rag.retrievers import KGRetriever, relation_words, rrf_sections


class _Linker:
    hub_cap = 1

    def __init__(self, entities):
        self.by_id = {e["entity_id"]: e for e in entities}

    def is_hub(self, e):
        return e["degree"] > self.hub_cap


def _kg():
    ents = [{"entity_id": "a", "degree": 1, "section_ids": ["s1"]},
            {"entity_id": "b", "degree": 1, "section_ids": ["s2"]},
            {"entity_id": "h", "degree": 5, "section_ids": ["s1", "s2", "s3"]},
            {"entity_id": "n", "degree": 1, "section_ids": ["s3"]}]
    kg = KGRetriever.__new__(KGRetriever)
    kg.linker = _Linker(ents)
    kg.entities = kg.linker.by_id
    kg.relations = [{"source": "a", "relation": "REQUIRES", "target": "n"},
                    {"source": "h", "relation": "PART_OF", "target": "b"}]
    kg.sections = {s: {"doc_id": "d", "id_sp": s, "span_ids": [s], "title": "t", "section_title": "", "text": s}
                   for s in ("s1", "s2", "s3")}
    kg.idf = {"a": 2.0, "b": 2.0, "h": 0.5, "n": 2.0}
    kg.adjacent = defaultdict(list, {"a": [0], "n": [0], "h": [1], "b": [1]})
    return kg


def test_sections_are_scored_by_idf_weighted_link_scores():
    kg = _kg()
    ranked = kg.rank_sections([{"entity_id": "a", "score": 1.0}, {"entity_id": "h", "score": 1.0}])
    assert [r["section_id"] for r in ranked] == ["s1", "s2", "s3"]   # 2.5, then hub-only 0.5 (tie by id)
    assert ranked[0]["score"] == 2.5 and ranked[0]["n_entities"] == 2


def test_expansion_adds_neighbours_of_non_hubs_only():
    kg = _kg()
    w = kg.weights([{"entity_id": "a", "score": 1.0}, {"entity_id": "h", "score": 1.0}], expand=True)
    assert w["n"] == 0.5 * 1.0 * 2.0      # neighbour of a, decayed
    assert "b" not in w                   # neighbour of the hub h is not expanded


def test_rrf_sections_merges_rankings():
    a = [{"section_id": "x", "rank": 1}, {"section_id": "y", "rank": 2}]
    b = [{"section_id": "y", "rank": 1}]
    assert [r["section_id"] for r in rrf_sections([a, b])] == ["y", "x"]


def test_relation_words():
    assert relation_words("ALTERNATIVE_TO") == "alternative to"
