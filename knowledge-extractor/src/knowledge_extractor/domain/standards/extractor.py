"""Yields triples from the hand-curated standards tables in ``model.py``."""

from __future__ import annotations

from typing import Iterator

from ...base import BaseExtractor, DatasetMeta, RawTriple
from .model import META, TABLES


class StandardsExtractor(BaseExtractor):
    def meta(self) -> DatasetMeta:
        return META

    def extract(self, config: dict) -> Iterator[RawTriple]:
        for relation, table in TABLES:
            for key, value in table.items():
                yield RawTriple(
                    subject=key,
                    relation=relation,
                    object=value,
                    provenance="iana",
                )
