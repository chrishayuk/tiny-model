"""Shared contract between the Natural Earth downloader and extractor.

Natural Earth ships as free shapefile bundles at 1:10m / 1:50m / 1:110m
scales. We pull two 10m cultural layers for their attribute tables
(we don't use the geometry at all — the value is in the DBF columns):

* ``ne_10m_admin_0_countries`` — ~258 sovereign states + dependencies
  with sovereignty chains, ISO codes, Natural Earth's TYPE
  classification, UN regions, World Bank regions, economic grouping,
  and World Bank income group.
* ``ne_10m_admin_1_states_provinces`` — ~4600 subnational regions
  (states, provinces, counties, regions) linked to their parent
  country, with ISO 3166-2 codes.

Both zips total ~20 MB. Downloader fetches and unzips; extractor uses
``pyshp`` to read the DBF attribute tables.
"""

from __future__ import annotations

from pathlib import Path

from ...base import DatasetMeta, RawLayout


META = DatasetMeta(
    name="natural-earth",
    category="knowledge",
    version="10m-2022-05",
    license="public domain (Natural Earth)",
    url="https://www.naturalearthdata.com/",
    layer_band="knowledge",
    description="Country sovereignty chains + admin-1 subdivisions from Natural Earth 10m cultural vectors",
)


CDN_BASE = "https://naciscdn.org/naturalearth/10m/cultural"


# (short name, zip filename, shapefile stem, on-disk subfolder)
LAYERS: list[tuple[str, str, str, str]] = [
    (
        "admin_0",
        "ne_10m_admin_0_countries.zip",
        "ne_10m_admin_0_countries",
        "10m_admin_0",
    ),
    (
        "admin_1",
        "ne_10m_admin_1_states_provinces.zip",
        "ne_10m_admin_1_states_provinces",
        "10m_admin_1",
    ),
]


def layer_url(zip_filename: str) -> str:
    return f"{CDN_BASE}/{zip_filename}"


class NaturalEarthRawLayout(RawLayout):
    """Raw layout: one subfolder per shapefile layer, each holding
    ``.shp`` + ``.shx`` + ``.dbf`` (+ ``.prj``)."""

    def layer_dir(self, subfolder: str) -> Path:
        return self.raw_dir / subfolder

    def shapefile_stem(self, subfolder: str, stem: str) -> Path:
        """Return the path **without** extension — pyshp ``Reader(str(stem))``
        discovers the sibling files automatically."""
        return self.layer_dir(subfolder) / stem

    def shp_path(self, subfolder: str, stem: str) -> Path:
        return self.shapefile_stem(subfolder, stem).with_suffix(".shp")

    def dbf_path(self, subfolder: str, stem: str) -> Path:
        return self.shapefile_stem(subfolder, stem).with_suffix(".dbf")

    def verify(self) -> bool:
        if not self.raw_dir.exists():
            return False
        for _, _, stem, subfolder in LAYERS:
            if not self.shp_path(subfolder, stem).exists():
                return False
            if not self.dbf_path(subfolder, stem).exists():
                return False
        return True


# Relation mappings for the admin_0 extractor: (dbf_column, relation_name).
# Columns are case-sensitive as they appear in the DBF; the extractor looks
# them up case-insensitively to survive NE version drift.
ADMIN0_SCALAR_RELATIONS: list[tuple[str, str]] = [
    ("TYPE",       "ne_type"),
    ("CONTINENT",  "continent_ne"),
    ("REGION_UN",  "region_un"),
    ("SUBREGION",  "subregion_un"),
    ("REGION_WB",  "region_wb"),
    ("ECONOMY",    "economy_class"),
    ("INCOME_GRP", "income_group"),
    ("ISO_A2",     "iso_alpha2"),
    ("ISO_A3",     "iso_alpha3"),
    ("ISO_N3",     "iso_numeric"),
]


# Values Natural Earth uses to signal "no value" in codes/classifications.
_NE_NULL_TOKENS = {"", "-99", "-1", "nan", "none", "null"}


def is_null_value(value: object) -> bool:
    """NE uses sentinel strings like '-99' and '-1' for missing values."""
    if value is None:
        return True
    s = str(value).strip().lower()
    return s in _NE_NULL_TOKENS
