"""Fetches Brown + WordNet corpora used for morphology candidates."""

from __future__ import annotations

from typing import ClassVar

from ...base import DatasetMeta, NLTKBackedDownloader, NLTKRawLayout
from .model import META, MorphologyRawLayout


class MorphologyDownloader(NLTKBackedDownloader):
    NLTK_PACKAGES: ClassVar[list[tuple[str, str]]] = MorphologyRawLayout.NLTK_PACKAGES
    LAYOUT_CLASS: ClassVar[type[NLTKRawLayout]] = MorphologyRawLayout

    def meta(self) -> DatasetMeta:
        return META
