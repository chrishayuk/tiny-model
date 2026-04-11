"""Fetches WordNet corpus files via NLTK."""

from __future__ import annotations

from typing import ClassVar

from ...base import DatasetMeta, NLTKBackedDownloader, NLTKRawLayout
from .model import META, WordNetRawLayout


class WordNetDownloader(NLTKBackedDownloader):
    NLTK_PACKAGES: ClassVar[list[tuple[str, str]]] = WordNetRawLayout.NLTK_PACKAGES
    LAYOUT_CLASS: ClassVar[type[NLTKRawLayout]] = WordNetRawLayout

    def meta(self) -> DatasetMeta:
        return META
