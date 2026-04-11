"""Walks the OSM GB PBF and yields named-entity triples.

Two relation families are emitted, using two different subject schemes:

**Semantic** (bare ``<name>`` subjects — chain stores collapse on dedup):

* ``is_a``       — ``<name>`` → primary tag value (e.g. ``restaurant``)
* ``located_in`` — ``<name>`` → ``addr:city`` value (when present)
* ``has_cuisine``— ``<name>`` → cuisine type (restaurant/cafe/bar/pub only)
* ``has_brand``  — ``<name>`` → ``brand`` value (when it differs from name)
* ``wikidata_id``— ``<name>`` → ``Q<id>`` (cross-link to knowledge/wikidata)

**Geometry** (per-instance subjects ``<name>#<kind><osm_id>`` so every
branch of a chain keeps its own coords):

* ``has_name``   — instance → its human name (bridge back to the semantic
  family so a joiner can link the two views)
* ``at_coords``  — instance → ``"<lat>,<lon>"`` at 5-decimal precision (~1m)
* ``in_geohash`` — instance → 7-char geohash (~150m grid cell) for cheap
  proximity clustering

Entities without a usable ``name`` tag, or whose primary tag isn't in
``PRIMARY_TAGS``, are skipped.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from ...base import BaseExtractor, DatasetMeta, RawTriple
from ...paths import default_raw_dir
from .model import (
    COORD_DECIMALS,
    GEOHASH_PRECISION,
    MAX_NAME_LEN,
    META,
    MIN_NAME_LEN,
    PRIMARY_TAGS,
    OsmGbRawLayout,
)


_CUISINE_PRIMARIES = {"restaurant", "cafe", "fast_food", "pub", "bar"}
_GEOHASH_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"


def _is_usable_name(name: str) -> bool:
    if not name:
        return False
    n = name.strip()
    if len(n) < MIN_NAME_LEN or len(n) > MAX_NAME_LEN:
        return False
    if n.isdigit():
        return False
    return True


def _primary_tag(tags: dict[str, str]) -> tuple[str, str] | None:
    """Return ``(key, value)`` for the first whitelisted primary tag on an
    entity, or ``None`` if it has no primary tag worth emitting."""
    for key, whitelist in PRIMARY_TAGS.items():
        value = tags.get(key)
        if not value:
            continue
        if whitelist is None or value in whitelist:
            return key, value
    return None


def _geohash(lat: float, lon: float, precision: int = GEOHASH_PRECISION) -> str:
    """Encode ``(lat, lon)`` as a geohash of ``precision`` base-32 characters.

    Standard geohash algorithm: alternate bit-splits of longitude and
    latitude ranges, group 5 bits per base-32 character. No external dep.
    """
    lat_lo, lat_hi = -90.0, 90.0
    lon_lo, lon_hi = -180.0, 180.0
    out: list[str] = []
    bits = 0
    bit_count = 0
    even = True  # start with longitude
    while len(out) < precision:
        if even:
            mid = (lon_lo + lon_hi) / 2
            if lon >= mid:
                bits = (bits << 1) | 1
                lon_lo = mid
            else:
                bits <<= 1
                lon_hi = mid
        else:
            mid = (lat_lo + lat_hi) / 2
            if lat >= mid:
                bits = (bits << 1) | 1
                lat_lo = mid
            else:
                bits <<= 1
                lat_hi = mid
        even = not even
        bit_count += 1
        if bit_count == 5:
            out.append(_GEOHASH_BASE32[bits])
            bits = 0
            bit_count = 0
    return "".join(out)


def _fmt_coord(x: float) -> str:
    return f"{x:.{COORD_DECIMALS}f}"


def _instance_id(name: str, osm_kind: str, osm_id: int) -> str:
    return f"{name}#{osm_kind}{osm_id}"


def _semantic_triples(
    name: str, primary_value: str, tags: dict[str, str], prov: str
) -> Iterator[RawTriple]:
    yield RawTriple(
        subject=name, relation="is_a", object=primary_value, provenance=prov
    )

    city = tags.get("addr:city", "").strip()
    if city and _is_usable_name(city):
        yield RawTriple(
            subject=name, relation="located_in", object=city, provenance=prov
        )

    if primary_value in _CUISINE_PRIMARIES:
        cuisine = tags.get("cuisine", "").strip()
        if cuisine:
            for c in cuisine.split(";"):
                c = c.strip().lower()
                if c:
                    yield RawTriple(
                        subject=name,
                        relation="has_cuisine",
                        object=c,
                        provenance=prov,
                    )

    brand = tags.get("brand", "").strip()
    if brand and brand != name and _is_usable_name(brand):
        yield RawTriple(
            subject=name, relation="has_brand", object=brand, provenance=prov
        )

    qid = tags.get("wikidata", "").strip()
    if len(qid) > 1 and qid.startswith("Q") and qid[1:].isdigit():
        yield RawTriple(
            subject=name, relation="wikidata_id", object=qid, provenance=prov
        )


def _geometry_triples(
    name: str,
    osm_kind: str,
    osm_id: int,
    lat: float | None,
    lon: float | None,
    prov: str,
) -> Iterator[RawTriple]:
    if lat is None or lon is None:
        return
    instance = _instance_id(name, osm_kind, osm_id)
    yield RawTriple(
        subject=instance, relation="has_name", object=name, provenance=prov
    )
    yield RawTriple(
        subject=instance,
        relation="at_coords",
        object=f"{_fmt_coord(lat)},{_fmt_coord(lon)}",
        provenance=prov,
    )
    yield RawTriple(
        subject=instance,
        relation="in_geohash",
        object=_geohash(lat, lon),
        provenance=prov,
    )


def _triples_for_entity(
    osm_id: int,
    osm_kind: str,
    tags: dict[str, str],
    lat: float | None = None,
    lon: float | None = None,
) -> Iterator[RawTriple]:
    name = tags.get("name", "").strip()
    if not _is_usable_name(name):
        return
    primary = _primary_tag(tags)
    if primary is None:
        return
    _primary_key, primary_value = primary
    prov = f"osm:{osm_kind}:{osm_id}"

    yield from _semantic_triples(name, primary_value, tags, prov)
    yield from _geometry_triples(name, osm_kind, osm_id, lat, lon, prov)


def _way_centroid(w) -> tuple[float, float] | None:
    """Arithmetic mean of a way's member-node coordinates.

    Requires the pbf to be walked with ``locations=True`` so nodes resolve
    inline. Returns ``None`` if any node in the way has no location (which
    can happen at the extract boundary).
    """
    lats: list[float] = []
    lons: list[float] = []
    try:
        for node_ref in w.nodes:
            lats.append(node_ref.lat)
            lons.append(node_ref.lon)
    except Exception:
        return None
    if not lats:
        return None
    return sum(lats) / len(lats), sum(lons) / len(lons)


class OsmGbExtractor(BaseExtractor):
    def meta(self) -> DatasetMeta:
        return META

    def extract(self, config: dict) -> Iterator[RawTriple]:
        raw_dir = Path(config.get("raw_dir") or default_raw_dir())
        layout = OsmGbRawLayout(raw_dir=raw_dir / META.category / META.name)
        pbf = layout.pbf_path()
        if not pbf.exists():
            return

        import osmium  # type: ignore  # optional dep via `[osm]` extra

        class _Handler(osmium.SimpleHandler):  # type: ignore[misc]
            def __init__(self) -> None:
                super().__init__()
                self.buffered: list[RawTriple] = []

            def _absorb_node(self, n) -> None:
                tag_dict = {t.k: t.v for t in n.tags}
                try:
                    lat: float | None = n.location.lat
                    lon: float | None = n.location.lon
                except Exception:
                    lat = lon = None
                self.buffered.extend(
                    _triples_for_entity(n.id, "n", tag_dict, lat, lon)
                )

            def _absorb_way(self, w) -> None:
                tag_dict = {t.k: t.v for t in w.tags}
                centroid = _way_centroid(w)
                lat, lon = centroid if centroid else (None, None)
                self.buffered.extend(
                    _triples_for_entity(w.id, "w", tag_dict, lat, lon)
                )

            def node(self, n):  # noqa: D401
                self._absorb_node(n)

            def way(self, w):  # noqa: D401
                self._absorb_way(w)

            def relation(self, r):  # noqa: D401
                # Relations are complex multi-polygon things — skip for now.
                # Most named POIs are nodes or ways; relations would need a
                # separate geometry resolver.
                pass

        handler = _Handler()
        handler.apply_file(str(pbf), locations=True)
        yield from handler.buffered
