"""Pure helper functions in the osm-gb extractor.

Does not exercise pyosmium itself — that requires a real PBF and is tested
by the ``make run-osm-gb`` integration run. These tests cover the triple-
shaping logic and the self-contained geohash encoder.
"""

from __future__ import annotations

import math

from knowledge_extractor.knowledge.osm_gb.extractor import (
    _fmt_coord,
    _geohash,
    _is_usable_name,
    _primary_tag,
    _triples_for_entity,
)


# ---------- _geohash ---------------------------------------------------


def test_geohash_wikipedia_canonical_vector():
    """Known-good geohash: (57.64911, 10.40744) → 'u4pruyd' at precision 7."""
    assert _geohash(57.64911, 10.40744, 7) == "u4pruyd"


def test_geohash_london_cluster():
    """Two points ~50 m apart share a 5-character prefix."""
    a = _geohash(51.51943, -0.12700, 7)
    b = _geohash(51.51900, -0.12650, 7)
    assert a[:5] == b[:5]


def test_geohash_precision_prefix():
    """Shorter precisions are prefixes of longer ones."""
    lat, lon = 51.5074, -0.1278
    g5 = _geohash(lat, lon, 5)
    g7 = _geohash(lat, lon, 7)
    assert g7.startswith(g5)


def test_geohash_default_precision_is_seven():
    assert len(_geohash(51.5, -0.1)) == 7


# ---------- _is_usable_name --------------------------------------------


def test_is_usable_name_rejects_too_short():
    assert _is_usable_name("") is False
    assert _is_usable_name("ab") is False


def test_is_usable_name_rejects_numeric():
    assert _is_usable_name("12345") is False


def test_is_usable_name_rejects_too_long():
    assert _is_usable_name("x" * 200) is False


def test_is_usable_name_accepts_normal():
    assert _is_usable_name("British Museum") is True
    assert _is_usable_name("Café Nero") is True


# ---------- _primary_tag -----------------------------------------------


def test_primary_tag_amenity_whitelisted():
    assert _primary_tag({"amenity": "restaurant"}) == ("amenity", "restaurant")


def test_primary_tag_amenity_rejected():
    # amenity=bench is not in the whitelist
    assert _primary_tag({"amenity": "bench"}) is None


def test_primary_tag_shop_accepts_any():
    # shop=* has no value whitelist
    assert _primary_tag({"shop": "bakery"}) == ("shop", "bakery")
    assert _primary_tag({"shop": "anything_exotic"}) == ("shop", "anything_exotic")


def test_primary_tag_ignores_non_primary_keys():
    assert _primary_tag({"highway": "primary", "name": "High Street"}) is None


# ---------- _fmt_coord -------------------------------------------------


def test_fmt_coord_five_decimal_places():
    assert _fmt_coord(51.5194382) == "51.51944"
    assert _fmt_coord(-0.127) == "-0.12700"


# ---------- _triples_for_entity: semantic --------------------------------


def test_triples_british_museum():
    tags = {
        "name": "The British Museum",
        "tourism": "museum",
        "addr:city": "London",
        "wikidata": "Q6373",
    }
    triples = list(_triples_for_entity(16217891, "w", tags, 51.51943, -0.12700))
    # 3 semantic + 3 geometry = 6
    assert len(triples) == 6
    relations = {t.relation: t for t in triples}
    assert relations["is_a"].object == "museum"
    assert relations["located_in"].object == "London"
    assert relations["wikidata_id"].object == "Q6373"
    # Geometry triples use the instance subject
    assert relations["has_name"].subject == "The British Museum#w16217891"
    assert relations["has_name"].object == "The British Museum"
    assert relations["at_coords"].object == "51.51943,-0.12700"
    assert len(relations["in_geohash"].object) == 7


def test_triples_restaurant_with_multi_cuisine_and_brand():
    tags = {
        "name": "Pizza Express Soho",
        "amenity": "restaurant",
        "cuisine": "italian;pizza",
        "brand": "Pizza Express",
        "addr:city": "London",
    }
    triples = list(_triples_for_entity(2, "n", tags, 51.51234, -0.13456))
    # is_a + located_in + 2 cuisines + brand + 3 geometry = 8
    assert len(triples) == 8
    by_relation = {t.relation: [x for x in triples if x.relation == t.relation] for t in triples}
    cuisines = {t.object for t in by_relation["has_cuisine"]}
    assert cuisines == {"italian", "pizza"}
    assert by_relation["has_brand"][0].object == "Pizza Express"


def test_triples_skipped_when_no_name():
    assert list(_triples_for_entity(1, "n", {"amenity": "restaurant"})) == []


def test_triples_skipped_when_primary_tag_not_whitelisted():
    tags = {"name": "High Street", "highway": "residential"}
    assert list(_triples_for_entity(1, "w", tags)) == []


def test_triples_without_geometry_emit_semantic_only():
    tags = {"name": "Somewhere", "amenity": "cafe"}
    triples = list(_triples_for_entity(1, "n", tags, None, None))
    # Only is_a — no located_in, no brand, no cuisine, no geometry
    assert len(triples) == 1
    assert triples[0].relation == "is_a"
    assert triples[0].object == "cafe"


def test_triples_brand_same_as_name_skipped():
    """When brand equals name there's nothing new to say."""
    tags = {"name": "Starbucks", "amenity": "cafe", "brand": "Starbucks"}
    triples = list(_triples_for_entity(1, "n", tags, 51.5, -0.1))
    relations = {t.relation for t in triples}
    assert "has_brand" not in relations
