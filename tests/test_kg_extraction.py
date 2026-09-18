"""Prompt regression tests for the closed-schema KG extraction.

The cached-output tests read the model's raw outputs from the extraction cache
(experiments/cache/kg_extract); they never call the API and are skipped when the
cache is missing. Populate it with:

    python -m src.kg.extract_closed --regression
    python -m src.kg.extract_closed

The regression sections are the ones where the open-extraction pilot made known
errors: reversed REQUIRES, requirement nodes as REQUIRES sources, self-loops,
EXEMPTS instead of EXEMPT_FROM, and CamelCase names.
"""
import json
import re
from typing import Any, Dict, List

import pytest

from src.data.loader import load_sections
from src.kg.extract import DEFAULT_CACHE_DIR, ExtractionCache
from src.kg.extract_closed import (
    REGRESSION_SECTIONS,
    CacheMiss,
    _with_domain,
    extract_chunk,
    merge_chunks,
    postprocess,
    select_pilot_sections,
)
from src.kg.pilot2_stats import is_camel_case
from src.kg.pilot_stats import _lenient
from src.kg.planning import CHUNK_MAX_CHARS, chunk_text, plan_units
from src.kg.schema import has_contact_detail

LEARNER_PERMIT = "Get a learner permit#1_0::31"
WOMENS_HEALTH = "Women's Health Care Needs | Veterans Affairs#1_0::1"
ARE_YOU_WORKING = "Benefits Planner: Disability | Are You Working | Social Security Administration#2_0::1"
WELCOME_KIT = "Print Out Your VA Welcome Kit | Veterans Affairs#1_0::13"
FEE_TABLE = "Commercial vehicle registration fees, vehicle use taxes and supplemental fees#3_0::34"
MEDICARE_PREMIUMS = "Benefits Planner: Retirement | Medicare Premiums | SSA#1_0::32"


@pytest.fixture(scope="module")
def cached() -> Dict[str, Dict[str, Any]]:
    """{section_id: {"text", "raw": [chunk outputs], "entities", "relations"}} from the cache."""
    sections = _with_domain(load_sections())
    plan = plan_units(sections)
    unit_of = {sid: u for u in plan["units"] for sid in u["member_ids"]}
    cache = ExtractionCache(DEFAULT_CACHE_DIR)
    targets = set(REGRESSION_SECTIONS) | {s["section_id"] for s in select_pilot_sections(sections, 2, 42)}

    out: Dict[str, Dict[str, Any]] = {}
    for s in sections:
        if s["section_id"] not in targets or s["section_id"] not in unit_of:
            continue
        unit = unit_of[s["section_id"]]
        try:
            raws = [extract_chunk(None, cache, unit, i)[0] for i in range(len(unit["chunks"]))]
        except CacheMiss:
            pytest.skip("extraction cache not populated; run src.kg.extract_closed first")
        entities, relations, _ = merge_chunks([postprocess(r) for r in raws])
        out[s["section_id"]] = {"text": s["text"], "raw": raws, "entities": entities, "relations": relations}
    return out


def _triples(record: Dict[str, Any], relation: str) -> List[tuple]:
    return [(r["source"].casefold(), r["target"].casefold(), r["source_type"], r["target_type"])
            for r in record["relations"] if r["relation"] == relation]


# --- known error cases from the open-extraction pilot -----------------------------------

def test_learner_permit_requires_points_from_road_test(cached):
    """Pilot 1 had 'supervised driving practice -REQUIRES-> road test' (reversed)."""
    requires = _triples(cached[LEARNER_PERMIT], "REQUIRES")
    assert any("road test" in s and "practice" in t for s, t, _, _ in requires)
    assert not any("road test" in t and ("practice" in s or "course" in s) for s, t, _, _ in requires)


def test_womens_health_requirement_is_not_a_requires_source(cached):
    """Pilot 1 had 'VAHealthCareEligibilityCondition -REQUIRES-> VAHealthCare' (reversed)."""
    requires = _triples(cached[WOMENS_HEALTH], "REQUIRES")
    assert requires
    assert all(st != "Requirement" for _, _, st, _ in requires)


def test_requirement_sources_of_requires_only_point_to_documents(cached):
    """Pilot 1 had 'DisabilityReviewRequirement -REQUIRES-> CaseReview' (malformed)."""
    for sid in (ARE_YOU_WORKING, WOMENS_HEALTH, LEARNER_PERMIT):
        for _, _, st, tt in _triples(cached[sid], "REQUIRES"):
            assert st != "Requirement" or tt == "Document", sid


def test_welcome_kit_has_no_self_loops_in_raw_output(cached):
    """Pilot 1 had 'VA Health Care -HAS_PDF-> VA Health Care' and two similar loops."""
    for raw in cached[WELCOME_KIT]["raw"]:
        assert all(r["source"].casefold() != r["target"].casefold() for r in raw["relations"])


@pytest.mark.xfail(strict=True, reason="model writes 'use taxes and supplemental fees -EXEMPT_FROM-> "
                                       "Agricultural (AGR)' etc.: the relation name is fixed but the "
                                       "direction is still reversed")
def test_fee_table_exemptions_point_to_the_tax_or_fee(cached):
    """Pilot 1 had 'AdditionalFee -EXEMPTS-> <class>' (wrong name and direction).

    The exempt party (vehicle class, taxi) must be the source, the tax or fee the target.
    """
    exempt = _triples(cached[FEE_TABLE], "EXEMPT_FROM")
    assert exempt
    assert all(re.search(r"\b(tax|taxes|fee|fees)\b", t) and not re.search(r"\b(tax|taxes|fee|fees)\b", s)
               for s, t, _, _ in exempt)


@pytest.mark.xfail(strict=True, reason="run-dependent: the pilot-3 prompt kept 1 class entity, the current "
                                       "run lists all 8 ('Agricultural (AGR)', ...)")
def test_fee_table_does_not_enumerate_every_class(cached):
    """Pilot 1 turned the 8 exempt registration classes into 8 entities."""
    codes = {"AGR", "AMB", "FAR", "HIS", "HOU", "SEM", "SPC", "TRL"}
    names = [e["name"] for e in cached[FEE_TABLE]["entities"]]
    assert sum(1 for n in names if set(re.findall(r"[A-Z]{3}", n)) & codes) <= 2


# --- output-wide properties ------------------------------------------------------------

def test_camel_case_names_are_rare(cached):
    """Pilot 1 had 69% CamelCase identifiers instead of surface names."""
    names = [e["name"] for rec in cached.values() for raw in rec["raw"] for e in raw["entities"]]
    assert sum(map(is_camel_case, names)) / len(names) <= 0.02


@pytest.mark.xfail(strict=True, reason="7 of 488 raw relations (1.4%) are self-loops; post-processing "
                                       "removes them")
def test_self_loops_are_rare_in_raw_output(cached):
    rels = [r for rec in cached.values() for raw in rec["raw"] for r in raw["relations"]]
    loops = sum(1 for r in rels if r["source"].casefold() == r["target"].casefold())
    assert loops / len(rels) <= 0.01


@pytest.mark.xfail(strict=True, reason="1 quote still joins two list items with '...' "
                                       "(NY State Insurance ID cards, 'Register a leased vehicle')")
def test_evidence_is_never_stitched_with_ellipsis(cached):
    quotes = [x["evidence"] for rec in cached.values() for raw in rec["raw"]
              for x in raw["entities"] + raw["relations"]]
    assert not [q for q in quotes if "..." in q or "…" in q]


def test_evidence_is_mostly_verbatim(cached):
    """Evidence must be copied from the section; spacing is ignored (the corpus has run-together words)."""
    found = total = 0
    for rec in cached.values():
        text = _lenient(rec["text"]).replace(" ", "")
        for x in rec["entities"] + rec["relations"]:
            total += 1
            found += _lenient(x["evidence"]).replace(" ", "") in text
    assert found / total >= 0.9


def test_alias_captures_parenthetical_abbreviation(cached):
    entities = cached[MEDICARE_PREMIUMS]["entities"]
    assert any(e["alias"] == "MAGI" and "modified adjusted gross income" in e["name"].casefold()
               for e in entities)


def test_time_limits_carry_a_value(cached):
    """The prompt allows a null value only when the text gives none, which should be rare for TimeLimit."""
    limits = [e for rec in cached.values() for e in rec["entities"] if e["type"] == "TimeLimit"]
    assert limits and sum(1 for e in limits if e["value"]) / len(limits) >= 0.95


def test_contact_points_with_a_detail_in_evidence_get_a_value_from_the_model(cached):
    """Pilot 3 left ContactPoint values empty; the prompt now requires them when the evidence
    contains a phone number, postal address, email or URL. Measured on raw model output."""
    raw = [e for rec in cached.values() for out in rec["raw"] for e in out["entities"]
           if e["type"] == "ContactPoint" and has_contact_detail(e["evidence"])]
    assert raw and sum(1 for e in raw if (e["value"] or "").strip()) / len(raw) >= 0.9


def test_contact_points_with_a_detail_in_evidence_always_have_a_value(cached):
    """After post-processing the value is required: missing ones are taken from the evidence."""
    cps = [e for rec in cached.values() for e in rec["entities"]
           if e["type"] == "ContactPoint" and has_contact_detail(e["evidence"])]
    assert cps and all(e["value"] for e in cps)


# --- deterministic post-processing and planning ----------------------------------------

def _entity(name: str, type_: str) -> Dict[str, Any]:
    return {"name": name, "alias": None, "type": type_, "kind": None, "value": None, "text": None,
            "negated": False, "evidence": name}


def test_postprocess_drops_self_loops_and_dangling_relations():
    raw = {
        "entities": [_entity("road test", "Service"), _entity("learner permit", "Service")],
        "relations": [
            {"source": "road test", "relation": "REQUIRES", "target": "road test", "evidence": "x"},
            {"source": "road test", "relation": "REQUIRES", "target": "insurance", "evidence": "x"},
            {"source": "road test", "relation": "REQUIRES", "target": "learner permit", "evidence": "x"},
        ],
    }
    _, relations, counts = postprocess(raw)
    assert [(r["source"], r["target"]) for r in relations] == [("road test", "learner permit")]
    assert counts["relation_self_loop"] == 1 and counts["relation_dangling"] == 1


def test_postprocess_stores_alternative_to_in_one_direction():
    entities = [_entity("Unpaid Refund Discharge", "Service"), _entity("closed school discharge", "Service")]
    forward = {"entities": entities, "relations": [
        {"source": "Unpaid Refund Discharge", "relation": "ALTERNATIVE_TO",
         "target": "closed school discharge", "evidence": "x"}]}
    backward = {"entities": entities, "relations": [
        {"source": "closed school discharge", "relation": "ALTERNATIVE_TO",
         "target": "Unpaid Refund Discharge", "evidence": "x"}]}
    a, b = postprocess(forward)[1][0], postprocess(backward)[1][0]
    assert (a["source"], a["target"]) == (b["source"], b["target"])
    assert a["schema_valid"]


def test_chunk_text_splits_long_text_at_sentence_boundaries():
    sentence = "You must bring an original document to the office . "
    text = sentence * 80  # about 4,200 characters
    chunks = chunk_text(text)
    assert len(chunks) > 1
    assert all(len(c) <= CHUNK_MAX_CHARS for c in chunks)
    assert all(re.search(r"\.$", c) for c in chunks)
    assert " ".join(chunks) == " ".join(text.split())


# --- prompt v2 worked examples ------------------------------------------------------------

def test_v2_examples_quote_their_sections_and_come_from_outside_the_pilot():
    from src.kg.extract_closed import ANNOTATION_DOCS, FEW_SHOT_V2
    from src.kg.schema import is_valid_triple

    sections = {s["section_id"]: s for s in _with_domain(load_sections())}
    pilot_docs = {s["doc_id"] for s in select_pilot_sections(list(sections.values()), 2, 42)}
    norm = lambda t: " ".join(t.split())  # noqa: E731
    for ex in FEW_SHOT_V2:
        sec = sections[ex["section_id"]]
        assert sec["doc_id"] not in pilot_docs and sec["doc_id"] not in ANNOTATION_DOCS
        types = {e["name"]: e["type"] for e in ex["entities"]}
        for e in ex["entities"]:
            assert norm(e["evidence"]) in norm(sec["text"]), e["evidence"]
        for src, rel, dst, evidence in ex["relations"]:
            assert norm(evidence) in norm(sec["text"]), evidence
            assert is_valid_triple(rel, types[src], types[dst]), (src, rel, dst)
