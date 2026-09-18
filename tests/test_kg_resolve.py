"""Tests for type-conflict resolution in entity resolution (src/kg/resolve.py)."""
import pytest

from src.kg.resolve import (DEFAULT_INPUT, choose_type, generic_specific_conflict, key_of, load_mentions,
                            resolve_types)


def _mention(type_, relations=()):
    return {"extracted_type": type_, "type": type_, "relations": list(relations)}


def test_majority_type_wins():
    ms = [_mention("Service"), _mention("Service"), _mention("Outcome")]
    assert choose_type(ms) == ("Service", "majority")


def test_tie_goes_to_the_type_that_fits_the_relations():
    # As a Service the mention can REQUIRE a Requirement; as a Requirement it cannot.
    ms = [_mention("Service", [("REQUIRES", True, "Requirement")]), _mention("Requirement")]
    assert choose_type(ms) == ("Service", "relation_fit")


def test_remaining_tie_uses_the_fixed_priority():
    ms = [_mention("Service"), _mention("Document")]
    assert choose_type(ms) == ("Document", "priority")
    ms = [_mention("ContactPoint"), _mention("Organization")]
    assert choose_type(ms) == ("Organization", "priority")


def test_ny_state_driver_license_becomes_a_document():
    """Pilot case: extracted once as Document and once as Service (with 4 relations that both
    types satisfy), previously resolved to Service by the type order."""
    if not DEFAULT_INPUT.exists():
        pytest.skip("pilot extraction file not found")
    mentions = load_mentions([DEFAULT_INPUT])
    conflicts = {c["name"]: c for c in resolve_types(mentions)}
    assert conflicts["ny state driver license"]["resolved_type"] == "Document"
    assert all(m["type"] == "Document" for m in mentions if m["name"].casefold() == "ny state driver license")


# --- generic vs specific -------------------------------------------------------------------

def _g(name):
    return {"key": key_of(name)}


@pytest.mark.parametrize("a, b", [
    ("proof of identity", "NY State driver license"),                      # category vs instance
    ("mail", "phone"),
    ("disability compensation", "disability compensation and pension benefits"),
    ("surviving spouses", "surviving spouse or child"),
])
def test_generic_and_specific_names_never_merge(a, b):
    assert generic_specific_conflict(_g(a), _g(b)) is not None


@pytest.mark.parametrize("a, b", [
    ("insurance ID card", "NY State Insurance ID card"),
    ("current NY State Insurance ID card", "digital electronic NY State Insurance ID Card"),
    ("loans", "student loans"),                                            # labelled correct in v1
    ("DMV office", "local DMV office"),
])
def test_qualified_names_may_still_merge(a, b):
    assert generic_specific_conflict(_g(a), _g(b)) is None
