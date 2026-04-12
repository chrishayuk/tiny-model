"""Reads the Natural Earth 10m cultural shapefiles and yields raw triples.

Two passes:

1. **admin_0** — for every country / dependency row, emit a block of
   relations keyed off the NAME column:

   * ``sovereignty`` — name → sovereign state (only when different)
   * ``ne_type`` — name → Natural Earth TYPE (Sovereign country,
     Dependency, Disputed, Indeterminate, Country)
   * ``continent_ne`` — name → NE continent attribution
   * ``region_un``, ``subregion_un`` — UN M49 region / subregion
   * ``region_wb`` — World Bank region
   * ``economy_class`` — NE economy classification (Developed G7, …)
   * ``income_group`` — World Bank income group
   * ``iso_alpha2`` / ``iso_alpha3`` / ``iso_numeric`` — cross-check
     with the countries dataset
   * ``wikidata_id`` — cross-link with knowledge/wikidata

2. **admin_1** — for every subnational region, emit:

   * ``within`` — subnational → parent country
   * ``iso_3166_2`` — subnational → ISO 3166-2 code (e.g. "GB-ENG")
   * ``admin_type`` — subnational → type_en (province, state, region, …)

Numeric-prefixed NE classifications like ``"2. Developed region: non-G7"``
get the numeric prefix stripped so the object is a clean token.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator

from ...base import BaseExtractor, DatasetMeta, RawTriple
from ...paths import default_raw_dir
from .model import (
    ADMIN0_SCALAR_RELATIONS,
    LAYERS,
    META,
    NaturalEarthRawLayout,
    is_null_value,
)


_NE_PREFIX = re.compile(r"^\s*\d+\.\s+")


def _strip_ne_prefix(value: str) -> str:
    """NE classifications carry sort prefixes like ``'2. Developed region'``.
    Strip them so the object token is clean."""
    return _NE_PREFIX.sub("", value).strip()


def _records_as_dicts(reader) -> Iterator[dict[str, object]]:
    """Yield each shapefile record as a lowercase-keyed dict.

    Natural Earth column casing has drifted over time (``NAME`` vs
    ``name``). Normalising here lets the rest of the code use one set of
    key names.
    """
    fields = [f[0] for f in reader.fields[1:]]  # skip DeletionFlag
    for record in reader.records():
        yield {f.lower(): record[i] for i, f in enumerate(fields)}


def _str_value(record: dict[str, object], key: str) -> str | None:
    value = record.get(key.lower())
    if is_null_value(value):
        return None
    return str(value).strip()


_SOVEREIGNTY_SKIP_TYPES = {"Indeterminate", "Disputed"}


def _admin0_triples(record: dict[str, object]) -> Iterator[RawTriple]:
    name = _str_value(record, "NAME") or _str_value(record, "NAME_LONG")
    if not name:
        return
    adm0_a3 = _str_value(record, "ADM0_A3") or ""
    sov_a3 = _str_value(record, "SOV_A3") or ""
    ne_type = _str_value(record, "TYPE") or ""
    # ADM0_A3 is always populated and unique; ISO_A3 is '-99' for many
    # dependencies. Prefer ADM0_A3 for provenance.
    prov = f"ne_admin0:{adm0_a3}" if adm0_a3 else "ne_admin0"

    # Sovereignty chain: only emit when the entity's own code differs
    # from its sovereign's code (signalling a real dependency) AND the
    # NE TYPE isn't "Indeterminate" or "Disputed". Comparing NAME to
    # SOVEREIGNT is wrong — NE uses abbreviated NAME ('Tanzania') vs
    # long-form SOVEREIGNT ('United Republic of Tanzania') for the
    # same entity, and that would emit a false dependency.
    sovereignty = _str_value(record, "SOVEREIGNT")
    if (
        sovereignty
        and sov_a3
        and adm0_a3
        and sov_a3 != adm0_a3
        and ne_type not in _SOVEREIGNTY_SKIP_TYPES
    ):
        yield RawTriple(
            subject=name, relation="sovereignty", object=sovereignty, provenance=prov
        )

    for column, relation in ADMIN0_SCALAR_RELATIONS:
        value = _str_value(record, column)
        if not value:
            continue
        clean = _strip_ne_prefix(value)
        if not clean:
            continue
        yield RawTriple(
            subject=name, relation=relation, object=clean, provenance=prov
        )

    wd = _str_value(record, "WIKIDATAID") or _str_value(record, "WIKIDATA_ID")
    if wd and wd.startswith("Q") and wd[1:].isdigit():
        yield RawTriple(
            subject=name, relation="wikidata_id", object=wd, provenance=prov
        )


def _admin1_triples(record: dict[str, object]) -> Iterator[RawTriple]:
    name = (
        _str_value(record, "NAME")
        or _str_value(record, "NAME_EN")
        or _str_value(record, "WOE_NAME")
    )
    if not name:
        return
    parent = _str_value(record, "ADMIN") or _str_value(record, "GEONUNIT")
    iso_3166_2 = _str_value(record, "ISO_3166_2")
    type_en = _str_value(record, "TYPE_EN") or _str_value(record, "TYPE")
    prov = f"ne_admin1:{iso_3166_2}" if iso_3166_2 else "ne_admin1"

    if parent:
        yield RawTriple(
            subject=name, relation="within", object=parent, provenance=prov
        )
    if iso_3166_2:
        yield RawTriple(
            subject=name, relation="iso_3166_2", object=iso_3166_2, provenance=prov
        )
    if type_en:
        yield RawTriple(
            subject=name, relation="admin_type", object=type_en, provenance=prov
        )


class NaturalEarthExtractor(BaseExtractor):
    def meta(self) -> DatasetMeta:
        return META

    def extract(self, config: dict) -> Iterator[RawTriple]:
        raw_dir = Path(config.get("raw_dir") or default_raw_dir())
        layout = NaturalEarthRawLayout(raw_dir=raw_dir / META.category / META.name)

        import shapefile  # type: ignore  # optional dep via `[natural-earth]` extra

        for short, _zip_name, stem, subfolder in LAYERS:
            shp_stem = layout.shapefile_stem(subfolder, stem)
            if not layout.shp_path(subfolder, stem).exists():
                continue
            reader = shapefile.Reader(str(shp_stem))
            try:
                shape_triples = _admin0_triples if short == "admin_0" else _admin1_triples
                for record in _records_as_dicts(reader):
                    yield from shape_triples(record)
            finally:
                reader.close()
