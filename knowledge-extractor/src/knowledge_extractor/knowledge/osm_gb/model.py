"""Shared contract between the OSM-GB downloader and extractor.

Source: the Geofabrik Great Britain extract, a weekly-updated PBF dump of
every OSM entity within the GB boundary (~2 GB compressed). The downloader
streams it to disk; the extractor walks it with pyosmium and yields triples
for named amenities, shops, tourism sites, historic sites, leisure areas,
and named natural features.

Licence: OSM data is ODbL 1.0 (share-alike with attribution). Triples
derived from this dataset inherit that constraint — downstream consumers
must attribute OpenStreetMap contributors and share derivatives under ODbL.
"""

from __future__ import annotations

from pathlib import Path

from ...base import DatasetMeta, RawLayout


META = DatasetMeta(
    name="osm-gb",
    category="knowledge",
    version="geofabrik-gb-latest",
    license="ODbL 1.0 (OpenStreetMap contributors)",
    url="https://download.geofabrik.de/europe/great-britain.html",
    layer_band="knowledge",
    description="Named places, amenities, and landmarks from the OSM GB extract",
)


GEOFABRIK_URL = "https://download.geofabrik.de/europe/great-britain-latest.osm.pbf"
PBF_FILENAME = "great-britain-latest.osm.pbf"

# Sanity lower-bound: the real file is ~2 GB. Anything smaller than 500MB
# is almost certainly a truncated/partial download; verify() treats it as
# missing and the downloader refuses to skip the fetch.
MIN_PBF_BYTES = 500_000_000

# Minimum / maximum name length to accept, and minimum primary-tag match
# required for an entity to be emitted. Tight filters matter — the raw
# extract has tens of millions of untagged geometry entries we don't want.
MIN_NAME_LEN = 3
MAX_NAME_LEN = 100

# Coordinate precision: 5 decimal places ≈ 1.1 m at the equator, which is
# well inside OSM's positional accuracy. Any more is spurious precision.
COORD_DECIMALS = 5

# Geohash precision: 7 characters ≈ 153 m × 153 m cell at mid-latitudes.
# Tight enough that "same cell" means "same block", loose enough that a
# chain store and its neighbours cluster together for proximity queries.
GEOHASH_PRECISION = 7


# Primary tag whitelist. None = accept any value for that key.
PRIMARY_TAGS: dict[str, set[str] | None] = {
    "amenity": {
        "restaurant", "cafe", "pub", "bar", "fast_food",
        "bank", "pharmacy", "hospital", "clinic",
        "school", "university", "college", "library",
        "theatre", "cinema", "museum", "arts_centre",
        "place_of_worship", "post_office", "townhall",
    },
    "shop":     None,  # any shop=*
    "tourism": {
        "hotel", "guest_house", "hostel", "motel",
        "attraction", "museum", "gallery", "viewpoint",
        "artwork", "zoo", "aquarium", "theme_park",
    },
    "historic": {
        "castle", "monument", "memorial", "ruins",
        "church", "archaeological_site", "fort",
        "manor", "tower", "wayside_cross",
    },
    "leisure": {
        "park", "stadium", "sports_centre",
        "nature_reserve", "golf_course", "garden",
    },
    "natural": {"peak", "water", "cape", "bay", "beach"},
}


class OsmGbRawLayout(RawLayout):
    """Raw layout: a single ``great-britain-latest.osm.pbf`` file."""

    def pbf_path(self) -> Path:
        return self.raw_dir / PBF_FILENAME

    def verify(self) -> bool:
        p = self.pbf_path()
        return p.exists() and p.stat().st_size >= MIN_PBF_BYTES
