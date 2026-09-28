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
