"""Walks the hand-curated country tables and yields raw triples.

For every country in ``_data.py``, emits one triple per scalar field
plus one ``official_language`` triple per language in the ``languages``
list and a ``un_member`` triple when the country is a UN member (omitted
when False to keep the output compact).
"""

from __future__ import annotations

from typing import Iterator

from ...base import BaseExtractor, DatasetMeta, RawTriple
from .model import COUNTRIES, META, SCALAR_RELATIONS


class CountriesExtractor(BaseExtractor):
    def meta(self) -> DatasetMeta:
        return META

    def extract(self, config: dict) -> Iterator[RawTriple]:
        for country in COUNTRIES:
            name = country["name"]
            prov = f"iso3166:{country['alpha3']}"

            for key, relation in SCALAR_RELATIONS:
                value = country.get(key)
                if not value:
                    continue
                yield RawTriple(
                    subject=name,
                    relation=relation,
                    object=str(value),
                    provenance=prov,
                )

            for language in country.get("languages", []):
                yield RawTriple(
                    subject=name,
                    relation="official_language",
                    object=language,
                    provenance=prov,
                )

            if country.get("un_member"):
                yield RawTriple(
                    subject=name,
                    relation="un_member",
                    object="yes",
                    provenance=prov,
                )
