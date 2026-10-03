"""Unit tests for the deterministic post-filters (src/kg/postfilter.py)."""
import pytest

from src.kg.postfilter import apply, is_opening_hours, is_staff_role, is_ui_text


def _e(name, type_, value=None):
    return {"name": name, "type": type_, "value": value}


def _r(source, relation, target, st="Service", tt="Service"):
    return {"source": source, "relation": relation, "target": target, "evidence": "x",
            "source_type": st, "target_type": tt, "schema_valid": True}


@pytest.mark.parametrize("name, value", [
    ("help 24 hours a day , 7 days a week", None), ("24/7", None), ("support hours", "Monday through Friday"),
    ("8:00 a.m. to 5:30 p.m.", "8:00 a.m. to 5:30 p.m."),
])
def test_opening_hours_time_limits_are_detected(name, value):
    assert is_opening_hours(_e(name, "TimeLimit", value))


@pytest.mark.parametrize("name, value", [("within 30 days", "within 30 days"), ("2 years", "2 years"),
                                         ("60 days", "within 60 days of receiving our decision")])
def test_deadlines_and_validity_periods_are_kept(name, value):
    assert not is_opening_hours(_e(name, "TimeLimit", value))


@pytest.mark.parametrize("name", ["trained VA counselor", "VA social worker", "Women Veterans Program Manager",
                                  "staff member", "representative"])
def test_staff_roles_are_detected(name):
    assert is_staff_role(_e(name, "Role"))


@pytest.mark.parametrize("name", ["Veteran", "surviving spouse", "lessee", "applicant"])
def test_citizen_roles_are_kept(name):
    assert not is_staff_role(_e(name, "Role"))


@pytest.mark.parametrize("name", ["sign in", "Create account", "Learn more", "continue", "Request Medical Reconsideration"])
def test_ui_text_is_detected(name):
    assert is_ui_text(_e(name, "Service"))


@pytest.mark.parametrize("name", ["Request a Reconsideration Online for a Non-Medical Determination",
                                  "print a temporary license", "Check the Status of Your Reconsideration",
                                  "request an appeal", "request an appeal online"])
def test_real_services_are_not_ui_text(name):
    assert not is_ui_text(_e(name, "Service"))


def test_dropping_an_entity_drops_its_relations():
    ents = [_e("VA medical center", "Organization"), _e("trained VA counselor", "Role")]
    rels = [_r("VA medical center", "APPLIES_TO", "trained VA counselor", "Organization", "Role")]
    kept, out, log = apply(ents, rels)
    assert [e["name"] for e in kept] == ["VA medical center"] and out == []
    assert {x["reason"] for x in log} == {"staff_role", "endpoint_removed"}


def test_part_of_hub_is_made_the_parent():
    """'request an appeal PART_OF <each level>' -> '<each level> PART_OF request an appeal'."""
    levels = ["Reconsideration", "Hearing by an administrative law judge", "Review by the Appeals Council"]
    rels = [_r("request an appeal", "PART_OF", lvl) for lvl in levels]
    _, out, log = apply([], rels)
    assert sorted((r["source"], r["target"]) for r in out) == sorted((lvl, "request an appeal") for lvl in levels)
    assert all(r["schema_valid"] for r in out) and len(log) == 3


def test_single_part_of_is_left_alone():
    rels = [_r("free health care", "PART_OF", "programs and services")]
    assert apply([], rels)[1] == rels
