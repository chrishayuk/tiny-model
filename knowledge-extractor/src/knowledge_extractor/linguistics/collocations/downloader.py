"""Fetches Brown + universal tagset via NLTK."""

from __future__ import annotations

from typing import ClassVar

from ...base import DatasetMeta, NLTKBackedDownloader, NLTKRawLayout
from .model import META, CollocationsRawLayout


class CollocationsDownloader(NLTKBackedDownloader):
    NLTK_PACKAGES: ClassVar[list[tuple[str, str]]] = CollocationsRawLayout.NLTK_PACKAGES
    LAYOUT_CLASS: ClassVar[type[NLTKRawLayout]] = CollocationsRawLayout

    def meta(self) -> DatasetMeta:
        return META
