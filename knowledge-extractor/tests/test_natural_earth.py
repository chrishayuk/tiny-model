"""Pure helper tests for knowledge/natural-earth.

The shapefile download/read path is integration-tested by
``make run-natural-earth``. These tests cover the record-shaping logic
against synthetic DBF-record dicts so they're dep-free and instant.
"""

from __future__ import annotations

import pytest

from knowledge_extractor.knowledge.natural_earth.extractor import (
    _admin0_triples,
    _admin1_triples,
    _strip_ne_prefix,
)
from knowledge_extractor.knowledge.natural_earth.model import is_null_value


# ---------- _strip_ne_prefix ------------------------------------------


def test_strip_ne_prefix_with_number():
    assert _strip_ne_prefix("2. Developed region: non-G7") == "Developed region: non-G7"
    assert _strip_ne_prefix("7. Least developed region") == "Least developed region"


def test_strip_ne_prefix_without_number():
    assert _strip_ne_prefix("High income: OECD") == "High income: OECD"
    assert _strip_ne_prefix("Sovereign country") == "Sovereign country"


def test_strip_ne_prefix_strips_whitespace():
    assert _strip_ne_prefix("  5. Emerging region  ") == "Emerging region"


# ---------- is_null_value ---------------------------------------------


@pytest.mark.parametrize("value", [None, "", "-99", "-1", "nan", "NONE", "null"])
def test_is_null_value_positive(value):
    assert is_null_value(value) is True


@pytest.mark.parametrize("value", ["GB", "France", "0", "Somewhere"])
def test_is_null_value_negative(value):
    assert is_null_value(value) is False


# ---------- _admin0_triples -------------------------------------------


def test_admin0_french_guiana_sovereignty_chain():
    """The motivating example for this dataset: dependencies surface
    their sovereign state via a ``sovereignty`` triple, keyed off
    ADM0_A3 ≠ SOV_A3."""
    rec = {
        "name": "French Guiana",
        "sovereignt": "France",
        "adm0_a3": "GUF",
        "sov_a3": "FR1",
        "type": "Dependency",
        "continent": "South America",
        "region_un": "Americas",
        "subregion": "South America",
        "region_wb": "Latin America & Caribbean",
        "economy": "6. Developing region",
        "income_grp": "2. High income: nonOECD",
        "iso_a2": "GF",
        "iso_a3": "GUF",
        "iso_n3": "254",
        "wikidataid": "Q3769",
    }
    triples = list(_admin0_triples(rec))
    by_rel = {t.relation: t.object for t in triples}

    assert by_rel["sovereignty"] == "France"
    assert by_rel["ne_type"] == "Dependency"
    assert by_rel["continent_ne"] == "South America"
    assert by_rel["economy_class"] == "Developing region"      # numeric prefix stripped
    assert by_rel["income_group"] == "High income: nonOECD"    # numeric prefix stripped
    assert by_rel["iso_alpha2"] == "GF"
    assert by_rel["iso_alpha3"] == "GUF"
    assert by_rel["iso_numeric"] == "254"
    assert by_rel["wikidata_id"] == "Q3769"
    # Provenance uses ADM0_A3
    assert all(t.provenance == "ne_admin0:GUF" for t in triples)


def test_admin0_sovereign_country_skips_sovereignty():
    """Sovereign countries have ADM0_A3 == SOV_A3; we don't emit a
    sovereignty triple."""
    rec = {
        "name": "Germany",
        "sovereignt": "Germany",
        "adm0_a3": "DEU",
        "sov_a3": "DEU",
        "type": "Sovereign country",
        "iso_a3": "DEU",
    }
    triples = list(_admin0_triples(rec))
    relations = {t.relation for t in triples}
    assert "sovereignty" not in relations
    assert "ne_type" in relations
    assert "iso_alpha3" in relations


def test_admin0_indeterminate_skips_sovereignty():
    """Entities with TYPE='Indeterminate' don't emit a sovereignty triple
    even when ADM0_A3 != SOV_A3 — the relationship is unresolved."""
    rec = {
        "name": "Palestine",
        "sovereignt": "Israel",
        "adm0_a3": "PSX",
        "sov_a3": "IS1",
        "type": "Indeterminate",
    }
    triples = list(_admin0_triples(rec))
    relations = {t.relation for t in triples}
    assert "sovereignty" not in relations
    assert "ne_type" in relations  # TYPE is still emitted


def test_admin0_null_sentinels_dropped():
    """NE uses '-99' / '-1' for missing values; the extractor must drop
    them rather than emit garbage."""
    rec = {
        "name": "Somewhere",
        "adm0_a3": "XYZ",
        "iso_a2": "-99",
        "iso_a3": "XYZ",
        "type": "Country",
    }
    triples = list(_admin0_triples(rec))
    by_rel = {t.relation: t.object for t in triples}
    assert "iso_alpha2" not in by_rel
    assert by_rel["iso_alpha3"] == "XYZ"
    assert by_rel["ne_type"] == "Country"


def test_admin0_missing_name_skipped():
    rec = {"sovereignt": "France", "type": "Dependency"}
    triples = list(_admin0_triples(rec))
    assert triples == []


def test_admin0_falls_back_to_name_long():
    rec = {"name": "", "name_long": "Long Country Name", "adm0_a3": "LCN", "type": "Country", "iso_a3": "LCN"}
    triples = list(_admin0_triples(rec))
    subjects = {t.subject for t in triples}
    assert subjects == {"Long Country Name"}


def test_admin0_wikidata_only_for_valid_qid():
    rec = {"name": "Foo", "wikidataid": "not-a-qid", "iso_a3": "FOO"}
    triples = list(_admin0_triples(rec))
    relations = {t.relation for t in triples}
    assert "wikidata_id" not in relations


# ---------- _admin1_triples -------------------------------------------


def test_admin1_england_within_uk():
    rec = {
        "name": "England",
        "admin": "United Kingdom",
        "iso_3166_2": "GB-ENG",
        "type_en": "Country",
    }
    triples = list(_admin1_triples(rec))
    by_rel = {t.relation: t.object for t in triples}
    assert by_rel["within"] == "United Kingdom"
    assert by_rel["iso_3166_2"] == "GB-ENG"
    assert by_rel["admin_type"] == "Country"
    for t in triples:
        assert t.provenance == "ne_admin1:GB-ENG"


def test_admin1_missing_name_skipped():
    rec = {"admin": "United Kingdom", "iso_3166_2": "GB-ENG"}
    assert list(_admin1_triples(rec)) == []


def test_admin1_falls_back_to_name_en():
    rec = {"name": "", "name_en": "Bavaria", "admin": "Germany", "type_en": "State"}
    triples = list(_admin1_triples(rec))
    subjects = {t.subject for t in triples}
    assert subjects == {"Bavaria"}


def test_admin1_partial_record_yields_what_it_can():
    """Some records have name+admin but no ISO code or type. We still
    emit the ``within`` triple rather than skipping the whole record."""
    rec = {"name": "Some County", "admin": "Ireland"}
    triples = list(_admin1_triples(rec))
    by_rel = {t.relation: t.object for t in triples}
    assert by_rel == {"within": "Ireland"}
